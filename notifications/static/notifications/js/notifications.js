(function () {
  const dock = document.getElementById("notif-dock");
  if (!dock) return;

  const userId = String(dock.dataset.userId || "");
  const listUrl = dock.dataset.listUrl;
  const readAllUrl = dock.dataset.readAllUrl;
  const readTemplate = dock.dataset.readUrlTemplate || "";
  const wsUrl = dock.dataset.wsUrl;
  const toasts = document.getElementById("notif-toasts");
  const panel = document.getElementById("notif-panel");
  const panelList = document.getElementById("notif-panel-list");
  const fab = document.getElementById("notif-fab");
  const fabBadge = document.getElementById("notif-fab-badge");
  const topBell = document.getElementById("notif-top-bell");
  const topBadge = document.getElementById("notif-top-badge");
  const readAllBtn = document.getElementById("notif-read-all");
  const seen = new Set();
  let unread = 0;

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setUnread(count) {
    unread = Math.max(0, count);
    [fabBadge, topBadge].forEach((el) => {
      if (!el) return;
      el.textContent = unread > 99 ? "99+" : String(unread);
      el.hidden = unread === 0;
    });
  }

  function setOpen(open) {
    if (!panel || !fab) return;
    panel.hidden = !open;
    fab.setAttribute("aria-expanded", open ? "true" : "false");
    if (topBell) topBell.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function itemHtml(item) {
    return (
      '<div class="notif-item-kicker">' +
      escapeHtml(item.module_label || item.module || "") +
      (item.time ? " · " + escapeHtml(item.time) : "") +
      "</div>" +
      '<div class="notif-item-title">' +
      escapeHtml(item.title || "") +
      "</div>" +
      (item.body ? '<div class="notif-item-body">' + escapeHtml(item.body) + "</div>" : "")
    );
  }

  function prependPanelItem(item) {
    if (!panelList) return;
    const empty = panelList.querySelector(".notif-empty");
    if (empty) empty.remove();
    let row = panelList.querySelector('[data-notification-id="' + item.id + '"]');
    if (!row) {
      row = document.createElement(item.url ? "a" : "div");
      row.className = "notif-item";
      row.dataset.notificationId = String(item.id);
      if (item.url) row.href = item.url;
      panelList.prepend(row);
    }
    row.classList.toggle("is-unread", Boolean(item.unread));
    row.innerHTML = itemHtml(item);
  }

  function showToast(item) {
    if (!toasts) return;
    if (item.actor_id && String(item.actor_id) === userId) return;
    const toast = document.createElement("button");
    toast.type = "button";
    toast.className = "notif-toast notif-toast--" + (item.level || "info");
    toast.dataset.notificationId = String(item.id);
    toast.innerHTML = itemHtml(item);
    toasts.prepend(toast);
    while (toasts.children.length > 4) {
      toasts.lastElementChild.remove();
    }
    window.setTimeout(() => toast.remove(), 7000);
    toast.addEventListener("click", () => {
      markRead(item.id);
      toast.remove();
      if (item.url) window.location.href = item.url;
    });
  }

  function ingest(item, { toast } = { toast: true }) {
    if (!item || !item.id) return;
    const first = !seen.has(item.id);
    seen.add(item.id);
    prependPanelItem(item);
    if (toast && first && item.unread !== false) {
      showToast(item);
    }
  }

  function markReadUrl(id) {
    return readTemplate.replace(/0\/leer\/?$/, id + "/leer/");
  }

  function markRead(id) {
    if (!id) return Promise.resolve();
    return fetch(markReadUrl(id), {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken() },
      credentials: "same-origin",
    })
      .then((res) => res.json())
      .then((data) => {
        if (typeof data.unread === "number") setUnread(data.unread);
        const row = panelList && panelList.querySelector('[data-notification-id="' + id + '"]');
        if (row) row.classList.remove("is-unread");
      })
      .catch(() => {});
  }

  function loadList() {
    if (!listUrl) return;
    fetch(listUrl, { credentials: "same-origin" })
      .then((res) => res.json())
      .then((data) => {
        setUnread(data.unread || 0);
        (data.results || [])
          .slice()
          .reverse()
          .forEach((item) => ingest(item, { toast: false }));
      })
      .catch(() => {});
  }

  function connect() {
    if (!wsUrl) return;
    const socket = new WebSocket(wsUrl);
    socket.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === "notification.new" && data.notification) {
          const item = data.notification;
          const mine = item.actor_id && String(item.actor_id) === userId;
          if (!mine) setUnread(unread + 1);
          ingest({ ...item, unread: !mine }, { toast: true });
        }
      } catch (err) {
        console.warn("notif ws parse error", err);
      }
    });
    socket.addEventListener("close", () => setTimeout(connect, 2500));
  }

  if (fab) {
    fab.addEventListener("click", () => setOpen(panel.hidden));
  }
  if (topBell) {
    topBell.addEventListener("click", () => setOpen(panel.hidden));
  }
  if (readAllBtn) {
    readAllBtn.addEventListener("click", () => {
      fetch(readAllUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken() },
        credentials: "same-origin",
      })
        .then((res) => res.json())
        .then(() => {
          setUnread(0);
          panelList.querySelectorAll(".notif-item").forEach((row) => row.classList.remove("is-unread"));
        })
        .catch(() => {});
    });
  }
  if (panelList) {
    panelList.addEventListener("click", (event) => {
      const item = event.target.closest("[data-notification-id]");
      if (item) markRead(item.dataset.notificationId);
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setOpen(false);
  });

  loadList();
  connect();
})();
