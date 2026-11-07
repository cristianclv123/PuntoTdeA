(function () {
  const status = document.getElementById("status");
  const group = document.getElementById("escalated-to-group");
  const escalated = document.getElementById("escalated_to");
  if (status && group) {
    function syncEscalation() {
      const show = status.value === "escalado";
      group.hidden = !show;
      group.style.display = show ? "" : "none";
      if (escalated) {
        escalated.required = show;
        if (!show) escalated.value = "";
      }
    }
    status.addEventListener("change", syncEscalation);
    syncEscalation();
  }

  const pane = document.getElementById("wa-chat-pane");
  const toggle = document.getElementById("wa-case-toggle");
  const STORAGE_KEY = "punto-tdea-case-panel";
  if (!pane || !toggle) return;

  function setOpen(open) {
    pane.classList.toggle("case-panel-hidden", !open);
    toggle.setAttribute("aria-pressed", open ? "true" : "false");
    try {
      localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
    } catch (_) {}
  }

  let open = true;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "0") open = false;
  } catch (_) {}
  if (window.innerWidth <= 1100) open = false;
  setOpen(open);

  toggle.addEventListener("click", () => {
    setOpen(pane.classList.contains("case-panel-hidden"));
  });
})();
