(function () {
  const area = document.getElementById("message-area");
  if (!area) return;
  const wsUrl = area.dataset.wsUrl;
  if (!wsUrl) return;

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderAttachments(attachments) {
    if (!attachments || !attachments.length) return "";
    const parts = attachments.map(function (att) {
      const name = escapeHtml(att.name || "archivo");
      const url = escapeHtml(att.url || "#");
      if (att.kind === "image") {
        return (
          '<a class="att-preview att-image" href="' +
          url +
          '" target="_blank" rel="noopener">' +
          '<img src="' +
          url +
          '" alt="' +
          name +
          '">' +
          "</a>"
        );
      }
      if (att.kind === "video") {
        return (
          '<video class="att-preview att-video" controls preload="metadata" src="' +
          url +
          '"></video>'
        );
      }
      return (
        '<a class="att-file" href="' +
        url +
        '" target="_blank" rel="noopener" download="' +
        name +
        '">' +
        "<span>" +
        name +
        "</span></a>"
      );
    });
    return '<div class="bubble-attachments">' + parts.join("") + "</div>";
  }

  function appendMessage(message) {
    if (!message || !message.id) return;
    if (area.querySelector(`[data-message-id="${message.id}"]`)) return;

    const text = message.text || message.body || "";
    const row = document.createElement("div");
    row.dataset.messageId = message.id;

    if (message.is_system || message.direction === "system") {
      row.className = "message-row system";
      row.innerHTML =
        '<div class="chat-system-event">' +
        '<span class="chat-system-text">' +
        escapeHtml(text) +
        "</span>" +
        '<span class="chat-system-time">' +
        escapeHtml(message.time || "") +
        "</span>" +
        "</div>";
    } else {
      row.className = "message-row" + (message.from_agent ? " from-agent" : "");
      row.innerHTML =
        '<div class="message-col">' +
        '<div class="bubble">' +
        (message.from_agent ? '<div class="bubble-sender">Asesor</div>' : "") +
        (text ? '<div class="bubble-text">' + escapeHtml(text) + "</div>" : "") +
        renderAttachments(message.attachments) +
        '<div class="bubble-meta"><span class="bubble-time">' +
        escapeHtml(message.time || "") +
        "</span></div>" +
        "</div>" +
        "</div>";
    }
    area.appendChild(row);
    area.scrollTop = area.scrollHeight;
  }

  let socket;
  function connect() {
    socket = new WebSocket(wsUrl);
    socket.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === "message.new" && data.message) {
          appendMessage(data.message);
        }
      } catch (err) {
        console.warn("conversation ws parse error", err);
      }
    });
    socket.addEventListener("close", () => setTimeout(connect, 2500));
  }

  connect();
  area.scrollTop = area.scrollHeight;
})();
