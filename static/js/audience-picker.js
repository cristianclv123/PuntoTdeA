/* Selector de audiencia reutilizable (Avisos y Campañas).
 *
 * Reemplaza la carga de archivo "inline" por botones:
 *   - Crear nueva audiencia  -> sube un .xlsx a /segments/import_excel/
 *   - Escoger audiencia      -> lista /segments/
 * y, una vez elegida, muestra un botón "Ver audiencia" con sus contactos.
 *
 * Uso:
 *   <div data-audience-picker data-api-base="/campanas/api" data-input-name="audience"></div>
 *   window.AudiencePicker.mountAll();
 *
 * Los diálogos se agregan a <body> para no anidar <form> dentro del <form>
 * de la página (HTML no permite forms anidados).
 */
(function () {
    "use strict";

    var CONTACT_COLUMNS = [
        ["full_name", "Nombre"],
        ["document_number", "Documento"],
        ["phone", "Teléfono"],
        ["email", "Correo"],
        ["academic_program", "Programa académico"],
        ["semester", "Semestre"],
        ["role", "Perfil"],
        ["whatsapp_opt_in", "Consentimiento WhatsApp"],
        ["source", "Origen del contacto"],
    ];

    var instanceCounter = 0;

    function escapeHtml(value) {
        if (value === undefined || value === null) return "";
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function formatCount(value) {
        var number = Number(value || 0);
        return number.toLocaleString("es-CO");
    }

    function trimBase(base) {
        return String(base || "/campanas/api").replace(/\/+$/, "");
    }

    function getCsrfToken(root) {
        var form = root.closest("form");
        if (form) {
            var input = form.querySelector('input[name="csrfmiddlewaretoken"]');
            if (input && input.value) return input.value;
        }
        var cookies = document.cookie ? document.cookie.split(";") : [];
        for (var i = 0; i < cookies.length; i++) {
            var parts = cookies[i].trim().split("=");
            if (parts[0] === "csrftoken") {
                return decodeURIComponent(parts.slice(1).join("="));
            }
        }
        return "";
    }

    function parseList(data) {
        return Array.isArray(data) ? data : (data.results || []);
    }

    function mount(root, options) {
        if (!root || root.dataset.audiencePickerMounted === "1") {
            return root && root.__audiencePicker;
        }
        options = options || {};
        root.dataset.audiencePickerMounted = "1";

        var apiBase = trimBase(options.apiBase || root.dataset.apiBase);
        var inputName = options.inputName || root.dataset.inputName || "";
        var contextLabel = options.context || root.dataset.context || "audiencia";
        var onChange = typeof options.onChange === "function" ? options.onChange : function () {};
        var instanceId = ++instanceCounter;

        var selected = null; // {id, name, contact_count}
        var contactsNextUrl = null;

        var removeMode = (options.removeMode || root.dataset.removeMode === "true");
        var viewIcon = options.viewIcon || root.dataset.viewIcon || "";
        var viewStyle = options.viewStyle || root.dataset.viewStyle || "";
        var actionsInline = (options.actionsInline || root.dataset.actionsInline === "true");

        root.innerHTML =
            '<div class="ap-actions' + (actionsInline ? " ap-actions-inline" : "") + '">' +
            '<button type="button" class="ap-btn" data-ap-create>' +
            '<span class="ap-btn-icon">+</span> Crear nueva audiencia</button>' +
            '<button type="button" class="ap-btn" data-ap-choose>Seleccionar audiencia</button>' +
            "</div>" +
            '<div class="ap-empty" data-ap-empty>Sin audiencia seleccionada.</div>' +
            '<div class="ap-selection" data-ap-selection hidden>' +
            '<div class="ap-selection-info">' +
            '<span class="ap-selection-label">Audiencia de destino:</span> ' +
            '<span class="ap-selection-name" data-ap-name></span> ' +
            '<span class="ap-selection-count" data-ap-count></span>' +
            "</div>" +
            '<div class="ap-selection-actions">' +
            '<button type="button" class="ap-btn ap-btn-sm' + (viewStyle === "gray" ? " ap-btn-view" : "") + '" data-ap-view>' +
            (viewIcon === "eye"
                ? '<span class="ap-btn-icon ap-btn-icon-svg">' +
                  '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>' +
                  '</span> '
                : (viewIcon ? '<span class="ap-btn-icon">' + escapeHtml(viewIcon) + '</span> ' : "")) +
            'Ver contactos</button>' +
            (removeMode
                ? '<button type="button" class="ap-btn ap-btn-sm ap-btn-view" data-ap-clear aria-label="Retirar audiencia">&times;</button>'
                : '<button type="button" class="ap-btn ap-btn-sm ap-btn-ghost" data-ap-change>Cambiar</button>') +
            "</div>" +
            "</div>" +
            (inputName
                ? '<input type="hidden" name="' + escapeHtml(inputName) + '" data-ap-input value="">'
                : "");

        var emptyEl = root.querySelector("[data-ap-empty]");
        var selectionEl = root.querySelector("[data-ap-selection]");
        var nameEl = root.querySelector("[data-ap-name]");
        var countEl = root.querySelector("[data-ap-count]");
        var inputEl = root.querySelector("[data-ap-input]");

        // --- Diálogos (en <body> para no anidar forms) ---
        var host = document.createElement("div");
        host.className = "ap-dialog-host";
        host.setAttribute("data-ap-host", String(instanceId));
        host.innerHTML =
            '<dialog class="ap-dialog" data-ap-dialog="create">' +
            '<form class="ap-dialog-form" data-ap-create-form novalidate>' +
            '<div class="ap-dialog-head"><h3>Crear nueva audiencia</h3>' +
            '<button type="button" class="ap-dialog-close" data-ap-close aria-label="Cerrar">&times;</button></div>' +
            '<div class="ap-dialog-body">' +
            '<label class="ap-field"><span>Nombre de la audiencia</span>' +
            '<input type="text" name="name" maxlength="150" placeholder="Ej. Estudiantes de Ingeniería" required></label>' +
            '<label class="ap-field"><span>Archivo de destinatarios (.xlsx)</span>' +
            '<input type="file" name="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"></label>' +
            '<p class="ap-hint">Formatos permitidos: .xlsx</p>' +
            '<div class="ap-feedback" data-ap-feedback hidden></div>' +
            "</div>" +
            '<div class="ap-dialog-actions">' +
            '<button type="button" class="ap-btn ap-btn-ghost" data-ap-close>Cancelar</button>' +
            '<button type="submit" class="ap-btn ap-btn-primary" data-ap-submit>Crear y usar</button>' +
            "</div></form></dialog>" +
            '<dialog class="ap-dialog" data-ap-dialog="choose">' +
            '<div class="ap-dialog-form">' +
            '<div class="ap-dialog-head"><h3>Escoger audiencia existente</h3>' +
            '<button type="button" class="ap-dialog-close" data-ap-close aria-label="Cerrar">&times;</button></div>' +
            '<div class="ap-dialog-body">' +
            '<input type="search" class="ap-search" data-ap-search placeholder="Buscar por nombre...">' +
            '<div class="ap-feedback" data-ap-feedback hidden></div>' +
            '<div class="ap-list" data-ap-list></div>' +
            "</div>" +
            '<div class="ap-dialog-actions">' +
            '<button type="button" class="ap-btn ap-btn-ghost" data-ap-close>Cerrar</button>' +
            "</div></div></dialog>" +
            '<dialog class="ap-dialog ap-dialog-wide" data-ap-dialog="view">' +
            '<div class="ap-dialog-form">' +
            '<div class="ap-dialog-head"><h3 data-ap-view-title>Audiencia</h3>' +
            '<button type="button" class="ap-dialog-close" data-ap-close aria-label="Cerrar">&times;</button></div>' +
            '<div class="ap-dialog-body">' +
            '<div class="ap-feedback" data-ap-feedback hidden></div>' +
            '<div class="ap-contacts" data-ap-contacts></div>' +
            '<button type="button" class="ap-btn ap-btn-sm ap-btn-ghost" data-ap-more hidden>Cargar más contactos</button>' +
            "</div>" +
            '<div class="ap-dialog-actions">' +
            '<button type="button" class="ap-btn ap-btn-ghost" data-ap-close>Cerrar</button>' +
            "</div></div></dialog>";
        document.body.appendChild(host);

        var createDialog = host.querySelector('[data-ap-dialog="create"]');
        var chooseDialog = host.querySelector('[data-ap-dialog="choose"]');
        var viewDialog = host.querySelector('[data-ap-dialog="view"]');
        var createForm = host.querySelector("[data-ap-create-form]");
        var createFeedback = createDialog.querySelector("[data-ap-feedback]");
        var chooseFeedback = chooseDialog.querySelector("[data-ap-feedback]");
        var chooseList = host.querySelector("[data-ap-list]");
        var chooseSearch = host.querySelector("[data-ap-search]");
        var viewFeedback = viewDialog.querySelector("[data-ap-feedback]");
        var viewTitle = host.querySelector("[data-ap-view-title]");
        var contactsEl = host.querySelector("[data-ap-contacts]");
        var moreButton = host.querySelector("[data-ap-more]");

        var allSegments = [];
        var creating = false;

        function setFeedback(el, message, kind) {
            if (!el) return;
            if (!message) {
                el.hidden = true;
                el.textContent = "";
                el.classList.remove("is-error", "is-ok");
                return;
            }
            el.hidden = false;
            el.textContent = message;
            el.classList.remove("is-error", "is-ok");
            el.classList.add(kind === "error" ? "is-error" : "is-ok");
        }

        function renderSelection() {
            var actions = root.querySelector(".ap-actions");
            if (!selected) {
                emptyEl.hidden = false;
                selectionEl.hidden = true;
                if (inputEl) inputEl.value = "";
                if (actions) actions.style.display = "";
                onChange(null);
                return;
            }
            emptyEl.hidden = true;
            selectionEl.hidden = false;
            if (actions) actions.style.display = "none";
            nameEl.textContent = selected.name || "";
            countEl.textContent = selected.contact_count !== undefined
                ? "· " + formatCount(selected.contact_count) + " contactos"
                : "";
            if (inputEl) inputEl.value = String(selected.id);
            onChange(selected);
        }

        function select(segment) {
            selected = segment
                ? {
                    id: segment.id,
                    name: segment.name || "",
                    contact_count: segment.contact_count,
                }
                : null;
            renderSelection();
        }

        function openDialog(dialog) {
            if (dialog && typeof dialog.showModal === "function" && !dialog.open) {
                dialog.showModal();
            }
        }

        function closeDialogs() {
            host.querySelectorAll("dialog[open]").forEach(function (dialog) {
                dialog.close();
            });
        }

        host.querySelectorAll("[data-ap-close]").forEach(function (button) {
            button.addEventListener("click", closeDialogs);
        });
        
        // Click directo en botón clear del DOM generado
        root.addEventListener("click", function (e) {
            var btn = e.target.closest("[data-ap-clear]");
            if (btn) {
                e.preventDefault();
                selected = null;
                if (inputEl) inputEl.value = "";
                if (emptyEl) emptyEl.hidden = false;
                if (selectionEl) selectionEl.hidden = true;
                var actionsRoot = root.querySelector(".ap-actions");
                if (actionsRoot) actionsRoot.style.display = "";
                onChange(null);
            }
        });
        host.querySelectorAll("dialog").forEach(function (dialog) {
            dialog.addEventListener("click", function (event) {
                if (event.target === dialog) dialog.close();
            });
        });

        // --- Crear nueva audiencia ---
        root.querySelector("[data-ap-create]").addEventListener("click", function () {
            setFeedback(createFeedback, "");
            createForm.reset();
            openDialog(createDialog);
        });

        createForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            if (creating) return;

            var nameInput = createForm.querySelector('input[name="name"]');
            var fileInput = createForm.querySelector('input[name="file"]');
            var name = (nameInput.value || "").trim();
            var file = fileInput.files && fileInput.files[0];

            if (!name) {
                setFeedback(createFeedback, "Escribe el nombre de la audiencia.", "error");
                return;
            }
            if (!file) {
                setFeedback(createFeedback, "Selecciona un archivo .xlsx.", "error");
                return;
            }
            if (!/\.xlsx$/i.test(file.name)) {
                setFeedback(createFeedback, "El archivo debe tener formato .xlsx.", "error");
                return;
            }

            creating = true;
            var submitButton = createForm.querySelector("[data-ap-submit]");
            submitButton.disabled = true;
            setFeedback(createFeedback, "Importando archivo...", "ok");

            try {
                var formData = new FormData();
                formData.append("name", name);
                formData.append("description", "Creada desde " + contextLabel);
                formData.append("file", file);

                var response = await fetch(apiBase + "/segments/import_excel/", {
                    method: "POST",
                    body: formData,
                    credentials: "same-origin",
                    headers: { "X-CSRFToken": getCsrfToken(root) },
                });

                var data = await response.json().catch(function () {
                    return {};
                });

                if (!response.ok) {
                    var detail = data.detail;
                    if (!detail && data && typeof data === "object") {
                        detail = Object.keys(data)
                            .map(function (field) {
                                var value = data[field];
                                return field + ": " + (Array.isArray(value) ? value.join(" ") : value);
                            })
                            .join(" ");
                    }
                    setFeedback(createFeedback, detail || "No fue posible importar el archivo.", "error");
                    return;
                }

                var segment = data.segment;
                if (!segment || segment.id === undefined || segment.id === null) {
                    setFeedback(createFeedback, "La importación no devolvió la audiencia creada.", "error");
                    return;
                }

                select(segment);
                closeDialogs();
            } catch (error) {
                console.error("Error al importar la audiencia:", error);
                setFeedback(createFeedback, "No se pudo conectar con el servidor.", "error");
            } finally {
                creating = false;
                submitButton.disabled = false;
            }
        });

        // --- Escoger audiencia existente ---
        root.querySelector("[data-ap-choose]").addEventListener("click", function () {
            setFeedback(chooseFeedback, "");
            chooseSearch.value = "";
            openDialog(chooseDialog);
            loadSegments();
        });

        function renderChooseList() {
            var term = (chooseSearch.value || "").trim().toLowerCase();
            var items = allSegments.filter(function (segment) {
                return !term || String(segment.name || "").toLowerCase().indexOf(term) >= 0;
            });

            if (!items.length) {
                chooseList.innerHTML =
                    '<div class="ap-empty-inline">' +
                    (allSegments.length ? "No hay audiencias que coincidan." : "No hay audiencias cargadas.") +
                    "</div>";
                return;
            }

            chooseList.innerHTML = items
                .map(function (segment) {
                    var isCurrent = selected && String(selected.id) === String(segment.id);
                    return (
                        '<button type="button" class="ap-list-item' + (isCurrent ? " is-selected" : "") +
                        '" data-ap-pick="' + escapeHtml(segment.id) + '">' +
                        '<span class="ap-list-name">' + escapeHtml(segment.name) + "</span>" +
                        '<span class="ap-list-count">' + formatCount(segment.contact_count) + " contactos</span>" +
                        "</button>"
                    );
                })
                .join("");
        }

        chooseList.addEventListener("click", function (event) {
            var button = event.target.closest("[data-ap-pick]");
            if (!button) return;
            var id = button.dataset.apPick;
            var segment = allSegments.find(function (item) {
                return String(item.id) === String(id);
            });
            if (!segment) return;
            select(segment);
            closeDialogs();
        });

        chooseSearch.addEventListener("input", renderChooseList);

        async function loadSegments() {
            chooseList.innerHTML =
                '<div class="ap-loading"><span class="ap-spinner"></span> Cargando audiencias...</div>';
            try {
                var response = await fetch(apiBase + "/segments/", {
                    headers: { Accept: "application/json" },
                    credentials: "same-origin",
                });
                if (!response.ok) throw new Error("HTTP " + response.status);
                var data = await response.json();
                allSegments = parseList(data);
                renderChooseList();
            } catch (error) {
                console.error("Error al cargar audiencias:", error);
                setFeedback(chooseFeedback, "No fue posible cargar las audiencias.", "error");
                chooseList.innerHTML = "";
            }
        }

        // --- Ver audiencia (contactos) ---
        root.querySelector("[data-ap-view]").addEventListener("click", async function () {
            if (!selected) return;
            setFeedback(viewFeedback, "");
            viewTitle.textContent = "Audiencia: " + (selected.name || "");
            contactsEl.innerHTML =
                '<div class="ap-loading"><span class="ap-spinner"></span> Cargando contactos...</div>';
            moreButton.hidden = true;
            openDialog(viewDialog);
            await loadContacts(apiBase + "/segments/" + encodeURIComponent(selected.id) + "/contacts/", false);
        });

        async function loadContacts(url, append) {
            if (append) {
                moreButton.disabled = true;
            } else {
                contactsNextUrl = null;
            }
            try {
                var response = await fetch(url, {
                    headers: { Accept: "application/json" },
                    credentials: "same-origin",
                });
                if (!response.ok) throw new Error("HTTP " + response.status);
                var data = await response.json();
                var contacts = parseList(data);
                contactsNextUrl = Array.isArray(data) ? null : data.next;

                if (!contacts.length && !append) {
                    contactsEl.innerHTML = '<div class="ap-empty-inline">Esta audiencia todavía no tiene contactos.</div>';
                    moreButton.hidden = true;
                    return;
                }

                if (!append) {
                    contactsEl.innerHTML = "";
                }
                var table = contactsEl.querySelector("table");
                if (!table) {
                    contactsEl.innerHTML =
                        '<div class="ap-table-scroll"><table class="ap-table"><thead><tr>' +
                        CONTACT_COLUMNS.map(function (column) {
                            return "<th>" + escapeHtml(column[1]) + "</th>";
                        }).join("") +
                        "</tr></thead><tbody data-ap-rows></tbody></table></div>";
                    table = contactsEl.querySelector("table");
                }
                var tbody = contactsEl.querySelector("[data-ap-rows]");
                tbody.insertAdjacentHTML(
                    "beforeend",
                    contacts
                        .map(function (contact) {
                            return (
                                "<tr>" +
                                CONTACT_COLUMNS.map(function (column) {
                                    var value = contact[column[0]];
                                    return "<td>" + escapeHtml(value === undefined || value === null || value === "" ? "—" : value) + "</td>";
                                }).join("") +
                                "</tr>"
                            );
                        })
                        .join("")
                );
                moreButton.hidden = !contactsNextUrl;
            } catch (error) {
                console.error("Error al cargar contactos:", error);
                setFeedback(viewFeedback, "No fue posible cargar los contactos.", "error");
                if (!append) contactsEl.innerHTML = "";
                moreButton.hidden = true;
            } finally {
                moreButton.disabled = false;
            }
        }

        moreButton.addEventListener("click", function () {
            if (contactsNextUrl) loadContacts(contactsNextUrl, true);
        });

        // --- Cambiar ---
        var changeBtn = root.querySelector("[data-ap-change]");
        if (changeBtn) {
            changeBtn.addEventListener("click", function () {
                setFeedback(chooseFeedback, "");
                chooseSearch.value = "";
                openDialog(chooseDialog);
                loadSegments();
            });
        }

        var instance = {
            root: root,
            get: function () {
                return selected;
            },
            select: select,
            clear: function () {
                select(null);
            },
            refreshIfSelected: function () {
                if (selected) renderSelection();
            },
        };

        renderSelection();

        // Selección inicial (id o {id, name, contact_count}).
        if (options.initial) {
            if (typeof options.initial === "object") {
                select(options.initial);
            } else {
                fetch(apiBase + "/segments/" + encodeURIComponent(options.initial) + "/", {
                    headers: { Accept: "application/json" },
                    credentials: "same-origin",
                })
                    .then(function (response) {
                        return response.ok ? response.json() : null;
                    })
                    .then(function (segment) {
                        if (segment && segment.id !== undefined) select(segment);
                    })
                    .catch(function () {});
            }
        }

        root.__audiencePicker = instance;
        return instance;
    }

    function mountAll() {
        var roots = document.querySelectorAll("[data-audience-picker]");
        var instances = [];
        roots.forEach(function (root) {
            instances.push(mount(root));
        });
        return instances;
    }

    window.AudiencePicker = { mount: mount, mountAll: mountAll };
})();
