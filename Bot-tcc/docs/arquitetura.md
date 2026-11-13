# Arquitetura do Chatbot TGI II

A aplicação é organizada em quatro camadas. A interface em `templates/index.html` e `static/` conduz a seleção de perfil e apresenta mensagens. O backend Flask em `app.py` valida entradas, mantém a sessão, registra rotas e compõe respostas. O módulo `nlp/` normaliza perguntas, transforma exemplos em TF-IDF e aplica o classificador treinado. As bases JSON são consultadas somente depois da intenção ser identificada.

O fluxo começa na seleção de Lucas Almeida ou Mariana Souza. O endpoint limpa a sessão anterior e grava somente o identificador sintético. Em seguida, `/chat` recebe uma pergunta limitada a 500 caracteres. Intenções institucionais consultam `institutional_data.json`; intenções individuais consultam exclusivamente o perfil cujo ID está na sessão. O ID informado pela interface não é aceito como autorização de consulta.

## Respostas controladas

O classificador interpreta linguagem natural, mas não redige fatos acadêmicos. Para endereço, CAA, canais e infraestrutura, o backend seleciona registros com fonte, URL e data. Para notas, curso, RGM, e-mail e frequência, lê somente o registro sintético da sessão. Sem confirmação ou com baixa confiança, usa fallback.

## Segurança e privacidade

Os perfis são fictícios e o cookie é HTTPOnly. O sistema não solicita senha, CPF, RGM real, documento, nota real ou informação financeira. Logs não registram a mensagem completa. A aplicação deve ser publicada com uma `SECRET_KEY` forte e não deve versionar `.env`.

## Arquivos principais

| Arquivo | Responsabilidade |
|---|---|
| `app.py` | Rotas Flask, sessões, controle de resposta e APIs |
| `nlp/preprocess.py` | Normalização de texto |
| `nlp/classifier.py` | TF-IDF, treinamento e previsão |
| `nlp/intents.py` | Exemplos de treinamento |
| `database/institutional_data.json` | Fonte controlada oficial |
| `database/demo_students.json` | Perfis sintéticos |
| `train.py` | Recriação do modelo |
| `evaluate.py` | Comparação técnica |
| `templates/index.html` | Interface |
| `static/js/app.js` | Interações do chat |
| `static/css/style.css` | Identidade visual e responsividade |
