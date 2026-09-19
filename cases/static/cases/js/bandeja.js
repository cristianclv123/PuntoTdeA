(function () {
  const list = document.getElementById("conversation-list");
  const searchInput = document.getElementById("wa-search-input");
  if (!list) return;

  const wsUrl = list.dataset.wsUrl;

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function updateCount() {
    const countEl = document.getElementById("result-count");
    if (!countEl) return;
    const visible = list.querySelectorAll(".conversation-row.wa-chat-card:not(.hidden-by-search)").length;
    countEl.textContent = String(visible);
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const q = searchInput.value.trim().toLowerCase();
      list.querySelectorAll(".conversation-row.wa-chat-card").forEach((row) => {
        const hay = (row.dataset.search || row.textContent || "").toLowerCase();
        row.classList.toggle("hidden-by-search", Boolean(q) && !hay.includes(q));
      });
      updateCount();
    });
  }

  if (!wsUrl) return;

  function upsertRow(conv) {
    let row = list.querySelector(`[data-conversation-id="${conv.id}"]`);

    // Casos cerrados salen de la cola
    if (conv.status === "cerrado") {
      if (row) row.remove();
      updateCount();
      return;
    }

    const empty = document.getElementById("empty-bandeja");
    if (empty) empty.remove();

    const badge =
      conv.status_badge ||
      (conv.unassigned ? "Esperando asesor" : (conv.status_label || conv.status || "Pendiente"));
    const tagClass =
      conv.status_tag_class ||
      (conv.unassigned ? "waiting" : (conv.status || "pendiente"));
    const html = `
      <div class="wa-avatar">${escapeHtml(conv.initials || "?")}</div>
      <div class="wa-card-body">
        <div class="wa-card-top">
          <span class="wa-card-name">${escapeHtml(conv.name || "")}</span>
          <span class="wa-card-time">${escapeHtml(conv.time || "")}</span>
        </div>
        <div class="wa-card-preview">${escapeHtml(conv.last_message || "Sin mensajes")}</div>
        <div class="wa-card-bottom">
          <span class="wa-status-tag wa-status-tag--${escapeHtml(tagClass)}">${escapeHtml(badge)}</span>
          <span class="wa-channel-icon ${escapeHtml(conv.channel_class || "")}"></span>
        </div>
      </div>
    `;

    if (!row) {
      row = document.createElement("a");
      row.className = "conversation-row wa-chat-card";
      row.dataset.conversationId = conv.id;
      const fq = list.dataset.filterQuery || "";
      row.href = (conv.detail_url || `/bandeja/${conv.id}/`) + (fq ? `?${fq}` : "");
      list.prepend(row);
    } else {
      list.prepend(row);
    }
    row.dataset.search = `${conv.name || ""} ${conv.phone || ""} ${conv.last_message || ""} ${conv.ticket_number || ""}`;
    row.dataset.assignedToId = conv.assigned_to_id || "";
    row.innerHTML = html;
    updateCount();
  }

  function connect() {
    const socket = new WebSocket(wsUrl);
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
