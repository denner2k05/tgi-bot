const $ = (selector) => document.querySelector(selector);
const profileScreen = $("#profile-screen");
const chatScreen = $("#chat-screen");
const messages = $("#messages");
const typing = $("#typing");
const input = $("#message");
const attachmentInput = $("#attachment");
const attachmentName = $("#attachment-name");
const profileIdInput = $("#profile-id");
let activeProfile = null;
const explainabilityLog = [];

function readSavedProfile() {
  try {
    return localStorage.getItem("chatbot_tgi_profile_id");
  } catch (error) {
    return null;
  }
}

function saveProfile(profileId) {
  try {
    localStorage.setItem("chatbot_tgi_profile_id", profileId);
  } catch (error) {
    // A sessão do servidor continua sendo a fonte principal.
  }
}

function clearSavedProfile() {
  try {
    localStorage.removeItem("chatbot_tgi_profile_id");
  } catch (error) {
    // O armazenamento pode estar bloqueado pelo navegador.
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  }[char]));
}

async function sendFeedback(button, feedback, messageId) {
  const response = await fetch("/feedback", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message_id: messageId, avaliacao: button.dataset.rating, profile_id: activeProfile?.id }) });
  if (response.ok) {
    feedback.querySelectorAll("button").forEach((item) => item.disabled = true);
    button.classList.add("selected");
    feedback.querySelector("span").textContent = "Obrigado pela avaliação.";
  }
}

function bindFeedback(feedback, messageId) {
  if (!feedback) return;
  feedback.querySelectorAll("button[data-rating]").forEach((button) => button.addEventListener("click", () => sendFeedback(button, feedback, messageId)));
}

function addFeedback(article, messageId) {
  if (!messageId) return;
  const feedback = document.createElement("div");
  feedback.className = "feedback-actions";
  feedback.innerHTML = `<span>A resposta foi útil?</span><button type="button" data-rating="like" aria-label="Gostei da resposta">Gostei</button><button type="button" data-rating="dislike" aria-label="Não gostei da resposta">Não gostei</button>`;
  bindFeedback(feedback, messageId);
  article.appendChild(feedback);
}

async function sendResolution(article, actions, messageId, intent, status, motivo = null) {
  const response = await fetch("/feedback-resolucao", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: messageId, intencao: intent, status, motivo, profile_id: activeProfile?.id || readSavedProfile() })
  });
  const data = await response.json();
  if (!response.ok) return alert(data.erro || "Não foi possível registrar a confirmação.");
  actions.querySelectorAll("button").forEach((button) => button.disabled = true);
  if (data.precisa_motivo) {
    actions.innerHTML = `<span>O que aconteceu?</span><div class="resolution-reasons"><button type="button" data-reason="opcao_nao_aparece">A opção não aparece</button><button type="button" data-reason="pagina_nao_abriu">A página não abriu</button><button type="button" data-reason="mensagem_erro">Apareceu um erro</button><button type="button" data-reason="nao_entendi">Ainda não entendi</button><button type="button" data-reason="preciso_pessoa">Preciso falar com uma pessoa</button></div>`;
    actions.querySelectorAll("button[data-reason]").forEach((button) => button.addEventListener("click", () => sendResolution(article, actions, messageId, intent, "nao_resolvido", button.dataset.reason)));
    return;
  }
  actions.innerHTML = `<span>${escapeHtml(data.resposta || "Obrigado pela confirmação.")}</span>`;
  if (data.resumo) {
    const summary = document.createElement("div");
    summary.className = "resolution-summary";
    summary.innerHTML = `<strong>Resumo para o CAA</strong><p>${escapeHtml(data.resumo)}</p><button type="button" class="copy-summary">Copiar resumo</button>`;
    summary.querySelector(".copy-summary").addEventListener("click", async (event) => {
      await navigator.clipboard.writeText(data.resumo);
      event.currentTarget.textContent = "Resumo copiado";
    });
    article.appendChild(summary);
  }
}

function addResolutionActions(article, meta) {
  if (!meta?.pode_confirmar_resolucao || !meta.message_id) return;
  const actions = document.createElement("div");
  actions.className = "resolution-actions";
  actions.innerHTML = `<span>Essa orientação resolveu sua dúvida?</span><button type="button" data-resolution="resolvido">Sim, resolveu</button><button type="button" data-resolution="nao_resolvido">Não, ainda preciso de ajuda</button>`;
  actions.querySelectorAll("button[data-resolution]").forEach((button) => button.addEventListener("click", () => sendResolution(article, actions, meta.message_id, meta.intencao, button.dataset.resolution)));
  article.appendChild(actions);
}

function confidenceLabel(value) {
  return value === "alta" ? "Alta" : value === "média" ? "Média" : "Baixa";
}

function addExplainabilityRecord(meta) {
  if (!meta?.explicabilidade) return;
  explainabilityLog.push(meta.explicabilidade);
  if (explainabilityLog.length > 40) explainabilityLog.shift();
  const count = $("#trace-count");
  if (count) count.textContent = explainabilityLog.length;
  renderExplainability();
}

function renderExplainability() {
  const list = $("#explainability-list");
  if (!list) return;
  if (!explainabilityLog.length) {
    list.innerHTML = '<div class="trace-empty"><span>✦</span><strong>Ainda não há análises</strong><p>Faça uma pergunta para construir o rastro da conversa.</p></div>';
    return;
  }
  list.innerHTML = explainabilityLog.map((item, index) => {
    const percent = Math.round((item.confianca || 0) * 100);
    const signals = item.sinais?.length ? item.sinais.join(", ") : "nenhum sinal textual suficiente";
    return `<details class="trace-card"><summary><span class="trace-index">${String(index + 1).padStart(2, "0")}</span><span class="trace-summary"><strong>${escapeHtml(item.intencao_label)}</strong><small>${escapeHtml(item.pergunta)}</small></span><span class="confidence confidence-${escapeHtml(item.nivel_confianca)}">${confidenceLabel(item.nivel_confianca)} · ${percent}%</span></summary><div class="trace-details"><div class="trace-step"><span>01</span><div><b>Pergunta recebida</b><p>${escapeHtml(item.pergunta)}</p></div></div><div class="trace-step"><span>02</span><div><b>Texto normalizado</b><p>${escapeHtml(item.texto_normalizado || "não disponível")}</p></div></div><div class="trace-step"><span>03</span><div><b>Intenção identificada</b><p>${escapeHtml(item.intencao_label)} · sinais encontrados: <em>${escapeHtml(signals)}</em></p></div></div><div class="trace-step"><span>04</span><div><b>Base consultada</b><p>${escapeHtml(item.base_consultada)}</p></div></div><div class="trace-step trace-decision"><span>05</span><div><b>Por que esta resposta foi escolhida</b><p>${escapeHtml(item.motivo_decisao)} ${escapeHtml(item.nivel_detalhe)}</p></div></div><div class="trace-safety"><b>Regra de segurança</b><p>${escapeHtml(item.regra_seguranca)}</p></div></div></details>`;
  }).join("");
}

function openExplainability() {
  const overlay = $("#explainability-overlay");
  if (!overlay) return;
  renderExplainability();
  overlay.scrollTop = 0;
  const panel = overlay.querySelector(".explainability-panel");
  if (panel) panel.scrollTop = 0;
  overlay.classList.remove("hidden");
  overlay.setAttribute("aria-hidden", "false");
  document.body.classList.add("panel-open");
  requestAnimationFrame(() => {
    if (!panel) return;
    panel.style.scrollBehavior = "auto";
    panel.scrollTo({ top: 0, left: 0, behavior: "auto" });
    requestAnimationFrame(() => panel.scrollTo(0, 0));
  });
}

function closeExplainability() {
  const overlay = $("#explainability-overlay");
  if (!overlay) return;
  overlay.classList.add("hidden");
  overlay.setAttribute("aria-hidden", "true");
  document.body.classList.remove("panel-open");
}

function addSuggestions(article, suggestions) {
  if (!Array.isArray(suggestions) || !suggestions.length) return;
  const box = document.createElement("div");
  box.className = "suggestion-actions";
  box.innerHTML = `<span>Você também pode:</span><div class="suggestion-list">${suggestions.map((item) => `<button type="button" data-prompt="${escapeHtml(item.pergunta)}">${escapeHtml(item.rotulo)}</button>`).join("")}</div>`;
  box.querySelectorAll("button[data-prompt]").forEach((button) => button.addEventListener("click", () => {
    input.value = button.dataset.prompt;
    $("#chat-form").requestSubmit();
  }));
  article.appendChild(box);
}

function addMessage(text, who = "bot", meta = null) {
  const article = document.createElement("article");
  article.className = `message ${who}`;
  article.innerHTML = `${who === "bot" ? '<div class="bot-message-head"><img class="bot-avatar" src="/static/bot-avatar.svg" alt="Avatar do assistente virtual"><span class="message-label">T2 · assistente</span></div>' : ""}<p>${escapeHtml(text)}</p>`;
  if (meta && meta.anexo) {
    const attachment = document.createElement("div");
    attachment.className = "attachment-preview";
    attachment.textContent = `Anexo enviado: ${meta.anexo.nome}`;
    article.appendChild(attachment);
  }
  if (meta && meta.fonte) {
    const evidence = document.createElement("div");
    evidence.className = "evidence";
    evidence.innerHTML = `Fonte: ${escapeHtml(meta.fonte)} · consultado em ${escapeHtml(meta.data_consulta || "data não informada")}<br><a href="${meta.url}" target="_blank" rel="noopener">Abrir fonte oficial ↗</a>`;
    article.appendChild(evidence);
  }
  if (who === "bot" && meta) {
    addFeedback(article, meta.message_id);
    addResolutionActions(article, meta);
    addSuggestions(article, meta.sugestoes);
    addExplainabilityRecord(meta);
  }
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

function renderProfile(profile) {
  $("#selected-profile").innerHTML = `<strong>${escapeHtml(profile.nome)}</strong><small>${escapeHtml(profile.curso)} · ${escapeHtml(profile.id)}</small>`;
}

bindFeedback(document.querySelector(".message.bot .feedback-actions"), "initial-greeting");

$("#open-explainability")?.addEventListener("click", openExplainability);
$("#close-explainability")?.addEventListener("click", closeExplainability);
$("#explainability-overlay")?.addEventListener("click", (event) => {
  if (event.target.id === "explainability-overlay") closeExplainability();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeExplainability();
});

document.querySelectorAll(".profile-card").forEach((card) => card.addEventListener("click", async () => {
  const response = await fetch("/selecionar-perfil", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile_id: card.dataset.profile }) });
  const data = await response.json();
  if (!response.ok) return alert(data.erro);
  activeProfile = data.perfil;
  if (profileIdInput) profileIdInput.value = activeProfile.id;
  saveProfile(activeProfile.id);
  renderProfile(activeProfile);
  profileScreen.classList.add("hidden");
  chatScreen.classList.remove("hidden");
  input.focus();
}));

attachmentInput.addEventListener("change", () => {
  attachmentName.textContent = attachmentInput.files.length ? attachmentInput.files[0].name : "Nenhum anexo selecionado";
});

$("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  const file = attachmentInput.files[0];
  if (!text && !file) return;
  if (file && file.size > 5 * 1024 * 1024) return alert("O anexo deve ter no máximo 5 MB.");
  addMessage(text || "Anexo enviado", "user", file ? { anexo: { nome: file.name } } : null);
  input.value = "";
  typing.classList.remove("hidden");
  const formData = new FormData();
  formData.append("mensagem", text);
  const selectedProfileId = profileIdInput?.value || activeProfile?.id || readSavedProfile();
  if (selectedProfileId) formData.set("profile_id", selectedProfileId);
  if (file) formData.append("anexo", file);
  try {
    const response = await fetch("/chat", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) addMessage(data.erro || "Não foi possível processar a pergunta.");
    else addMessage(data.resposta, "bot", data);
  } finally {
    attachmentInput.value = "";
    attachmentName.textContent = "Nenhum anexo selecionado";
    typing.classList.add("hidden");
    input.focus();
  }
});

$("#clear-chat").addEventListener("click", () => {
  messages.innerHTML = "";
  addMessage("Conversa limpa. O perfil fictício selecionado continua vinculado a esta sessão.", "bot", { message_id: `clear-${Date.now()}` });
});

$("#switch-profile").addEventListener("click", async () => {
  await fetch("/reiniciar-sessao", { method: "POST" });
  clearSavedProfile();
  location.reload();
});
