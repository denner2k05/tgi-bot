# Chatbot TGI II — relatório final-base

## Resumo

Este projeto apresenta o Chatbot TGI II, um protótipo acadêmico próprio para dúvidas gerais relacionadas ao campus Anália Franco. O sistema combina Processamento de Linguagem Natural, TF-IDF e classificação de intenções com respostas controladas. A aplicação também demonstra consultas individualizadas em dois perfis sintéticos, sem acesso a alunos reais.

## Introdução, problema e justificativa

Estudantes podem ter dificuldade para localizar endereço, horários, canais e orientações acadêmicas. Um chatbot pode organizar perguntas em linguagem natural, desde que diferencie interpretação de consulta factual. A justificativa deste trabalho é demonstrar uma solução explicável, limitada a fontes públicas e transparente sobre seus limites.

O nome e a implementação são próprios. A Duda foi considerada somente como inspiração conceitual de atendimento virtual institucional. Não existe integração com a Duda, com autenticação universitária ou com sistemas internos.

## Objetivos

O objetivo geral é construir um chatbot web que classifique dúvidas, consulte uma base controlada do campus Anália Franco e demonstre dados sintéticos vinculados a um perfil selecionado. Objetivos específicos são implementar o pipeline de PLN, separar as bases, aplicar controle de sessão, exibir fontes, oferecer fallback e preparar testes técnicos e com usuários.

## Fundamentação e método

O PLN converte a pergunta em uma representação tratável. Neste projeto, a normalização remove ruídos e acentos e o TF-IDF atribui peso aos termos e n-gramas. Foram preparados três classificadores para comparação: Regressão Logística, Naive Bayes e SVM. O modelo usado na aplicação é a Regressão Logística por oferecer probabilidades para cálculo de confiança; a comparação pode ser reproduzida com `python evaluate.py`.

## Arquitetura e implementação

A arquitetura e a tabela de arquivos estão em `docs/arquitetura.md`. O frontend chama a API Flask. A camada de interpretação não inventa respostas: ela encaminha intenções para registros institucionais ou para o perfil sintético da sessão. Confiança baixa, pergunta fora do escopo ou informação sem fonte conduzem ao fallback.

## Base institucional

As fontes confirmadas em 06/11/2026 informam o endereço textual Av. Regente Feijó, 1.295, São Paulo/SP, CEP 03342-000; a CAA de segunda a sexta, 8h–21h, e sábado, 11h–15h; o e-mail comercial do CSE Anália Franco; e a existência descrita de laboratórios, clínicas, núcleos, webclass e biblioteca. Horários e canais podem mudar. O mapa não foi usado devido a divergência entre o link e o endereço textual.

## Base fictícia, sessão e privacidade

Lucas Almeida e Mariana Souza são perfis sintéticos com e-mails `example.com`. O perfil de Ciência da Computação também possui uma grade noturna demonstrativa, com aulas fictícias às segundas, quartas e sextas, explicitamente marcada como sintética. A sessão guarda apenas o ID selecionado e a troca exige reinício. Assim, mencionar o ID de outro perfil não autoriza acesso. A aplicação não deve receber dados pessoais reais.

## Testes e resultados

Os testes automatizados cobrem normalização, classificação, fallback, endpoints, seleção e isolamento. `python evaluate.py` separa as frases de forma estratificada, com 50% para teste, porque o conjunto inicial precisa conter ao menos uma frase de cada uma das 22 intenções. Na execução de 06/11/2026, o F1 macro foi 0,223 para Regressão Logística com TF-IDF de palavras, 0,152 para Naive Bayes, 0,315 para SVM e 0,352 para Regressão Logística com TF-IDF híbrido de palavras e caracteres. Esse último foi escolhido para a aplicação por obter o melhor F1 entre as configurações comparadas e oferecer `predict_proba` para o limiar de confiança. A avaliação é técnica e pequena, não substitui uma validação externa nem teste com usuários. Os testes com 30–40 alunos ainda não foram executados neste projeto; portanto, não há resultados de usuários a declarar. O protocolo e o questionário estão em `docs/protocolo_teste.md` e o CSV vazio em `tests/participantes_template.csv`.

As regras controladas também cobrem o período demonstrativo da A1, de 26/11 a 02/12; orientação de dúvidas acadêmicas pela CAA presencial ou por chamado na Área do Aluno; fluxo textual de rematrícula; encaminhamento do calendário ao CAA online ou coordenador; explicação das atividades complementares como exigência do MEC; encaminhamento de documentos e assuntos financeiros ao CAA; pedido de reformulação para perguntas vagas; e apresentação da fonte oficial quando solicitada. Essas respostas são orientações do protótipo e devem ser reconfirmadas nos canais institucionais.

## Limitações, ética e trabalhos futuros

As informações podem mudar e exigem manutenção. O modelo pode errar e perguntas ambíguas exigem reformulação. O chatbot não substitui atendimento humano. A avaliação futura só deve ocorrer com autorização adequada e dados agregados. Trabalhos futuros podem incorporar banco persistente, painel protegido de revisão de fontes, mais exemplos de linguagem e avaliação com amostra autorizada.

## Conclusão

O Chatbot TGI II demonstra uma arquitetura simples e explicável para atendimento acadêmico experimental. O ponto central é separar PLN e conhecimento: o modelo interpreta a pergunta, enquanto bases controladas fornecem os fatos. Essa decisão reduz o risco de respostas inventadas e torna o sistema adequado para discussão acadêmica.

## Referências

1. Universidade Cruzeiro do Sul. [Canais de Atendimento](https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/canais-de-atendimento/).
2. Universidade Cruzeiro do Sul. [Nossas Unidades](https://www.cruzeirodosul.edu.br/a-cruzeiro-do-sul/nossas-unidades/).
3. Pedregosa et al. Scikit-learn: Machine Learning in Python. JMLR, 2011.
