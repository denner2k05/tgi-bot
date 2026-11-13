# Chatbot TGI II

O Chatbot TGI II é um protótipo acadêmico próprio para o TGI/TCC. Ele auxilia com informações públicas do campus Anália Franco e demonstra consultas em dois perfis fictícios. Não é a Duda, não possui integração com a Duda ou com sistemas internos da Universidade Cruzeiro do Sul e não acessa alunos reais.

## Execução local

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python train.py
python app.py
```

Abra `http://localhost:3000`. Para executar os testes: `pytest -q`. Para comparar os classificadores: `python evaluate.py`.

## Como o sistema responde

O texto passa por normalização, remoção de ruído, tratamento de acentos e vetorização TF-IDF híbrida, com n-gramas de palavras e caracteres. A Regressão Logística classifica a intenção e informa uma confiança. A resposta não é gerada livremente: o backend consulta a base institucional ou o perfil sintético vinculado à sessão. Confiança baixa, ausência de fonte e temas fora do escopo acionam respostas conservadoras.

Dúvidas gerais sobre a área Financeiro recebem instruções de navegação baseadas no material fornecido para a Área do Aluno. Pedidos para gerar ou consultar boleto, declaração, comprovante, valor, dívida, acordo ou qualquer dado financeiro individual continuam sendo encaminhados ao CAA, porque o protótipo não acessa documentos nem contas reais.

O chat também possui um painel único chamado **Rastro da explicabilidade**. Cada resposta acrescenta metadados compactos e específicos da pergunta: texto normalizado, intenção, sinais encontrados, confiança, base consultada, motivo da decisão e regra de segurança. O painel apresenta esses registros em uma linha do tempo com cartões expansíveis, sem repetir um painel pesado dentro de cada mensagem e sem expor o raciocínio interno completo do modelo.

O chat aceita anexos PDF, PNG, JPG, DOC, DOCX, XLS e XLSX de até 5 MB. O arquivo é recebido apenas para demonstração, não é salvo como documento persistente e não é analisado automaticamente. Cada resposta do assistente possui botões “Gostei” e “Não gostei”; a avaliação é enviada de forma anônima junto somente ao identificador da mensagem e ao perfil sintético da sessão.

## Dados e manutenção

`database/institutional_data.json` contém apenas fatos públicos com fonte, URL, data de consulta, confiança e observação. Antes de alterar um item, abra a página oficial, confirme o campus, registre a data de consulta e revise o texto. Não preencha prazos, telefones, horários ou regras sem confirmação. A base `database/demo_students.json` deve continuar sintética e usar apenas `example.com`. O perfil de Ciência da Computação possui uma grade noturna fictícia de demonstração às segundas, quartas e sextas; ela não representa a grade oficial da universidade.

Para adicionar uma intenção, inclua exemplos em `nlp/intents.py`, trate a resposta controlada em `app.py` e, se for institucional, cadastre o registro com a fonte. Depois execute `python train.py` e os testes.

## Hospedagem no Render

1. Crie um repositório no GitHub e envie este projeto.
2. No Render, escolha **New > Web Service**, conecte o repositório e selecione Python/Docker.
3. Com Docker, use o `Dockerfile` já incluído. O serviço deve expor a variável `PORT` fornecida pela plataforma e usar o comando do Dockerfile.
4. Cadastre `SECRET_KEY` como variável secreta no painel. Nunca publique `.env`.
5. Configure a health check path como `/status`; o Dockerfile também declara um healthcheck nativo.
6. Faça o deploy e abra a URL fornecida. Teste seleção de cada perfil, perguntas institucionais, pergunta de nota e tentativa de consultar o outro perfil. `SECRET_KEY` é obrigatória no container de produção.

A persistência atual é propositalmente mínima e adequada à demonstração: o conhecimento e os perfis estão em arquivos versionados e a sessão usa cookie assinado. Se o TCC evoluir para registros de participantes, use banco persistente, anonimização e autorização do professor antes de coletar qualquer dado.

## Testes com pessoas

O sistema inclui `docs/protocolo_teste.md`, `tests/participantes_template.csv` e `docs/relatorio_final.md`. Os resultados com alunos não foram inventados. Antes de testar com pessoas, confirme com o orientador se é necessário termo de consentimento ou autorização institucional.

## Fontes oficiais usadas

- [Canais de Atendimento](https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/)
- [Nossas Unidades](https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/nossas-unidades/)

O mapa da página de canais foi deliberadamente não incluído, pois o link encontrado apresenta divergência no número do endereço. O endereço textual oficial foi priorizado.

## Base ampliada de perguntas acadêmicas

O projeto inclui `database/qa_training.json` com 123 perguntas específicas da Universidade Cruzeiro do Sul/Unicsul que foram revisadas a partir de pesquisa pública e convertidas em respostas profissionais. A aplicação usa `nlp/knowledge_base.py` para normalizar a pergunta, calcular similaridade com TF-IDF de unigramas e bigramas e recuperar a resposta controlada mais próxima quando a similaridade é forte.

A resposta recuperada é identificada pela API com `tipo: orientacao_revisada`, `qa_id`, `qa_numero` e `similaridade`. Isso permite demonstrar na explicabilidade qual registro foi utilizado. A base não consulta sistemas internos, não acessa dados reais e não substitui a confirmação pela Área do Aluno, App Duda, CAA ou coordenação quando a pergunta envolve login, notas, faltas, valores, documentos, prazos, curso, modalidade, campus ou situação individual.

Para atualizar o modelo e validar a cobertura:

```bash
python3 train.py
pytest -q
```

## Painel de registros administrativos

A rota `/admin` permite visualizar as perguntas recebidas e as respostas enviadas pelo chatbot. O painel exige o código definido em `ADMIN_PANEL_TOKEN`; em desenvolvimento local, se a variável não estiver definida, o código demonstrativo é `admin`. Em produção, configure obrigatoriamente um valor longo e aleatório no ambiente do Render e não coloque esse valor no GitHub.

Cada registro salva apenas horário, pergunta, resposta, intenção, confiança, tipo de resposta e identificador do perfil sintético. O sistema não salva senha, CPF, RGM, anexos ou dados financeiros. No protótipo, os registros ficam em `database/question_logs.jsonl`; em hospedagens com armazenamento efêmero, esse arquivo pode ser perdido após reinicialização. Para uma coleta real, é necessário migrar o armazenamento para banco autorizado e aplicar consentimento, anonimização e política de retenção.
