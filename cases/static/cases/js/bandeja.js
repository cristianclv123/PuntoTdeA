(function () {
  const list = document.getElementById("conversation-list");
  if (!list) return;

  const wsUrl = list.dataset.wsUrl;
  if (!wsUrl) return;

  const statusLabel = {
    pendiente: ["Pendiente", "pill-warning"],
    completado: ["Completado", "pill-success"],
    rechazado: ["Rechazado", "pill-danger"],
    escalado: ["Escalado", "pill-danger"],
    cerrado: ["Cerrado", "pill-neutral"],
  };

  function upsertRow(conv) {
    const empty = document.getElementById("empty-bandeja");
    if (empty) empty.remove();

    let row = list.querySelector(`[data-conversation-id="${conv.id}"]`);
    const [label, pillClass] = statusLabel[conv.status] || statusLabel.pendiente;
    const html = `
      <div class="channel-wrap ${conv.channel_class || ""}"></div>
      <div class="avatar avatar-soft">${conv.initials || "?"}</div>
      <div class="conversation-name-col">
        <div class="conversation-name-row">
          <span class="conversation-name">${conv.name || ""}</span>
          <span class="conversation-role">${conv.role || ""}</span>
        </div>
        <div class="conversation-message">${conv.last_message || ""}</div>
      </div>
      <div class="tag">${conv.theme || "General"}</div>
      <div class="conversation-time">${conv.time || ""}</div>
      <div class="advisor-col"><span>${conv.advisor || "Sin asignar"}</span></div>
      <span class="pill ${pillClass}">${label}</span>
    `;

    if (!row) {
      row = document.createElement("a");
      row.className = "conversation-row";
      row.dataset.conversationId = conv.id;
      row.href = conv.detail_url || `/bandeja/${conv.id}/`;
      list.prepend(row);
      const countEl = document.getElementById("result-count");
      if (countEl) countEl.textContent = String(Number(countEl.textContent || "0") + 1);
    } else {
      list.prepend(row);
    }
    row.innerHTML = html;
  }

  let socket;
  function connect() {
    socket = new WebSocket(wsUrl);
    socket.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === "conversation.upsert" && data.conversation) {
          upsertRow(data.conversation);
        }
      } catch (err) {
        console.warn("bandeja ws parse error", err);
      }
    });
    socket.addEventListener("close", () => {
      setTimeout(connect, 2500);
    });
  }

  connect();
})();
