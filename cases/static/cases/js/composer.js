(function () {
  const menu = document.getElementById("clip-menu");
  const toggle = document.getElementById("clip-toggle");
  const dropdown = document.getElementById("clip-dropdown");
  const attachBtn = document.getElementById("clip-attach");
  const fileInput = document.getElementById("attachment-input");
  const previews = document.getElementById("attachment-previews");
  const bodyInput = document.getElementById("reply-body");
  const replyForm = document.getElementById("reply-form");
  const dialog = document.getElementById("template-dialog");
  const openCreate = document.getElementById("clip-create-template");
  const closeCreate = document.getElementById("template-dialog-close");
  const cancelCreate = document.getElementById("template-dialog-cancel");

  if (!toggle || !dropdown) return;

  function closeMenu() {
    dropdown.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
  }

  function openMenu() {
    dropdown.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
  }

  toggle.addEventListener("click", function (event) {
    event.stopPropagation();
    if (dropdown.hidden) openMenu();
    else closeMenu();
  });

  document.addEventListener("click", function (event) {
    if (menu && !menu.contains(event.target)) closeMenu();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeMenu();
      if (dialog && dialog.open) dialog.close();
    }
  });

  if (attachBtn && fileInput) {
    attachBtn.addEventListener("click", function () {
      closeMenu();
      fileInput.click();
    });
  }

  function renderPreviews() {
    if (!previews || !fileInput) return;
    previews.innerHTML = "";
    const files = Array.from(fileInput.files || []);
    if (!files.length) {
      previews.hidden = true;
      return;
    }
    previews.hidden = false;
    files.forEach(function (file, index) {
      const chip = document.createElement("div");
      chip.className = "composer-file-chip";
      chip.innerHTML =
        '<span class="composer-file-name"></span>' +
        '<button type="button" class="composer-file-remove" aria-label="Quitar archivo">&times;</button>';
      chip.querySelector(".composer-file-name").textContent = file.name;
      chip.querySelector(".composer-file-remove").addEventListener("click", function () {
        const dt = new DataTransfer();
        Array.from(fileInput.files).forEach(function (f, i) {
          if (i !== index) dt.items.add(f);
        });
        fileInput.files = dt.files;
        renderPreviews();
      });
      previews.appendChild(chip);
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", renderPreviews);
  }

  const COMPOSER_MAX_LINES = 5;

  function resizeComposer() {
    if (!bodyInput || bodyInput.tagName !== "TEXTAREA") return;
    bodyInput.style.height = "auto";
    const style = window.getComputedStyle(bodyInput);
    const line = parseFloat(style.lineHeight) || 20;
    const pad = (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0);
    const max = line * COMPOSER_MAX_LINES + pad;
    const next = Math.min(bodyInput.scrollHeight, max);
    bodyInput.style.height = next + "px";
    bodyInput.style.overflowY = bodyInput.scrollHeight > max + 1 ? "auto" : "hidden";
  }

  if (bodyInput) {
    bodyInput.addEventListener("input", resizeComposer);
    bodyInput.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
      event.preventDefault();
      if (replyForm && typeof replyForm.requestSubmit === "function") {
        replyForm.requestSubmit();
      }
    });
    resizeComposer();
  }

  document.querySelectorAll(".clip-template").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!bodyInput) return;
      const text = btn.getAttribute("data-template-body") || "";
      bodyInput.value = text;
      bodyInput.focus();
      resizeComposer();
      closeMenu();
    });
  });

  function openDialog() {
    closeMenu();
    if (dialog && typeof dialog.showModal === "function") dialog.showModal();
  }

  function closeDialog() {
    if (dialog && dialog.open) dialog.close();
  }

  if (openCreate) openCreate.addEventListener("click", openDialog);
  if (closeCreate) closeCreate.addEventListener("click", closeDialog);
  if (cancelCreate) cancelCreate.addEventListener("click", closeDialog);

  if (replyForm) {
    replyForm.addEventListener("submit", function (event) {
      const hasText = bodyInput && bodyInput.value.trim().length > 0;
      const hasFiles = fileInput && fileInput.files && fileInput.files.length > 0;
      if (!hasText && !hasFiles) {
        event.preventDefault();
        if (bodyInput) bodyInput.focus();
      }
    });
  }
})();
