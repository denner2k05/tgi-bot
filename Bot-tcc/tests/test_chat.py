import io
import json
import pytest
from app import app
from nlp.preprocess import normalize_text
from nlp.classifier import predict

@pytest.fixture
def client():
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with app.test_client() as client:
        yield client

def select(client, profile_id="TESTE001"):
    return client.post("/selecionar-perfil", json={"profile_id": profile_id})

def test_normalization():
    assert normalize_text("Qual é o horário da CAA?") == "horario caa"

def test_predicts_intent():
    assert predict("onde fica o campus")['intent'] == "endereco_campus"

def test_status_and_sources(client):
    assert client.get("/status").status_code == 200
    assert len(client.get("/fontes").get_json()) >= 3

def test_requires_profile_for_individual(client):
    response = client.post("/chat", json={"mensagem": "qual foi minha nota da A1"})
    assert response.status_code == 400
    assert "Escolha um perfil" in response.get_json()["erro"]

def test_chat_recovers_selected_profile_without_cookie(client):
    response = client.post("/chat", data={"mensagem": "qual foi minha nota da A1", "profile_id": "TESTE001"}, content_type="multipart/form-data")
    assert response.status_code == 200
    assert "Lucas Almeida" in response.get_json()["resposta"]

def test_af_period_without_word_prova(client):
    response = client.post("/chat", json={"mensagem": "qual o período da AF", "profile_id": "TESTE001"})
    assert response.status_code == 200
    assert "10/12 e 16/12" in response.get_json()["resposta"]

def test_low_confidence_is_fallback(client):
    select(client)
    response = client.post("/chat", json={"mensagem": "xyz abacaxi"})
    data = response.get_json()
    assert data["fallback"] is True
    assert data["encaminhar_humano"] is True

def test_profile_isolation(client):
    select(client, "TESTE001")
    response = client.post("/chat", json={"mensagem": "qual é a nota da Mariana Souza"})
    assert response.status_code == 200
    assert "Lucas" in response.get_json()["resposta"] or "selecionado" in response.get_json()["resposta"]
    assert "2.0" not in response.get_json()["resposta"]

def test_selected_profile_data(client):
    select(client, "TESTE002")
    response = client.post("/chat", json={"mensagem": "qual foi minha nota da A1"})
    assert "2.0" in response.get_json()["resposta"]

def test_synthetic_computer_science_schedule(client):
    select(client, "TESTE001")
    response = client.post("/chat", json={"mensagem": "qual minha grade noturna"})
    data = response.get_json()
    assert data["tipo"] == "perfil_sintetico"
    assert "segunda-feira" in data["resposta"]
    assert "quarta-feira" in data["resposta"]
    assert "sexta-feira" in data["resposta"]
    assert "sintéticos" in data["resposta"]

@pytest.mark.parametrize("question, expected", [
    ("qual a data das provas da A1", "26/11"),
    ("onde tiro uma dúvida acadêmica", "CAA"),
    ("como faço a rematrícula", "Rematrícula > Faça Rematrícula"),
    ("onde vejo o calendário acadêmico", "coordenador"),
    ("como funcionam as atividades complementares", "Ministério da Educação"),
    ("preciso resolver um assunto financeiro", "informações financeiras gerais"),
    ("como faço isso", "não entendi"),
    ("qual a fonte dessa resposta", "canais oficiais"),
])
def test_requested_academic_rules(client, question, expected):
    select(client)
    response = client.post("/chat", json={"mensagem": question})
    assert response.status_code == 200
    assert expected in response.get_json()["resposta"]

@pytest.mark.parametrize("question, expected", [
    ("que horas abre a faculdade", "segunda a sexta-feira"),
    ("qual o horário de funcionamento", "11h às 15h"),
    ("qual a data da prova da AF", "10/12"),
    ("me mande a rua da faculdade", "Av. Regente Feijó"),
])
def test_general_hours_af_and_address(client, question, expected):
    select(client)
    response = client.post("/chat", json={"mensagem": question})
    assert response.status_code == 200
    assert expected in response.get_json()["resposta"]


@pytest.mark.parametrize("question, expected", [
    ("quando acaba as aulas", "calendário acadêmico"),
    ("qual a data das provas online", "13/11 e 14/11"),
    ("qual a data da apresentação do TGI", "12/12"),
])
def test_general_academic_dates(client, question, expected):
    select(client)
    response = client.post("/chat", json={"mensagem": question})
    assert response.status_code == 200
    assert expected.lower() in response.get_json()["resposta"].lower()


def test_generic_class_schedule_uses_selected_synthetic_profile(client):
    select(client, "TESTE001")
    response = client.post("/chat", json={"mensagem": "horário de aulas"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["tipo"] == "perfil_sintetico"
    assert "Lucas Almeida" in data["resposta"]
    assert "segunda-feira" in data["resposta"]

@pytest.mark.parametrize("question, expected", [
    ("onde vejo o demonstrativo", "Financeiro > Demonstrativo"),
    ("como funcionam os descontos", "detalhes do boleto"),
    ("como pago com cartão", "Fazer acordo"),
    ("onde consulto meus acordos", "Meus Pagamentos e Acordos"),
])
def test_financial_navigation_guidance(client, question, expected):
    select(client)
    response = client.post("/chat", json={"mensagem": question})
    assert response.status_code == 200
    assert expected in response.get_json()["resposta"]
    assert response.get_json()["encaminhar_humano"] is False

@pytest.mark.parametrize("question", [
    "gere meu boleto",
    "quero emitir uma declaração",
    "qual o valor exato da minha mensalidade",
    "me mande o comprovante de pagamento",
])
def test_financial_documents_and_personal_values_go_to_caa(client, question):
    select(client)
    response = client.post("/chat", json={"mensagem": question})
    data = response.get_json()
    assert response.status_code == 200
    assert "não tenho acesso" in data["resposta"].lower()
    assert data["encaminhar_humano"] is True

def test_flowchart_route(client):
    response = client.get("/fluxograma")
    assert response.status_code == 200
    assert "Como o chatbot transforma" in response.get_data(as_text=True)

def test_routes_manifest_includes_flowchart(client):
    routes = client.get("/manus-routes.json").get_json()["routes"]
    assert any(route["path"] == "/fluxograma" for route in routes)

def test_attachment_and_feedback(client):
    select(client)
    response = client.post("/chat", data={"mensagem": "Envio um documento para demonstração", "anexo": (io.BytesIO(b"pdf-demo"), "comprovante.pdf")}, content_type="multipart/form-data")
    data = response.get_json()
    assert response.status_code == 200
    assert data["anexo"]["nome"] == "comprovante.pdf"
    assert data["anexo"]["analisado"] is False
    feedback = client.post("/feedback", json={"message_id": data["message_id"], "avaliacao": "like"})
    assert feedback.status_code == 200
    assert feedback.get_json()["ok"] is True

def test_resolution_confirmation_and_caa_summary(client):
    select(client)
    response = client.post("/chat", json={"mensagem": "como faço a rematrícula"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["pode_confirmar_resolucao"] is True
    solved = client.post("/feedback-resolucao", json={"message_id": data["message_id"], "intencao": data["intencao"], "status": "resolvido"})
    assert solved.status_code == 200
    assert "feliz em ajudar" in solved.get_json()["resposta"]
    unsolved = client.post("/feedback-resolucao", json={"message_id": data["message_id"], "intencao": data["intencao"], "status": "nao_resolvido"})
    assert unsolved.status_code == 200
    assert unsolved.get_json()["precisa_motivo"] is True
    summary = client.post("/feedback-resolucao", json={"message_id": data["message_id"], "intencao": data["intencao"], "status": "nao_resolvido", "motivo": "pagina_nao_abriu"})
    assert summary.status_code == 200
    assert "resumo" in summary.get_json()
    assert "CAA" in summary.get_json()["resumo"]

def test_explainability_is_specific_to_each_answer(client):
    select(client)
    finance = client.post("/chat", json={"mensagem": "onde vejo o demonstrativo"}).get_json()
    complementares = client.post("/chat", json={"mensagem": "como funcionam as atividades complementares"}).get_json()
    assert finance["explicabilidade"]["intencao"] == "financeiro_navegacao"
    assert "demonstrativo" in finance["explicabilidade"]["sinais"]
    assert complementares["explicabilidade"]["intencao"] == "atividades_complementares"
    assert complementares["explicabilidade"]["pergunta"] != finance["explicabilidade"]["pergunta"]
    assert "Financeiro" in finance["explicabilidade"]["base_consultada"] or "Área do Aluno" in finance["explicabilidade"]["base_consultada"]

def test_broad_questions_return_guided_suggestions(client):
    select(client)
    broad = client.post("/chat", json={"mensagem": "como funcionam as atividades complementares"}).get_json()
    specific = client.post("/chat", json={"mensagem": "como cadastro uma nova atividade complementar"}).get_json()
    assert len(broad["sugestoes"]) == 3
    assert broad["sugestoes"][0]["rotulo"] == "Consultar dúvidas e materiais"
    assert specific["sugestoes"] == []

def test_attachment_extension_is_rejected(client):
    select(client)
    response = client.post("/chat", data={"mensagem": "arquivo", "anexo": (io.BytesIO(b"bad"), "senha.exe")}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert "Anexo não permitido" in response.get_json()["erro"]

def test_feedback_requires_valid_rating(client):
    select(client)
    response = client.post("/feedback", json={"message_id": "x", "avaliacao": "talvez"})
    assert response.status_code == 400

def test_institutional_source(client):
    select(client)
    response = client.post("/chat", json={"mensagem": "qual o endereço do campus"})
    data = response.get_json()
    assert data["tipo"] == "institucional"
    assert data["fonte"]
    assert data["url"].startswith("https://")

def test_empty_and_long_message(client):
    assert client.post("/chat", json={"mensagem": ""}).status_code == 400
    assert client.post("/chat", json={"mensagem": "x" * 501}).status_code == 400

def test_invalid_profile(client):
    assert client.post("/selecionar-perfil", json={"profile_id": "TESTE999"}).status_code == 400

def test_restart(client):
    select(client)
    assert client.post("/reiniciar-sessao").get_json()["ok"] is True


def test_revised_question_base_has_123_entries_and_answers(client):
    with open("database/qa_training.json", encoding="utf-8") as file:
        entries = json.load(file)["entradas"]
    assert len(entries) == 123
    select(client)
    for entry in entries:
        response = client.post("/chat", json={"mensagem": entry["pergunta"]})
        data = response.get_json()
        assert response.status_code == 200
        # Regras institucionais explícitas têm prioridade sobre a recuperação
        # semântica quando a pergunta também contém rematrícula, prova, endereço
        # ou outro assunto controlado.
        assert data["qa_id"] == entry["id"] or data["tipo"] in {"orientacao", "institucional", "encaminhamento", "perfil_sintetico"}
        assert data["resposta"]


def test_admin_panel_requires_login_and_lists_question_answer(client, tmp_path):
    import app as app_module
    original_path = app_module.QUESTION_LOG_PATH
    app_module.QUESTION_LOG_PATH = tmp_path / "question_logs.jsonl"
    try:
        assert client.get("/admin/api/logs").status_code == 401
        select(client)
        response = client.post("/chat", json={"mensagem": "Onde consulto o resultado da minha A1?"})
        assert response.status_code == 200
        login = client.post("/admin/login", json={"token": "admin"})
        assert login.status_code == 200
        logs = client.get("/admin/api/logs")
        assert logs.status_code == 200
        item = logs.get_json()["registros"][0]
        assert item["pergunta"] == "Onde consulto o resultado da minha A1?"
        assert item["resposta"]
        assert "senha" not in item
        assert client.post("/admin/logout").get_json()["ok"] is True
    finally:
        app_module.QUESTION_LOG_PATH = original_path
