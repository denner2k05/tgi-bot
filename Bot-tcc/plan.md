# Plano — Chatbot TGI II

## Abordagem

O projeto será uma aplicação web acadêmica própria, em Python com Flask, que interpreta perguntas por PLN e responde somente com dados controlados. O frontend será servido pelo Flask e usará HTML, CSS e JavaScript sem dependência de build, facilitando a explicação no TCC e a hospedagem em um container.

A classificação usará pré-processamento em português, TF-IDF e comparação entre Regressão Logística, Naive Bayes e SVM. O modelo final será persistido em `models/` e o treinamento permanecerá reproduzível em `train.py`. A IA não gerará fatos: após classificar a intenção, o backend consulta `institutional_data.json` ou `demo_students.json`.

Sessões de demonstração serão vinculadas a um único `profile_id` armazenado no cookie de sessão do Flask. A seleção inicial é obrigatória, o perfil não pode ser trocado silenciosamente e as consultas individualizadas nunca recebem um identificador fornecido na mensagem.

## Estrutura

- `app.py`: aplicação Flask e rotas principais.
- `nlp/`: normalização, treinamento e previsão de intenções.
- `database/`: base institucional oficial e perfis sintéticos.
- `templates/`, `static/`: interface responsiva.
- `train.py`, `evaluate.py`: reprodução e avaliação técnica.
- `tests/`: testes automatizados de comportamento e API.
- `docs/`: arquitetura, protocolo e relatório final.
- `Dockerfile`, `requirements.txt`, `.env.example`: execução e hospedagem.

## Direção visual escolhida

- **Movimentos considerados:** editorial acadêmico (0,07), dashboard institucional (0,08), minimalismo tecnológico acolhedor (0,06).
- **Movimento escolhido:** minimalismo tecnológico acolhedor.
- **Princípios:** clareza antes de decoração; contraste acessível; hierarquia editorial; feedback visível.
- **Paleta:** azul-petróleo como cor própria e confiável, creme para reduzir sensação clínica, coral para ações e alertas importantes.
- **Layout:** painel lateral de contexto e área de conversa em fluxo vertical, evitando uma tela genérica centralizada.
- **Elementos de assinatura:** monograma “T2”, selo “protótipo acadêmico” e cartões de evidência com fonte/data.
- **Interação:** seleção de perfil explícita, respostas com evidência e fallback sem ambiguidade.
- **Animação:** transições curtas, indicador de processamento discreto, sem movimento ornamental.
- **Tipografia:** Inter para interface e fraunces-like Georgia para títulos, com escala legível.
- **Essência:** um laboratório conversacional para dúvidas acadêmicas simples, transparente sobre seus limites.
- **Voz:** direta, respeitosa e didática. Ex.: “Vamos consultar a fonte cadastrada.” / “Não encontrei confirmação pública para isso.”
- **Marca:** wordmark “Chatbot TGI II” acompanhado de dois blocos verticais que formam o “II”.
