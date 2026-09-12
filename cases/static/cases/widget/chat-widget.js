(function () {
  const script = document.currentScript;
  const apiBase = (script && script.getAttribute("data-api")) || "/api/cases/";
  const storageKey = "tdea_widget_session";

  function api(path, options) {
    return fetch(apiBase.replace(/\/?$/, "/") + path.replace(/^\//, ""), {
      headers: { "Content-Type": "application/json", ...(options && options.headers) },
      ...options,
    }).then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Error de API");
      return data;
    });
  }

  function loadSession() {
    try {
      return JSON.parse(localStorage.getItem(storageKey) || "null");
    } catch (_) {
      return null;
    }
  }

  function saveSession(session) {
    localStorage.setItem(storageKey, JSON.stringify(session));
  }

  const style = document.createElement("link");
  style.rel = "stylesheet";
  const src = script && script.src ? script.src.replace(/[^/]+$/, "chat-widget.css") : "";
  if (src) style.href = src;
  document.head.appendChild(style);

  const launcher = document.createElement("button");
  launcher.className = "tdea-chat-launcher";
  launcher.type = "button";
  launcher.textContent = "Chat Punto TdeA";
  document.body.appendChild(launcher);

  const panel = document.createElement("div");
  panel.className = "tdea-chat-panel";
  panel.innerHTML = `
    <div class="tdea-chat-header">Punto TdeA · Atención</div>
    <div class="tdea-chat-body" id="tdea-chat-body"></div>
    <div id="tdea-chat-stage"></div>
  `;
  document.body.appendChild(panel);

  const bodyEl = panel.querySelector("#tdea-chat-body");
  const stage = panel.querySelector("#tdea-chat-stage");
  let session = loadSession();
  let pollTimer = null;
  let lastMessageId = 0;

  function addBubble(text, mine) {
    const el = document.createElement("div");
    el.className = "tdea-chat-msg" + (mine ? " mine" : "");
    el.textContent = text;
    bodyEl.appendChild(el);
    bodyEl.scrollTop = bodyEl.scrollHeight;
  }

  function renderContactForm() {
    stage.innerHTML = `
      <form class="tdea-chat-form" id="tdea-contact-form">
        <input name="full_name" placeholder="Nombre completo" required>
        <input name="document_number" placeholder="Número de documento" required>
        <input name="email" type="email" placeholder="Correo electrónico" required>
        <input name="phone" placeholder="Teléfono" required>
        <input name="academic_program" placeholder="Programa académico" required>
        <input name="semester" type="number" min="1" max="20" placeholder="Semestre" required>
        <button type="submit">Continuar</button>
      </form>
    `;
    stage.querySelector("form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = e.target;
      const payload = Object.fromEntries(new FormData(form).entries());
      payload.semester = Number(payload.semester);
      try {
        const contact = await api("web/contacts/", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        session = { contactId: contact.id, documentNumber: contact.document_number, conversationId: null };
        saveSession(session);
        renderComposer();
        addBubble("¡Hola! Cuéntanos en qué podemos ayudarte.", false);
      } catch (err) {
        alert(err.message);
      }
    });
  }

  function renderComposer() {
    stage.innerHTML = `
      <form class="tdea-chat-compose" id="tdea-compose-form">
        <input name="body" placeholder="Escribe tu mensaje..." required autocomplete="off">
        <button type="submit">Enviar</button>
      </form>
    `;
    stage.querySelector("form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = e.target.body;
      const body = input.value.trim();
      if (!body) return;
      input.value = "";
      addBubble(body, true);
      try {
        const result = await api("web/messages/", {
          method: "POST",
          body: JSON.stringify({
            contact_id: session.contactId,
            document_number: session.documentNumber,
            body,
          }),
        });
        session.conversationId = result.conversation.id;
        lastMessageId = Math.max(lastMessageId, result.message.id || 0);
        saveSession(session);
        startPolling();
      } catch (err) {
        addBubble("No se pudo enviar. Intenta de nuevo.", false);
      }
    });
    if (session.conversationId) startPolling();
  }

  async function pollMessages() {
    if (!session || !session.conversationId) return;
    try {
      const data = await api(
        `web/conversations/${session.conversationId}/messages/?after_id=${lastMessageId}`
      );
      (data.messages || []).forEach((m) => {
        lastMessageId = Math.max(lastMessageId, m.id);
        if (m.direction === "outbound") addBubble(m.body || m.text, false);
      });
    } catch (_) {
      /* ignore transient poll errors */
    }
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(pollMessages, 3000);
    pollMessages();
  }

  launcher.addEventListener("click", () => {
    panel.classList.toggle("open");
  });

  if (session && session.contactId) {
    renderComposer();
    addBubble("Retomamos tu conversación.", false);
  } else {
    renderContactForm();
  }
})();
