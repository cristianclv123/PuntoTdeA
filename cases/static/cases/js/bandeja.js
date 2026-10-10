(function () {
  const list = document.getElementById("conversation-list");
  const searchInput = document.getElementById("wa-search-input");
  if (!list) return;

  const wsUrl = list.dataset.wsUrl;
  const currentUserId = String(list.dataset.currentUserId || "");

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function isViewing(convId) {
    const path = window.location.pathname;
    return path === `/bandeja/${convId}/` || path === `/bandeja/${convId}`;
  }

  function isUnassigned(conv) {
    return Boolean(conv.unassigned) && conv.status !== "cerrado";
  }

  function isMine(conv) {
    return (
      conv.status !== "cerrado" &&
      Boolean(conv.assigned_to_id) &&
      String(conv.assigned_to_id) === currentUserId
    );
  }

  function isUnanswered(conv) {
    return conv.status !== "cerrado" && conv.last_direction === "inbound";
  }

  function matchesTab(conv) {
    const tab = list.dataset.activeTab || "all";
    if (tab === "closed") return conv.status === "cerrado";
    if (conv.status === "cerrado") return false;
    if (tab === "mine") return isMine(conv);
    if (tab === "unassigned") return isUnassigned(conv);
    if (tab === "unanswered") return isUnanswered(conv);
    return true;
  }

  function setChip(id, delta) {
    const el = document.getElementById(id);
    if (!el || !delta) return;
    const next = Math.max(0, (parseInt(el.textContent, 10) || 0) + delta);
    el.textContent = String(next);
    el.hidden = next === 0;
  }

  function rowFlags(row) {
    if (!row) {
      return { unassigned: false, mine: false, unanswered: false, closed: false };
    }
    const status = row.dataset.status || "";
    const assigned = row.dataset.assignedToId || "";
    return {
      unassigned: row.dataset.unassigned === "1" && status !== "cerrado",
      mine: status !== "cerrado" && Boolean(assigned) && assigned === currentUserId,
      unanswered: status !== "cerrado" && row.dataset.lastDirection === "inbound",
      closed: status === "cerrado",
    };
  }

  function applyCountDelta(prev, next) {
    setChip("count-unassigned", Number(next.unassigned) - Number(prev.unassigned));
    setChip("count-mine", Number(next.mine) - Number(prev.mine));
    setChip("count-unanswered", Number(next.unanswered) - Number(prev.unanswered));
    setChip("count-closed", Number(next.closed) - Number(prev.closed));
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
    const prev = rowFlags(row);
    const next = {
      unassigned: isUnassigned(conv),
      mine: isMine(conv),
      unanswered: isUnanswered(conv),
      closed: conv.status === "cerrado",
    };
    applyCountDelta(prev, next);

    if (!matchesTab(conv) && !isViewing(conv.id)) {
      if (row) row.remove();
      updateCount();
      return;
    }

    const empty = document.getElementById("empty-bandeja");
    if (empty) empty.remove();

    const badge =
      conv.status_badge ||
      (conv.unassigned ? "Esperando asesor" : conv.status_label || conv.status || "Pendiente");
    const tagClass =
      conv.status_tag_class || (conv.unassigned ? "waiting" : conv.status || "pendiente");
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
    row.dataset.unassigned = isUnassigned(conv) ? "1" : "0";
    row.dataset.status = conv.status || "";
    row.dataset.lastDirection = conv.last_direction || "";
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
