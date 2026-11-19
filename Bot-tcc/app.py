import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, render_template, request, session
from nlp.classifier import predict
from nlp.knowledge_base import retrieve as retrieve_qa
from nlp.preprocess import normalize_text
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent
with open(ROOT / "database" / "institutional_data.json", encoding="utf-8") as f:
    INSTITUTIONAL = json.load(f)
with open(ROOT / "database" / "demo_students.json", encoding="utf-8") as f:
    DEMO_DATA = json.load(f)

app = Flask(__name__)
secret_key = os.getenv("SECRET_KEY")
if os.getenv("APP_ENV") == "production" and not secret_key:
    raise RuntimeError("SECRET_KEY deve ser configurada em produção")
app.config["SECRET_KEY"] = secret_key or "local-development-secret-change-me"
app.config["SESSION_COOKIE_NAME"] = "chatbot_tgi_session"
app.config["SESSION_COOKIE_HTTPONLY"] = True
# O padrão de produção é compatível com o Preview HTTPS embutido. Para execução
# em HTTP local, use COOKIE_SECURE=0 no .env ou no comando de inicialização.
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "1") == "1"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
ALLOWED_ATTACHMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"}
FEEDBACK_LOG = []
RESOLUTION_LOG = []
QUESTION_LOG_PATH = ROOT / "database" / "question_logs.jsonl"
ADMIN_PANEL_TOKEN = os.getenv("ADMIN_PANEL_TOKEN") or ("admin" if os.getenv("APP_ENV") != "production" else None)

FALLBACK = "Desculpe, não tenho acesso a uma informação confirmada sobre esse assunto. Recomendo procurar a CAA online, abrindo um chamado na Área do Aluno, ou dirigir-se presencialmente à CAA do campus Anália Franco."
HELP = "Você pode perguntar sobre endereço, horário da CAA, canais de atendimento, infraestrutura, ou sobre os dados do perfil fictício selecionado, como nota, curso, RGM, e-mail e frequência."
CAA_GUIDANCE = "Para tirar uma dúvida acadêmica, dirija-se à CAA do campus presencialmente ou abra um chamado online na Área do Aluno. Os dois canais são a Central de Atendimento ao Aluno (CAA) da Universidade Cruzeiro do Sul."
OFFICIAL_SOURCE = "Esta informação veio dos canais oficiais da Universidade Cruzeiro do Sul. Consulte a página oficial da CAA: https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/"
ADDRESS_GUIDANCE = "O campus Anália Franco fica na Av. Regente Feijó, 1.295, Vila Regente Feijó, São Paulo — SP, CEP 03342-000."
HOURS_GUIDANCE = "O horário geral de funcionamento informado para atendimento é de segunda a sexta-feira, das 8h às 21h, e aos sábados, das 11h às 15h. Domingos, feriados, férias e recessos podem ter horários diferentes; confirme com a CAA."
RESOLUTION_TYPES = {"orientacao", "orientacao_revisada", "encaminhamento", "esclarecimento"}
RESOLUTION_REASONS = {
    "opcao_nao_aparece": "A opção indicada não aparece.",
    "pagina_nao_abriu": "A página não abriu.",
    "mensagem_erro": "Apareceu uma mensagem de erro.",
    "nao_entendi": "Ainda não entendi a orientação.",
    "preciso_pessoa": "Preciso falar com uma pessoa.",
}
INTENT_LABELS = {
    "rematricula": "rematrícula",
    "atividades_complementares": "atividades complementares",
    "documento_financeiro": "documentos ou assunto financeiro",
    "calendario_academico": "calendário acadêmico",
    "duvida_academica": "dúvida acadêmica",
    "pedido_esclarecimento": "orientação acadêmica",
    "financeiro_navegacao": "navegação financeira na Área do Aluno",
    "base_qa_revisada": "resposta acadêmica revisada",
}

QA_URL = "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/"
INDIVIDUAL_INTENTS = {"consulta_nota_perfil", "consulta_curso_perfil", "consulta_rgm_perfil", "consulta_email_perfil", "consulta_horario_aulas_perfil", "consulta_sala_perfil", "frequencia"}

FINANCE_TERMS = ("financeiro", "mensalidade", "pagamento", "pagamentos", "boleto", "acordo", "desconto", "demonstrativo", "cartao", "cartão", "rematricula", "rematrícula")
FINANCE_SENSITIVE_TERMS = (
    "gerar boleto", "gere boleto", "emitir boleto", "emita boleto", "baixar boleto", "mande boleto", "me mande o boleto", "segunda via", "boleto especifico", "boleto específico",
    "gerar documento", "emitir documento", "baixar documento", "comprovante", "declaracao", "declaração",
    "valor exato", "valor da mensalidade", "quanto devo", "minha divida", "minha dívida", "consultar divida",
    "consultar dívida", "pagamento foi realizado", "pagamento foi compensado", "negociar valor", "negociar dívida",
    "dados financeiros", "meus dados financeiros",
)


def special_intent(message):
    """Regras explícitas para requisitos acadêmicos e encaminhamentos sensíveis."""
    text = normalize_text(message)
    if any(term in text for term in ("fonte", "de onde veio", "link oficial", "site cruzeiro")):
        return "fonte_resposta"
    if "atividade complementar" in text or "atividades complementares" in text:
        return "atividades_complementares"
    if "rematricula" in text or "rematricula" in text:
        return "rematricula"
    if "calendario academico" in text or "calendario de aulas" in text:
        return "calendario_academico"
    if any(term in text for term in ("acaba as aulas", "acaba aulas", "acabam as aulas", "acabam aulas", "terminam as aulas", "terminam aulas", "termina as aulas", "termina aulas", "fim das aulas", "fim aulas", "final das aulas", "final aulas", "encerram as aulas", "encerram aulas", "quando termina o semestre", "quando acaba o semestre")):
        return "calendario_academico"
    if any(term in text for term in FINANCE_SENSITIVE_TERMS) or (
        "documento" in text and any(term in text for term in FINANCE_TERMS)
    ):
        return "documento_financeiro"
    if "oferta" in text and "rematricula" in text:
        return "financeiro_navegacao"
    if "condic" in text and "rematricula" in text:
        return "financeiro_navegacao"
    if any(term in text for term in FINANCE_TERMS if term not in {"rematricula", "rematrícula"}):
        return "financeiro_navegacao"
    if "af" in text.split() or "avaliacao final" in text or "periodo af" in text:
        return "prova_af"
    if any(term in text for term in ("apresentacao do tgi", "apresentacao tgi", "apresentar o tgi", "defesa do tgi", "defesa tgi")):
        return "apresentacao_tgi"
    if "prova" in text and any(term in text for term in ("online", "on line", "ead", "remota", "remoto")):
        return "prova_online"
    if "prova" in text or "avaliacao" in text:
        return "provas"
    if any(term in text for term in ("horario de aula", "horario aulas", "horario das aulas", "horarios de aula", "horarios aulas", "horarios das aulas", "grade de aula", "grade aulas", "grade de aulas", "minhas aulas", "minha grade", "disciplina da noite", "aulas noturnas")):
        return "consulta_horario_aulas_perfil"
    if "sala" in text or "laboratorio" in text or "ambiente" in text:
        if any(term in text for term in ("hoje", "aula", "turma", "meu", "minha", "aluno")):
            return "consulta_sala_perfil"
    if any(term in text.split() for term in ("horario", "hora", "horas", "abre", "aberto", "aberta", "fecha", "fechado", "fechada", "funcionamento", "atendimento", "manha", "tarde", "noite")):
        return "horario_funcionamento"
    if any(term in text for term in ("endereco", "rua", "avenida", "cep", "onde fica", "como chegar", "localizacao")):
        return "endereco_campus"
    if "duvida academica" in text or "duvida" in text and any(term in text for term in ("setor", "tirar", "academica")):
        return "duvida_academica"
    if any(term in text for term in ("como faco isso", "onde vejo isso", "quando e isso", "nao consigo resolver meu problema", "como funciona isso", "como funciona")):
        return "pedido_esclarecimento"
    return None


def profile():
    selected = session.get("profile_id")
    return next((p for p in DEMO_DATA["perfis"] if p["identificador_do_perfil"] == selected), None)


def restore_profile_from_request(data):
    """Recupera o perfil sintético em navegadores que não preservam o cookie."""
    current = profile()
    if current:
        return current
    requested_id = data.get("profile_id") if data else None
    allowed = {p["identificador_do_perfil"] for p in DEMO_DATA["perfis"]}
    if requested_id in allowed:
        session["profile_id"] = requested_id
        return profile()
    return None


def controlled_answer(intent):
    if intent in {"endereco_campus", "horario_caa", "canais_atendimento", "infraestrutura"}:
        item = next((x for x in INSTITUTIONAL if x["intencao"] == intent), None)
        return item
    return None


def individual_answer(intent, selected):
    p = profile()
    if not p:
        return {"resposta": "Escolha um perfil fictício antes de consultar dados individuais.", "tipo": "controle", "encaminhar_humano": False}
    if intent == "consulta_nota_perfil":
        return {"resposta": f"No perfil fictício de {p['nome']}, a nota A1 simulada é {p['nota_a1']:.1f}, a A2 é {p['nota_a2']:.1f} e a média simulada é {p['media']:.1f}.", "tipo": "perfil_sintetico"}
    if intent == "consulta_curso_perfil":
        return {"resposta": f"O curso do perfil fictício selecionado ({p['nome']}) é {p['curso']}, no campus Anália Franco.", "tipo": "perfil_sintetico"}
    if intent == "consulta_rgm_perfil":
        return {"resposta": f"O RGM do perfil fictício selecionado é {p['identificador_do_perfil']}.", "tipo": "perfil_sintetico"}
    if intent == "consulta_email_perfil":
        return {"resposta": f"O e-mail do perfil fictício selecionado é {p['email']}.", "tipo": "perfil_sintetico"}
    if intent == "consulta_horario_aulas_perfil":
        aulas = p.get("horario_aulas_sintetico")
        if not aulas:
            return {"resposta": "Não há uma grade de aulas sintética cadastrada para este perfil de demonstração.", "tipo": "perfil_sintetico"}
        agenda = "; ".join(f"{aula['dia']}: {aula['disciplina']} ({aula['horario']})" for aula in aulas)
        return {"resposta": f"A grade noturna fictícia de {p['nome']} é: {agenda}. Esses horários são sintéticos e existem apenas para demonstração.", "tipo": "perfil_sintetico"}
    if intent == "consulta_sala_perfil":
        sala = p.get("sala_hoje_sintetica")
        if not sala:
            return {"resposta": "Não há uma sala sintética cadastrada para este perfil de demonstração.", "tipo": "perfil_sintetico"}
        return {"resposta": f"Para a demonstração de hoje, a sala do perfil fictício de {p['nome']} é o {sala}. Essa informação é sintética e existe apenas para demonstrar uma consulta de sala; confirme a sala real nos canais oficiais ou com a coordenação.", "tipo": "perfil_sintetico", "encaminhar_humano": True}
    if intent == "frequencia":
        return {"resposta": f"A frequência simulada do perfil fictício de {p['nome']} é {p['frequencia']}.", "tipo": "perfil_sintetico"}
    return None


def chat_response(message):
    result = predict(message)
    override = special_intent(message)
    intent = override or result["intent"]
    qa_match = retrieve_qa(message)
    if qa_match and not override and intent not in INDIVIDUAL_INTENTS:
        return {
            "resposta": qa_match["resposta"],
            "tipo": "orientacao_revisada",
            "fonte": qa_match["fonte"],
            "url": qa_match.get("url", QA_URL),
            "data_consulta": "2026-11-13",
            "encaminhar_humano": True,
            "qa_id": qa_match["id"],
            "qa_numero": qa_match["numero"],
            "similaridade": qa_match["similaridade"],
            "intencao_qa": qa_match["categoria"],
        }
    if not override and (intent == "fallback" or result["confidence"] < 0.07):
        return {"resposta": FALLBACK, "tipo": "fallback", "encaminhar_humano": True}
    if intent == "saudacao":
        return {"resposta": "Olá! Sou o Chatbot TGI II, um protótipo acadêmico para informações gerais do campus Anália Franco e demonstração com perfis fictícios. Como posso ajudar?", "tipo": "controle"}
    if intent == "despedida":
        return {"resposta": "Até mais. Lembre-se de confirmar informações institucionais nos canais oficiais.", "tipo": "controle"}
    if intent == "ajuda":
        return {"resposta": HELP, "tipo": "controle"}
    if intent == "provas":
        return {"resposta": "O período de provas da A1 será realizado entre os dias 26/11 e 02/12.", "tipo": "institucional", "fonte": "Calendário de provas do projeto acadêmico", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "data_consulta": "2026-11-06"}
    if intent == "prova_af":
        return {"resposta": "O período da AF (Avaliação Final) será realizado entre os dias 10/12 e 16/12.", "tipo": "institucional", "fonte": "Calendário de provas do projeto acadêmico", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "data_consulta": "2026-11-11"}
    if intent == "apresentacao_tgi":
        return {"resposta": "A apresentação do TGI está prevista para o dia 12/12. Para confirmar o horário, a sala e as orientações da sua turma, consulte o professor orientador ou a coordenação.", "tipo": "institucional", "fonte": "Calendário acadêmico do projeto", "url": QA_URL, "data_consulta": "2026-11-13", "encaminhar_humano": True}
    if intent == "prova_online":
        return {"resposta": "As provas online serão realizadas entre os dias 13/11 e 14/11. Para confirmar o horário, o link e as regras da sua turma, consulte o calendário acadêmico ou abra um chamado na CAA.", "tipo": "institucional", "fonte": "Calendário acadêmico do projeto", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "data_consulta": "2026-11-13", "encaminhar_humano": True}
    if intent == "horario_funcionamento":
        return {"resposta": HOURS_GUIDANCE, "tipo": "institucional", "fonte": "Universidade Cruzeiro do Sul — Canais de Atendimento", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "data_consulta": "2026-11-11"}
    if intent == "endereco_campus":
        return {"resposta": ADDRESS_GUIDANCE + " O endereço deve ser confirmado nos canais oficiais antes do deslocamento.", "tipo": "institucional", "fonte": "Universidade Cruzeiro do Sul — Canais de Atendimento", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "data_consulta": "2026-11-06"}
    if intent == "duvida_academica":
        return {"resposta": CAA_GUIDANCE, "tipo": "encaminhamento", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "encaminhar_humano": True}
    if intent == "rematricula":
        return {"resposta": "Para efetuar sua rematrícula clique em: Rematrícula > Faça Rematrícula > você será redirecionado para a página de rematrícula, basta seguir o passo a passo até concluir.", "tipo": "orientacao"}
    if intent == "calendario_academico":
        return {"resposta": "Para informações sobre o calendário acadêmico, abra um chamado na CAA online ou peça orientação ao coordenador da sua turma.", "tipo": "encaminhamento", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "encaminhar_humano": True}
    if intent == "atividades_complementares":
        text = normalize_text(message)
        if any(term in text for term in ("duvida", "material", "ajuda")):
            resposta = "Para consultar dúvidas e materiais de apoio, acesse: Atividades Complementares > Dúvidas > Ajuda > selecione o material de apoio ou a opção desejada."
        elif any(term in text for term in ("cadastrar", "cadastre", "nova atividade")):
            resposta = "Para cadastrar uma nova atividade complementar, acesse: Atividades Complementares > Cadastre Uma Nova Atividade > Cadastrar > siga todos os passos até concluir."
        elif any(term in text for term in ("visualize", "visualizar", "cadastrada", "arquivo")):
            resposta = "Para visualizar suas atividades cadastradas, acesse: Atividades Complementares > Visualize Atividades. Para consultar o arquivo, clique em Mais Detalhes > Visualizar Arquivo."
        else:
            resposta = "As atividades complementares são exigências do Ministério da Educação (MEC) para os cursos de graduação no Brasil. Elas servem para ampliar sua formação acadêmica e prática para além da grade curricular tradicional."
        return {"resposta": resposta + " Em caso de dúvida sobre aprovação ou regras específicas, procure o professor coordenador da sua turma ou a CAA.", "tipo": "orientacao", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "encaminhar_humano": True}
    if intent == "financeiro_navegacao":
        text = normalize_text(message)
        if "demonstrativo" in text:
            resposta = "Para consultar o demonstrativo, acesse: Financeiro > Demonstrativo > clique em Imprimir no canto superior direito da tela."
        elif "cartao" in text or "cartão" in message.lower():
            resposta = "Para efetuar um pagamento com cartão, acesse: Financeiro > Meus Pagamentos e Acordos > selecione o título > Fazer acordo > role a barra lateral até o final > selecione o plano de pagamento > Cartão."
        elif "desconto" in text:
            resposta = "Os descontos aparecem nos detalhes do boleto emitido. Em caso de acordo, os valores exibidos já consideram os descontos. Para consultar essa área, acesse Financeiro > Meus Pagamentos e Acordos."
        elif "oferta" in text:
            resposta = "Para acessar a oferta de rematrícula, acesse: Financeiro > Oferta Rematrícula."
        elif "condic" in text and "rematric" in text:
            resposta = "Para acessar as condições especiais da rematrícula, acesse: Financeiro > Condições Especiais (Rematrícula)."
        elif "acordo" in text:
            resposta = "Para consultar pagamentos e acordos, acesse: Financeiro > Meus Pagamentos e Acordos. Selecione o título desejado para ver as opções disponíveis."
        elif "boleto" in text:
            resposta = "Para consultar um boleto dentro do prazo de vencimento, acesse: Financeiro > Meus Pagamentos e Acordos > selecione o título > Boleto. Para boleto vencido ou fora do mês vigente, selecione Fazer acordo e depois o plano de pagamento."
        else:
            resposta = "Para consultar informações financeiras gerais, acesse: Financeiro > Meus Pagamentos e Acordos. Nessa área você encontra títulos, boletos, acordos e opções de pagamento."
        return {"resposta": resposta + " Esta é uma orientação de navegação; o chatbot não acessa dados financeiros reais.", "tipo": "orientacao", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/"}
    if intent == "documento_financeiro":
        return {"resposta": "Posso explicar o caminho geral dentro da Área do Aluno, mas não tenho acesso a documentos, boletos, comprovantes, valores ou dados financeiros individuais. Para gerar ou consultar essas informações, acesse o CAA Online ou procure o CAA presencialmente no campus Anália Franco.", "tipo": "encaminhamento", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "encaminhar_humano": True}
    if intent == "pedido_esclarecimento":
        return {"resposta": "Desculpe, não entendi sua pergunta. Tente repeti-la com mais detalhes. Se o erro persistir, entre em contato com a CAA online ou presencial no campus.", "tipo": "esclarecimento", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "encaminhar_humano": True}
    if intent == "fonte_resposta":
        return {"resposta": OFFICIAL_SOURCE, "tipo": "fonte", "fonte": "Universidade Cruzeiro do Sul — Canais de Atendimento", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "data_consulta": "2026-11-06"}
    if intent == "atendimento_humano":
        return {"resposta": "Para atendimento humano, consulte a página oficial de Canais de Atendimento da Universidade Cruzeiro do Sul. O chatbot não substitui a Central de Atendimento ao Aluno.", "tipo": "encaminhamento", "url": "https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/", "encaminhar_humano": True}
    individual = individual_answer(intent, session.get("profile_id")) if intent in {"consulta_nota_perfil", "consulta_curso_perfil", "consulta_rgm_perfil", "consulta_email_perfil", "consulta_horario_aulas_perfil", "consulta_sala_perfil", "frequencia"} else None
    if individual:
        return individual
    item = controlled_answer(intent)
    if item:
        return {"resposta": item["resposta"] + " " + item["observacao"], "tipo": "institucional", "fonte": item["fonte"], "url": item["url_fonte"], "data_consulta": item["data_consulta"], "pode_mudar": item["pode_mudar"]}
    if intent == "fora_escopo":
        return {"resposta": "Essa pergunta está fora do escopo acadêmico deste protótipo. Posso ajudar com informações públicas do campus Anália Franco ou com o perfil fictício selecionado.", "tipo": "fallback"}
    return {"resposta": "Desculpe, não tenho acesso a essa informação. Tente reformular a pergunta; se o erro persistir, procure a CAA online pela Área do Aluno ou presencialmente no campus.", "tipo": "fallback", "encaminhar_humano": True}


INTENT_EXPLANATIONS = {
    "endereco_campus": ("Localização do campus", "A pergunta pediu um endereço ou localização institucional."),
    "horario_funcionamento": ("Horário de funcionamento", "A pergunta contém sinais de horário, abertura ou atendimento."),
    "provas": ("Calendário de provas A1", "A pergunta menciona provas ou avaliação A1."),
    "prova_af": ("Calendário da Avaliação Final", "A pergunta menciona AF ou Avaliação Final."),
    "prova_online": ("Calendário de provas online", "A pergunta menciona provas online, remotas ou EAD."),
    "apresentacao_tgi": ("Apresentação do TGI", "A pergunta menciona a data de apresentação ou defesa do TGI."),
    "calendario_academico": ("Calendário acadêmico", "A pergunta indica término de aulas ou necessidade de consultar datas acadêmicas."),
    "consulta_horario_aulas_perfil": ("Grade de aulas fictícia", "A pergunta pede horários, disciplinas ou grade de aulas do perfil de demonstração."),
    "consulta_sala_perfil": ("Sala fictícia do dia", "A pergunta pede a sala ou o laboratório associado ao perfil de demonstração para a consulta de hoje."),
    "atividades_complementares": ("Atividades complementares", "A pergunta cita atividades complementares e recebeu orientação geral acadêmica."),
    "financeiro_navegacao": ("Navegação financeira", "A pergunta pediu orientação de caminho na área Financeiro, sem solicitar dado individual."),
    "documento_financeiro": ("Documento ou dado financeiro individual", "A solicitação envolve documento, boleto, comprovante, valor ou outro dado que o protótipo não acessa."),
    "rematricula": ("Rematrícula", "A pergunta menciona o processo de rematrícula."),
    "duvida_academica": ("Encaminhamento acadêmico", "A pergunta solicita ajuda acadêmica que depende da CAA ou da coordenação."),
    "calendario_academico": ("Calendário acadêmico", "A pergunta solicita uma informação que deve ser confirmada pela CAA ou coordenação."),
    "fonte_resposta": ("Fonte da informação", "A pergunta solicitou a origem ou o link oficial da resposta."),
    "pedido_esclarecimento": ("Pedido pouco específico", "A formulação não informa claramente qual procedimento o aluno deseja realizar."),
    "fallback": ("Intenção não determinada", "A confiança ou a correspondência com as intenções conhecidas não foi suficiente."),
}


def build_explanation(message, result, answer):
    """Cria uma explicação curta e específica, sem expor o raciocínio interno do modelo."""
    intent = result.get("intent", "fallback")
    label, reason = INTENT_EXPLANATIONS.get(intent, (intent.replace("_", " ").title(), "A intenção foi associada ao conteúdo mais próximo na base de treinamento."))
    confidence = float(result.get("confidence", 0) or 0)
    if confidence >= 0.65:
        level = "alta"
        level_detail = "Há forte correspondência entre a pergunta e a intenção identificada."
    elif confidence >= 0.25:
        level = "média"
        level_detail = "Existem sinais relevantes, mas a pergunta pode admitir mais de uma interpretação."
    else:
        level = "baixa"
        level_detail = "O sistema adotou uma resposta conservadora porque não encontrou segurança suficiente."
    normalized = result.get("normalized") or normalize_text(message)
    stopwords = {"onde", "como", "qual", "quais", "para", "isso", "minha", "meu", "uma", "das", "dos", "que", "vejo", "faco", "fazer"}
    signals = [word for word in normalized.split() if len(word) > 3 and word not in stopwords][:6]
    answer_type = answer.get("tipo", "fallback")
    if answer_type == "perfil_sintetico":
        base = "Perfil fictício selecionado"
        safety = "A resposta usa somente os dados sintéticos do perfil vinculado à sessão; nenhum aluno real foi consultado."
    elif intent == "documento_financeiro" or answer.get("encaminhar_humano"):
        base = "Regra de segurança e encaminhamento"
        safety = "O protótipo não acessa contas, documentos, valores ou sistemas internos; por isso, encaminhou para um canal humano quando necessário."
    elif answer_type == "institucional":
        base = "Base institucional controlada"
        safety = "A resposta foi limitada a uma informação institucional cadastrada e acompanhada de fonte quando disponível."
    elif intent in {"financeiro_navegacao", "atividades_complementares"}:
        base = "Orientações da Área do Aluno fornecidas para o protótipo"
        safety = "O sistema orienta a navegação, mas não abre a conta nem confirma dados individuais do aluno."
    else:
        base = "Base controlada de respostas acadêmicas"
        safety = "A resposta foi selecionada de forma controlada; o chatbot não gera fatos fora da base cadastrada."
    return {
        "pergunta": message[:500],
        "texto_normalizado": normalized[:500],
        "intencao": intent,
        "intencao_label": label,
        "sinais": signals,
        "confianca": round(confidence, 4),
        "nivel_confianca": level,
        "nivel_detalhe": level_detail,
        "base_consultada": base,
        "tipo_resposta": answer_type,
        "motivo_decisao": reason,
        "regra_seguranca": safety,
    }


def build_suggestions(message, intent):
    """Retorna atalhos leves para perguntas amplas, sem transformar toda resposta em menu."""
    text = normalize_text(message)
    if intent == "atividades_complementares":
        specific = ("cadastre", "cadastrar", "nova atividade", "visualize", "visualizar", "arquivo", "material", "duvida", "dúvida")
        if not any(term in text for term in specific):
            return [
                {"rotulo": "Consultar dúvidas e materiais", "pergunta": "Onde encontro dúvidas e materiais de atividades complementares?"},
                {"rotulo": "Cadastrar nova atividade", "pergunta": "Como cadastro uma nova atividade complementar?"},
                {"rotulo": "Visualizar minhas atividades", "pergunta": "Como visualizo minhas atividades complementares cadastradas?"},
            ]
    if intent == "financeiro_navegacao" and not any(term in text for term in ("demonstrativo", "desconto", "cartao", "cartão", "boleto", "acordo", "oferta", "condic")):
        return [
            {"rotulo": "Ver demonstrativo", "pergunta": "Onde vejo o demonstrativo financeiro?"},
            {"rotulo": "Consultar pagamentos e acordos", "pergunta": "Onde consulto meus pagamentos e acordos?"},
            {"rotulo": "Ver descontos", "pergunta": "Como funcionam os descontos?"},
        ]
    if intent in {"consulta_nota_perfil", "frequencia"} and not any(term in text for term in ("nota", "falta", "frequencia", "frequência")):
        return [
            {"rotulo": "Consultar notas", "pergunta": "Onde vejo minhas notas?"},
            {"rotulo": "Consultar faltas", "pergunta": "Onde vejo minhas faltas?"},
            {"rotulo": "Consultar histórico", "pergunta": "Onde vejo meu histórico?"},
        ]
    if intent == "rematricula" and text in {"rematricula", "rematricula do aluno", "renovar matricula", "como fazer rematricula"}:
        return [
            {"rotulo": "Fazer rematrícula", "pergunta": "Como faço a rematrícula?"},
            {"rotulo": "Documentos de matrícula", "pergunta": "Onde vejo a lista de documentos de matrícula?"},
            {"rotulo": "Condições especiais", "pergunta": "Onde vejo as condições especiais da rematrícula?"},
        ]
    return []


def register_question_log(message, answer, result, message_id):
    """Registra somente metadados acadêmicos da interação, sem dados sensíveis."""
    entry = {
        "id": message_id,
        "horario": datetime.now(timezone.utc).isoformat(),
        "pergunta": message[:500],
        "resposta": answer.get("resposta", "")[:2000],
        "intencao": result.get("intent", "fallback"),
        "confianca": result.get("confidence", 0),
        "tipo": answer.get("tipo", "fallback"),
        "qa_id": answer.get("qa_id"),
        "qa_numero": answer.get("qa_numero"),
        "similaridade": answer.get("similaridade"),
        "perfil_sintetico": session.get("profile_id"),
    }
    QUESTION_LOG_PATH.parent.mkdir(exist_ok=True)
    with QUESTION_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_question_logs(limit=200):
    if not QUESTION_LOG_PATH.exists():
        return []
    entries = []
    with QUESTION_LOG_PATH.open(encoding="utf-8") as file:
        for line in file:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(entries[-limit:]))


@app.get("/")
def index():
    return render_template("index.html", profiles=DEMO_DATA["perfis"], selected=profile())


@app.get("/fluxograma")
def flowchart():
    return render_template("fluxograma.html")


@app.get("/manus-routes.json")
def routes_manifest():
    return jsonify({"routes": [{"path": "/", "title": "Chatbot TGI II"}, {"path": "/fluxograma", "title": "Como o chatbot funciona"}, {"path": "/admin", "title": "Painel administrativo"}]})


@app.get("/admin")
def admin_panel():
    return render_template("admin.html", authenticated=bool(session.get("admin_authenticated")), has_token=bool(ADMIN_PANEL_TOKEN))


@app.post("/admin/login")
def admin_login():
    data = request.get_json(silent=True) or request.form
    token = str(data.get("token", ""))
    if not ADMIN_PANEL_TOKEN or token != ADMIN_PANEL_TOKEN:
        return jsonify({"erro": "Código de acesso inválido."}), 401
    session["admin_authenticated"] = True
    return jsonify({"ok": True})


@app.post("/admin/logout")
def admin_logout():
    session.pop("admin_authenticated", None)
    return jsonify({"ok": True})


@app.get("/admin/api/logs")
def admin_logs():
    if not session.get("admin_authenticated"):
        return jsonify({"erro": "Acesso administrativo necessário."}), 401
    return jsonify({"registros": read_question_logs(), "total": len(read_question_logs(limit=100000))})


@app.get("/status")
def status():
    return jsonify({"status": "ok", "projeto": "Chatbot TGI II", "modelo": "TF-IDF híbrido + Regressão Logística", "perfis_sinteticos": True})


@app.get("/fontes")
def fontes():
    return jsonify(INSTITUTIONAL)


@app.post("/selecionar-perfil")
def select_profile():
    data = request.get_json(silent=True) or {}
    profile_id = data.get("profile_id")
    if profile_id not in {p["identificador_do_perfil"] for p in DEMO_DATA["perfis"]}:
        return jsonify({"erro": "Perfil de demonstração não encontrado."}), 400
    session.clear()
    session["profile_id"] = profile_id
    selected = profile()
    assert selected is not None
    return jsonify({"ok": True, "perfil": {"id": selected["identificador_do_perfil"], "nome": selected["nome"], "curso": selected["curso"]}})


@app.post("/reiniciar-sessao")
def restart():
    session.clear()
    return jsonify({"ok": True})


@app.post("/chat")
def chat():
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        data = request.form
        attachment = request.files.get("anexo")
    else:
        data = request.get_json(silent=True) or {}
        attachment = None
    message = (data.get("mensagem") or "").strip()
    if not restore_profile_from_request(data):
        return jsonify({"erro": "Escolha um perfil fictício antes de iniciar a conversa."}), 400
    attachment_meta = None
    if attachment and attachment.filename:
        safe_name = secure_filename(attachment.filename)
        extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
        if not safe_name or extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
            return jsonify({"erro": "Anexo não permitido. Use PDF, PNG, JPG, DOC, DOCX, XLS ou XLSX."}), 400
        attachment.seek(0, os.SEEK_END)
        size = attachment.tell()
        attachment.seek(0)
        if size > app.config["MAX_CONTENT_LENGTH"]:
            return jsonify({"erro": "O anexo deve ter no máximo 5 MB."}), 400
        attachment_meta = {"nome": safe_name, "tamanho": size, "tipo": attachment.mimetype or "application/octet-stream", "analisado": False}
    if not message and not attachment_meta:
        return jsonify({"erro": "Digite uma pergunta para continuar."}), 400
    if len(message) > 500:
        return jsonify({"erro": "A pergunta deve ter no máximo 500 caracteres."}), 400
    if attachment_meta and not message:
        return jsonify({"resposta": f"Recebi o anexo {attachment_meta['nome']}. Nesta demonstração, o arquivo não é analisado automaticamente. Escreva sua dúvida e, se necessário, procure a CAA.", "intencao": "anexo_recebido", "confianca": 1.0, "tipo": "anexo", "anexo": attachment_meta, "message_id": str(uuid.uuid4()), "fallback": False, "encaminhar_humano": True})
    result = predict(message)
    override = special_intent(message)
    if override:
        result["intent"] = override
    answer = chat_response(message)
    message_id = str(uuid.uuid4())
    if answer.get("tipo") == "orientacao_revisada":
        result["intent"] = "base_qa_revisada"
        result["confidence"] = answer.get("similaridade", result["confidence"])
    register_question_log(message, answer, result, message_id)
    return jsonify({"resposta": answer["resposta"], "intencao": result["intent"], "confianca": result["confidence"], "tipo": answer.get("tipo"), "fonte": answer.get("fonte"), "url": answer.get("url"), "data_consulta": answer.get("data_consulta"), "qa_id": answer.get("qa_id"), "qa_numero": answer.get("qa_numero"), "similaridade": answer.get("similaridade"), "anexo": attachment_meta, "message_id": message_id, "fallback": answer.get("tipo") == "fallback", "encaminhar_humano": answer.get("encaminhar_humano", False), "pode_confirmar_resolucao": answer.get("tipo") in RESOLUTION_TYPES, "sugestoes": build_suggestions(message, result["intent"]), "explicabilidade": build_explanation(message, result, answer)})


@app.post("/feedback")
def feedback():
    data = request.get_json(silent=True) or {}
    if not restore_profile_from_request(data):
        return jsonify({"erro": "Selecione um perfil antes de avaliar a resposta."}), 400
    rating = data.get("avaliacao")
    if rating not in {"like", "dislike"}:
        return jsonify({"erro": "A avaliação deve ser like ou dislike."}), 400
    FEEDBACK_LOG.append({"message_id": str(data.get("message_id", ""))[:100], "avaliacao": rating, "perfil": session.get("profile_id")})
    return jsonify({"ok": True, "avaliacao": rating})


@app.post("/feedback-resolucao")
def resolution_feedback():
    data = request.get_json(silent=True) or {}
    if not restore_profile_from_request(data):
        return jsonify({"erro": "Selecione um perfil antes de confirmar a resolução."}), 400
    status = data.get("status")
    if status not in {"resolvido", "nao_resolvido"}:
        return jsonify({"erro": "A confirmação deve ser resolvido ou nao_resolvido."}), 400
    motivo = data.get("motivo")
    if motivo and motivo not in RESOLUTION_REASONS:
        return jsonify({"erro": "Motivo de não resolução inválido."}), 400
    intent = str(data.get("intencao", "orientacao"))[:80]
    RESOLUTION_LOG.append({"message_id": str(data.get("message_id", ""))[:100], "status": status, "motivo": motivo, "intencao": intent})
    if status == "resolvido":
        return jsonify({"ok": True, "resposta": "Ótimo! Fico feliz em ajudar. Você pode fazer outra pergunta quando quiser."})
    assunto = INTENT_LABELS.get(intent, "sua dúvida acadêmica")
    if not motivo:
        return jsonify({"ok": True, "precisa_motivo": True, "resposta": "Entendi. O que aconteceu? Escolha uma opção para eu orientar o próximo passo."})
    motivo_texto = RESOLUTION_REASONS[motivo]
    resumo = f"Olá, preciso de ajuda do CAA com {assunto}. O chatbot apresentou uma orientação, mas ainda preciso de auxílio. Situação: {motivo_texto}"
    return jsonify({"ok": True, "resposta": "Entendi. Como não consegui resolver automaticamente, recomendo procurar a CAA online pela Área do Aluno ou a CAA presencial no campus. Preparei um resumo que você pode copiar:", "resumo": resumo, "encaminhar_humano": True})


@app.errorhandler(500)
def server_error(error):
    app.logger.error("erro interno controlado: %s", type(error).__name__)
    return jsonify({"erro": "Ocorreu um erro interno. Tente novamente."}), 500


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(error):
    return jsonify({"erro": "O anexo deve ter no máximo 5 MB."}), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
