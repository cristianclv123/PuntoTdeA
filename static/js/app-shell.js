(function () {
  const shell = document.querySelector(".app-shell");
  const toggle = document.getElementById("nav-toggle");
  const closeBtn = document.getElementById("sidebar-close");
  const backdrop = document.getElementById("sidebar-backdrop");
  const collapseBtn = document.getElementById("sidebar-collapse");
  const STORAGE_KEY = "punto-tdea-sidebar-collapsed";

  if (!shell) return;

  function setOpen(open) {
    if (!toggle) return;
    shell.classList.toggle("nav-open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (backdrop) backdrop.hidden = !open;
    document.body.classList.toggle("nav-locked", open);
  }

  function isDesktop() {
    return window.innerWidth > 960;
  }

  function setCollapsed(collapsed) {
    if (!isDesktop()) {
      shell.classList.remove("sidebar-collapsed");
      return;
    }
    shell.classList.toggle("sidebar-collapsed", collapsed);
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
    } catch (_) {
      /* ignore */
    }
    if (collapseBtn) {
      collapseBtn.setAttribute(
        "aria-label",
        collapsed ? "Expandir menú" : "Colapsar menú"
      );
      collapseBtn.setAttribute(
        "title",
        collapsed ? "Expandir menú" : "Colapsar menú"
      );
    }
  }

  function restoreCollapsed() {
    if (!isDesktop()) {
      shell.classList.remove("sidebar-collapsed");
      return;
    }
    let collapsed = false;
    try {
      collapsed = localStorage.getItem(STORAGE_KEY) === "1";
    } catch (_) {
      collapsed = false;
    }
    setCollapsed(collapsed);
  }

  if (toggle) {
    toggle.addEventListener("click", () => {
      setOpen(!shell.classList.contains("nav-open"));
    });
  }
  if (closeBtn) closeBtn.addEventListener("click", () => setOpen(false));
  if (backdrop) backdrop.addEventListener("click", () => setOpen(false));

  if (collapseBtn) {
    collapseBtn.addEventListener("click", () => {
      if (!isDesktop()) return;
      setCollapsed(!shell.classList.contains("sidebar-collapsed"));
    });
  }

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setOpen(false);
  });

  window.addEventListener("resize", () => {
    if (isDesktop()) {
      setOpen(false);
      restoreCollapsed();
    } else {
      shell.classList.remove("sidebar-collapsed");
    }
  });

  restoreCollapsed();
})();
