(function () {
  const shell = document.querySelector(".app-shell");
  const toggle = document.getElementById("nav-toggle");
  const closeBtn = document.getElementById("sidebar-close");
  const backdrop = document.getElementById("sidebar-backdrop");
  if (!shell || !toggle) return;

  function setOpen(open) {
    shell.classList.toggle("nav-open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (backdrop) backdrop.hidden = !open;
    document.body.classList.toggle("nav-locked", open);
  }

  toggle.addEventListener("click", () => {
    setOpen(!shell.classList.contains("nav-open"));
  });
  if (closeBtn) closeBtn.addEventListener("click", () => setOpen(false));
  if (backdrop) backdrop.addEventListener("click", () => setOpen(false));

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setOpen(false);
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 960) setOpen(false);
  });
})();
