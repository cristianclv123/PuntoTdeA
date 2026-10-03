const OutboundUI = (() => {

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(';').shift();
        }
        return null;
    }

    const { CHANNELS, SEGMENTS, TEMPLATES, SEED_LOGS, loadCampaigns, saveCampaigns } = window.OutboundDemo;

    function toast(message) {
        const el = document.getElementById('outboundToast');
        const body = document.getElementById('outboundToastBody');
        if (!el || !body) return;
        body.textContent = message;
        bootstrap.Toast.getOrCreateInstance(el).show();
    }

    function pct(part, total) {
        if (!total) return '0%';
        return `${Math.round((part / total) * 100)}%`;
    }

    function channelBadge(channel) {
        const meta = CHANNELS[channel] || { label: channel, icon: 'bi-broadcast' };
        return `<span class="channel-chip"><span class="channel-icon ${channel}"><i class="bi ${meta.icon}"></i></span>${meta.label}</span>`;
    }

    function statusPill(status) {
        return `<span class="status-pill status-${status}">${status}</span>`;
    }

    const CAMPAIGN_STATUS_LABELS = {
        draft: 'Borrador',
        scheduled: 'Programada',
        sending: 'Enviando',
        sent: 'Enviada',
        paused: 'Pausada',
        cancelled: 'Cancelada',
        failed: 'Fallida',
    };

    const CAMPAIGN_STATUS_CLASSES = {
        draft: 'borrador',
        scheduled: 'programada',
        sent: 'enviada',
        cancelled: 'cancelada',
    };

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (character) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;',
        }[character]));
    }

    async function fetchCampaigns() {
        const response = await fetch('/campanas/api/campaigns/', {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });
        if (!response.ok) {
            throw new Error(`No se pudieron cargar las campañas (${response.status}).`);
        }
        const payload = await response.json();
        return Array.isArray(payload) ? payload : (payload.results || []);
    }

    function renderCampaignCard(campaign) {
        const statusLabel = CAMPAIGN_STATUS_LABELS[campaign.status] || campaign.status;
        const statusClass = CAMPAIGN_STATUS_CLASSES[campaign.status] || campaign.status;
        const metadata = [
            campaign.template_name && `Plantilla: ${campaign.template_name}`,
            campaign.segment_name && `Audiencia: ${campaign.segment_name}`,
            campaign.scheduled_at && `Programada: ${campaign.scheduled_at}`,
        ].filter(Boolean).join(' · ');

        return `
            <a class="campaign-item d-block text-decoration-none" href="${campaignUrl(campaign.id)}">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div class="d-flex align-items-center gap-2">
                        <div class="campaign-item-icon">
                            <i class="bi bi-whatsapp text-success fs-5"></i>
                        </div>
                        <div>
                            <h3 class="h6 fw-bold mb-0 text-light">${escapeHtml(campaign.name)}</h3>
                            <span class="small" style="color: var(--text-muted);">${escapeHtml(metadata || 'Sin audiencia o plantilla')}</span>
                        </div>
                    </div>
                    <span class="status-pill status-${escapeHtml(statusClass)}">${escapeHtml(statusLabel)}</span>
                </div>
                ${campaign.sent_count > 0 || campaign.delivered_count > 0 || campaign.read_count > 0 ? `
                    <div class="row text-center g-2 pt-2 mt-2 border-top border-secondary">
                        <div class="col-4">
                            <div class="fw-bold text-light">${Number(campaign.sent_count || 0).toLocaleString('es-CO')}</div>
                            <div class="small" style="color: var(--text-muted); font-size: 0.75rem;">Enviados</div>
                        </div>
                        <div class="col-4">
                            <div class="fw-bold text-light">${Number(campaign.delivered_count || 0).toLocaleString('es-CO')}</div>
                            <div class="small" style="color: var(--text-muted); font-size: 0.75rem;">Entregados</div>
                        </div>
                        <div class="col-4">
                            <div class="fw-bold text-light">${Number(campaign.read_count || 0).toLocaleString('es-CO')}</div>
                            <div class="small" style="color: var(--text-muted); font-size: 0.75rem;">Leídos</div>
                        </div>
                    </div>
                ` : ''}
            </a>
        `;
    }

    async function renderCampaignCards() {
        const list = document.getElementById('campaignsList');
        const empty = document.getElementById('campaignsEmpty');
        const error = document.getElementById('campaignsError');
        const count = document.getElementById('campaignsCount');
        if (!list || !empty || !error || !count) return;

        try {
            const campaigns = await fetchCampaigns();
            count.textContent = `${campaigns.length} campaña${campaigns.length === 1 ? '' : 's'}`;
            list.innerHTML = campaigns.map(renderCampaignCard).join('');
            empty.classList.toggle('d-none', campaigns.length > 0);
        } catch (requestError) {
            list.innerHTML = '';
            count.textContent = 'Error';
            error.textContent = requestError.message;
            error.classList.remove('d-none');
        }
    }

    function campaignUrl(id) {
        return `/campanas/detalle/?id=${encodeURIComponent(id)}`;
    }

    function renderDashboard() {
        const campaigns = loadCampaigns();
        const sent = campaigns.reduce((a, c) => a + (c.sent || 0), 0);
        const delivered = campaigns.reduce((a, c) => a + (c.delivered || 0), 0);
        const read = campaigns.reduce((a, c) => a + (c.read || 0), 0);
        const replies = campaigns.reduce((a, c) => a + (c.replies || 0), 0);
        const kpis = [
            { label: 'Mensajes enviados', value: sent.toLocaleString('es-CO') },
            { label: 'Entregados', value: delivered.toLocaleString('es-CO') },
            { label: 'Tasa de lectura', value: pct(read, delivered) },
            { label: 'Respuestas', value: replies.toLocaleString('es-CO') },
        ];
        document.getElementById('kpiGrid').innerHTML = kpis.map((k) => `
            <div class="col-6 col-lg-3"><div class="kpi-card"><div class="kpi-label">${k.label}</div><div class="kpi-value">${k.value}</div></div></div>
        `).join('');

        document.getElementById('recentCampaignsBody').innerHTML = campaigns.slice(0, 4).map((c) => `
            <tr data-href="${campaignUrl(c.id)}">
                <td class="fw-semibold">${c.name}</td>
                <td>${channelBadge(c.channel)}</td>
                <td>${c.segments.join(', ')}</td>
                <td>${statusPill(c.status)}</td>
                <td>${pct(c.read, c.delivered)}</td>
            </tr>
        `).join('');

        document.getElementById('channelList').innerHTML = Object.entries(CHANNELS).map(([key, meta]) => {
            const count = campaigns.filter((c) => c.channel === key).length;
            return `<div class="channel-row">${channelBadge(key)}<span class="ms-auto small text-muted">${count} campañas</span></div>`;
        }).join('');

        document.getElementById('activityFeed').innerHTML = SEED_LOGS.slice(0, 4).map((log) => `
            <div class="activity-item">
                <span class="channel-icon ${log.channel}"><i class="bi ${CHANNELS[log.channel].icon}"></i></span>
                <div>
                    <div><strong>${log.person}</strong> · ${log.event} en ${log.campaign}</div>
                    <time>${log.at}</time>
                </div>
            </div>
        `).join('');

        bindRowLinks();
    }

    function bindRowLinks(root = document) {
        root.querySelectorAll('tr[data-href]').forEach((row) => {
            row.addEventListener('click', () => { window.location.href = row.dataset.href; });
        });
    }

    function renderCampaignsPage() {
        const search = document.getElementById('filterSearch');
        const channel = document.getElementById('filterChannel');
        const status = document.getElementById('filterStatus');
        const clear = document.getElementById('clearFilters');
        const draw = () => {
            const q = (search.value || '').toLowerCase();
            const list = loadCampaigns().filter((c) => {
                const hay = `${c.name} ${c.segments.join(' ')}`.toLowerCase();
                const okQ = !q || hay.includes(q);
                const okC = !channel.value || c.channel === channel.value;
                const okS = !status.value || c.status === status.value;
                return okQ && okC && okS;
            });
            const body = document.getElementById('campaignsTableBody');
            const empty = document.getElementById('campaignsEmpty');
            body.innerHTML = list.map((c) => `
                <tr data-href="${campaignUrl(c.id)}">
                    <td class="fw-semibold">${c.name}</td>
                    <td>${channelBadge(c.channel)}</td>
                    <td>${c.segments.join(', ')}</td>
                    <td>${c.executedAt}</td>
                    <td>${pct(c.read, c.delivered)}</td>
                    <td>${pct(c.clicks, c.delivered)}</td>
                    <td>${pct(c.replies, c.delivered)}</td>
                    <td>${statusPill(c.status)}</td>
                </tr>
            `).join('');
            empty.classList.toggle('d-none', list.length > 0);
            bindRowLinks();
        };
        [search, channel, status].forEach((el) => el.addEventListener('input', draw));
        clear.addEventListener('click', () => {
            search.value = '';
            channel.value = '';
            status.value = '';
            draw();
        });
        draw();
    }

    async function renderCampaignDetail() {
        const id = new URLSearchParams(window.location.search).get('id');
        const root = document.getElementById('campaignDetailRoot');

        if (!root) {
            console.error('No se encontró campaignDetailRoot.');
            return;
        }

        if (!id) {
            root.innerHTML = '<div class="alert alert-warning">No se especificó una campaña.</div>';
            return;
        }

        let campaign = null;

        /*
         * 1. Primero intentamos obtener la campaña desde Django.
         */
        try {
            const response = await fetch(`/campanas/api/campaigns/${id}/`);

            if (response.ok) {
                const data = await response.json();

                /*
                 * Adaptamos los nombres del backend al formato
                 * que ya utiliza el frontend.
                 */
                campaign = {
                    id: String(data.id),
                    name: data.name,
                    channel: data.channel,
                    template: data.template,
                    templateName: data.template_name || 'Sin plantilla',
                    defaultParams: data.default_params || {},

                    segments: data.segment
                        ? [data.segment_name || data.segment]
                        : [],

                    totalRecipients: data.total_recipients ?? 0,
                    sent: data.sent_count ?? 0,
                    delivered: data.delivered_count ?? 0,
                    read: data.read_count ?? 0,
                    failed: data.failed_count ?? 0,

                    executedAt: data.scheduled_at || '-',
                    type: data.type || 'Campaña',

                    status: data.status,

                    // Todavía no existen estos indicadores en CampaignSerializer.
                    clicks: 0,
                    replies: 0
                };
                console.log('Campaña cargada desde Django:', campaign);
            }
        } catch (error) {
            console.warn('No fue posible consultar la campaña en Django:', error);
        }

        /*
         * 2. Si no se encontró en el backend, conservamos
         *    el funcionamiento anterior con loadCampaigns().
         */
        if (!campaign) {
            campaign = loadCampaigns().find((c) => String(c.id) === String(id));
        }

        /*
         * 3. Si tampoco existe localmente, mostramos el mensaje anterior.
         */
        if (!campaign) {
            root.innerHTML = '<div class="alert alert-warning">No se encontró la campaña. Vuelve al listado.</div>';
            return;
        }

        /*
         * 4. Desde aquí mantenemos prácticamente intacta
         *    la lógica visual que ya tenías.
         */
        let tpl = null;
        try {
            const templatesResponse = await fetch('/campanas/api/templates/', {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
            });
            if (!templatesResponse.ok) {
                throw new Error(`No se pudieron cargar las plantillas (${templatesResponse.status}).`);
            }
            const templatesData = await templatesResponse.json();
            const templates = Array.isArray(templatesData) ? templatesData : templatesData.results;
            if (!Array.isArray(templates)) {
                throw new Error('La respuesta de plantillas no tiene un formato válido.');
            }
            const selectedTemplate = templates.find(
                (template) => String(template.id) === String(campaign.template)
            );
            if (selectedTemplate) {
                tpl = {
                    ...selectedTemplate,
                    body: selectedTemplate.body_text || '',
                    buttons: Array.isArray(selectedTemplate.buttons) ? selectedTemplate.buttons : [],
                };
            }
        } catch (error) {
            console.warn('No fue posible cargar la plantilla de la campaña:', error);
        }

        root.innerHTML = `
        <div class="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-4">
            <div>
                <h2 class="h4 mb-1">${campaign.name}</h2>
                <div class="d-flex flex-wrap gap-2">
                    ${channelBadge(campaign.channel)}
                    ${statusPill(campaign.status)}
                </div>
            </div>
        </div>

        <div class="row g-3 mb-4">
            ${[
                ['Enviados', campaign.sent],
                ['Entregados', campaign.delivered],
                ['Lectura', pct(campaign.read, campaign.delivered)],
                ['Clics', pct(campaign.clicks, campaign.delivered)],
                ['Respuestas', campaign.replies],
            ].map(([label, value]) => `
                <div class="col">
                    <div class="kpi-card">
                        <div class="kpi-label">${label}</div>
                        <div class="kpi-value">${value}</div>
                    </div>
                </div>
            `).join('')}
        </div>

        <div class="row g-4">
            <div class="col-lg-7">
                <div class="card outbound-card">
                    <div class="card-body">
                        <h3 class="h6">Audiencias</h3>
                        <p class="mb-1">${campaign.segments.join(', ') || 'Sin audiencia'}</p>
                        <p class="small text-muted mb-3">
                            ${campaign.totalRecipients.toLocaleString('es-CO')} destinatarios
                        </p>
                                                

                        <h3 class="h6">Ejecución</h3>
                        <p class="mb-0">
                            ${campaign.executedAt} · tipo ${campaign.type}
                        </p>
                    </div>
                </div>
            </div>

            <div class="col-lg-5">
                <div class="card outbound-card">
                    <div class="card-body">
                        <h3 class="h6 text-uppercase text-muted">
                              Plantilla
                        </h3>
                        <p class="fw-semibold mb-3">
                            ${campaign.templateName}
                        </p>

                    <div class="phone-frame">
                            <div class="phone-screen">
                                ${previewHtml(campaign.channel, tpl, campaign.defaultParams)}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    }

    function previewHtml(channel, tpl, vars = {}) {
        if (!tpl) return '<p class="small text-muted">Sin plantilla.</p>';
        let body = tpl.body;
        Object.entries(vars).forEach(([k, v]) => {
            body = body.replaceAll(`{{${k}}}`, v || `{{${k}}}`);
        });
        const buttons = (tpl.buttons || []).map((b) => `<span>${b}</span>`).join('');
        if (channel === 'whatsapp') {
            return `<div class="wa-bubble">${body}<span class="wa-meta">TdeA · ahora</span></div>${buttons ? `<div class="wa-buttons">${buttons}</div>` : ''}`;
        }
        return `<div class="wa-bubble" style="background:#fff">${body}</div>`;
    }

    function extractVars(body) {
        return [...body.matchAll(/\{\{([^}]+)\}\}/g)].map((m) => m[1]);
    }

    function initWizard() {
        let templates = [];
        let segments = [];
        const state = {
            step: 1,
            channel: 'whatsapp',
            include: [],
            exclude: [],
            templateId: '',
            vars: {},
        };

        const loadRecipientsFileBtn = document.getElementById('loadRecipientsFileBtn');
        const recipientsFileInput = document.getElementById('recipientsFileInput');
        const selectedRecipientsFileName = document.getElementById('selectedRecipientsFileName');
        let selectedRecipientsFile = null;
        let importingRecipients = false;
        if (loadRecipientsFileBtn && recipientsFileInput && selectedRecipientsFileName) {
            loadRecipientsFileBtn.addEventListener('click', () => recipientsFileInput.click());
            recipientsFileInput.addEventListener('change', () => {
                const file = recipientsFileInput.files && recipientsFileInput.files[0];
                if (!file) return;

                if (!file.name.toLowerCase().endsWith('.xlsx')) {
                    toast('Selecciona un archivo con formato .xlsx.');
                    return;
                }

                selectedRecipientsFile = file;
                selectedRecipientsFileName.textContent = `Archivo seleccionado: ${file.name}`;
                selectedRecipientsFileName.classList.remove('d-none');
            });
        }

        async function loadSegments() {
            try {
                const response = await fetch('/campanas/api/segments/');

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const data = await response.json();

                segments = Array.isArray(data)
                    ? data
                    : (data.results || []);

                renderSegments();
                return true;
            } catch (error) {
                console.error('Error cargando audiencias:', error);
                toast('No se pudieron cargar las audiencias.');
                return false;
            }
        }

        const picker = document.getElementById('channelPicker');
        picker.innerHTML = Object.entries(CHANNELS).map(([key, meta]) => `
            <button type="button" class="channel-option ${key === state.channel ? 'is-selected' : ''}" data-channel="${key}">
                <span class="channel-icon ${key} mx-auto mb-2"><i class="bi ${meta.icon}"></i></span>
                <div class="fw-semibold">${meta.label}</div>
            </button>
        `).join('');

        const includeBox = document.getElementById('includeSegments');
        const excludeBox = document.getElementById('excludeSegments');

        function chip(s, kind) {
            return `<button type="button" class="segment-chip" data-kind="${kind}" data-id="${s.id}">
        ${s.name} · ${(s.contact_count || 0).toLocaleString('es-CO')}
    </button>`;
        }

        function renderSegments() {
            includeBox.innerHTML = segments
                .map((s) => chip(s, 'include'))
                .join('');

            excludeBox.innerHTML = segments
                .map((s) => chip(s, 'exclude'))
                .join('');

            document.querySelectorAll('.segment-chip').forEach((btn) => {
                const id = Number(btn.dataset.id);
                const selectedSegments = btn.dataset.kind === 'include' ? state.include : state.exclude;
                btn.classList.toggle('is-selected', selectedSegments.includes(id));
                btn.addEventListener('click', () => {
                    const kind = btn.dataset.kind;
                    const list = kind === 'include' ? state.include : state.exclude;
                    const idx = list.indexOf(id);

                    if (idx >= 0) {
                        list.splice(idx, 1);
                    } else if (kind === 'include' && list.length >= 5) {
                        toast('Puedes incluir hasta 5 audiencias.');
                        return;
                    } else {
                        list.push(id);
                    }

                    btn.classList.toggle('is-selected');
                });
            });
        }

        function fillAccounts() {
            document.getElementById('senderAccount').innerHTML =
                `<option>${CHANNELS[state.channel].account}</option>`;
        }

        fillAccounts();
        loadSegments();

        picker.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-channel]');
            if (!btn) return;
            state.channel = btn.dataset.channel;
            state.templateId = '';
            picker.querySelectorAll('.channel-option').forEach((el) => el.classList.toggle('is-selected', el === btn));
            fillAccounts();
            renderTemplates();
            updatePreview();
        });

        function renderTemplates() {
            const grid = document.getElementById('templateGrid');
            const list = templates;
            grid.innerHTML = list.map((t) => `
                <button type="button" class="template-card ${String(t.id) === state.templateId ? 'is-selected' : ''}" data-tpl="${t.id}">
                    <div class="small text-muted mb-1">${t.type}</div>
                    <div class="fw-semibold">${t.name}</div>
                    <p class="small mb-0 mt-2 text-muted">${t.body}</p>
                </button>
            `).join('');
        }

        async function loadTemplates() {
            try {
                const response = await fetch('/campanas/api/templates/', {
                    headers: { Accept: 'application/json' },
                    credentials: 'same-origin',
                });
                if (!response.ok) {
                    throw new Error(`No se pudieron cargar las plantillas (${response.status}).`);
                }
                const data = await response.json();
                const results = Array.isArray(data) ? data : data.results;
                if (!Array.isArray(results)) {
                    throw new Error('La respuesta de plantillas no tiene un formato válido.');
                }
                templates = results.map((template) => ({
                    ...template,
                    type: template.category,
                    body: template.body_text || '',
                }));
                renderTemplates();
            } catch (error) {
                templates = [];
                renderTemplates();
                console.error('Error al cargar plantillas:', error);
                toast('No fue posible cargar las plantillas.');
            }
        }

        loadTemplates();

        document.getElementById('templateGrid').addEventListener('click', (e) => {
            const card = e.target.closest('[data-tpl]');
            if (!card) return;
            const tpl = templates.find((template) => String(template.id) === card.dataset.tpl);
            if (!tpl) return;
            state.templateId = String(tpl.id);
            document.querySelectorAll('.template-card').forEach((el) => el.classList.toggle('is-selected', el === card));
            const vars = extractVars(tpl.body);
            const editor = document.getElementById('variableEditor');
            const fields = document.getElementById('variableFields');
            if (!vars.length) {
                editor.classList.add('d-none');
                state.vars = {};
            } else {
                editor.classList.remove('d-none');
                state.vars = Object.fromEntries(vars.map((v) => [v, state.vars[v] || '']));
                fields.innerHTML = vars.map((v) => `
                    <label class="form-label small mt-2">${v}</label>
                    <input class="form-control var-input" data-var="${v}" value="${state.vars[v] || ''}" placeholder="${v}">
                `).join('');
            }
            updatePreview();
        });

        document.getElementById('variableFields').addEventListener('input', (e) => {
            if (!e.target.classList.contains('var-input')) return;
            state.vars[e.target.dataset.var] = e.target.value;
            updatePreview();
        });

        document.getElementById('sendMode').addEventListener('change', (e) => {
            document.getElementById('scheduleAt').disabled = e.target.value !== 'later';
        });

        function currentTpl() {
            return templates.find((t) => String(t.id) === state.templateId);
        }

        function updatePreview() {
            document.getElementById('messagePreview').innerHTML = previewHtml(state.channel, currentTpl(), state.vars);
        }

        function showStep(n) {
            state.step = n;
            document.querySelectorAll('.wizard-pane').forEach((p) => p.classList.toggle('d-none', Number(p.dataset.pane) !== n));
            document.querySelectorAll('.wizard-step').forEach((s) => {
                const step = Number(s.dataset.step);
                s.classList.toggle('is-active', step === n);
                s.classList.toggle('is-done', step < n);
            });
            document.getElementById('wizardBack').disabled = n === 1;
            document.getElementById('wizardNext').textContent = n === 3 ? 'Lanzar campaña' : 'Continuar';
            document.getElementById('wizardTest').classList.toggle('d-none', n !== 3);
            if (n === 2) renderTemplates();
            if (n === 3) fillReview();
            updatePreview();
        }

        function fillReview() {
            const name = document.getElementById('campaignName').value || 'Sin nombre';
            const type = document.getElementById('campaignType').value;
            const tpl = currentTpl();

            const includeNames = segments
                .filter((s) => state.include.includes(Number(s.id)))
                .map((s) => s.name);

            const excludeNames = segments
                .filter((s) => state.exclude.includes(Number(s.id)))
                .map((s) => s.name);

            const size = segments
                .filter((s) => state.include.includes(Number(s.id)))
                .reduce((total, s) => total + Number(s.contact_count || 0), 0);

            document.getElementById('reviewList').innerHTML = `
                <dt class="col-sm-4">Nombre</dt>
                <dd class="col-sm-8">${name}</dd>

                <dt class="col-sm-4">Canal</dt>
                <dd class="col-sm-8">${CHANNELS[state.channel].label}</dd>

                <dt class="col-sm-4">Tipo</dt>
                <dd class="col-sm-8">${type}</dd>

                <dt class="col-sm-4">Audiencias</dt>
                <dd class="col-sm-8">${includeNames.join(', ') || 'Ninguna'}</dd>

                <dt class="col-sm-4">Excluir</dt>
                <dd class="col-sm-8">${excludeNames.join(', ') || 'Ninguna'}</dd>

                <dt class="col-sm-4">Plantilla</dt>
                <dd class="col-sm-8">${tpl ? tpl.name : 'Sin seleccionar'}</dd>
                `;

            document.getElementById('costEstimate').textContent =
                `Audiencia estimada: ${size.toLocaleString('es-CO')} destinatarios.`;
        }

        function getCookie(name) {
            const cookies = document.cookie ? document.cookie.split(';') : [];

            for (const cookie of cookies) {
                const [key, ...valueParts] = cookie.trim().split('=');

                if (key === name) {
                    return decodeURIComponent(valueParts.join('='));
                }
            }

            return '';
        }

        async function importRecipientsFile(nextButton) {
            if (importingRecipients) return;

            importingRecipients = true;
            nextButton.disabled = true;
            toast('Importando archivo...');

            try {
                const segmentNameInput = document.getElementById('segmentName');
                const segmentName = segmentNameInput
                    ? segmentNameInput.value.trim()
                    : '';

                if (!segmentName) {
                    toast('Escribe el nombre de la audiencia.');
                    return false;
                }

                const formData = new FormData();
                formData.append('name', segmentName);
                formData.append('description', 'Importada desde campaña');
                formData.append('file', selectedRecipientsFile);

                const response = await fetch('/campanas/api/segments/import_excel/', {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });

                if (!response.ok) {
                    let backendError;

                    try {
                        backendError = await response.json();
                    } catch (error) {
                        backendError = {
                            detail: 'El servidor rechazó la importación.',
                        };
                    }

                    console.error('Error al importar archivo:', backendError);

                    const message = backendError.detail
                        || Object.entries(backendError)
                            .map(([field, messages]) =>
                                `${field}: ${Array.isArray(messages)
                                    ? messages.join(' ')
                                    : messages}`
                            )
                            .join(' ');

                    toast(message || 'No fue posible importar el archivo.');
                    return false;
                }

                const data = await response.json();
                const segment = data.segment;

                if (!segment || segment.id === undefined || segment.id === null) {
                    console.error('Respuesta de importación sin segmento:', data);
                    toast(
                        'La importación respondió correctamente, pero no se recibió la audiencia creada.'
                    );
                    return false;
                }

                const segmentsLoaded = await loadSegments();
                const segmentId = Number(segment.id);

                if (!segments.some((item) => Number(item.id) === segmentId)) {
                    segments.push(segment);
                }

                let audienceLimitReached = false;

                if (!state.include.includes(segmentId)) {
                    if (state.include.length < 5) {
                        state.include.push(segmentId);
                    } else {
                        audienceLimitReached = true;
                    }
                }

                renderSegments();

                const summary =
                    `Importación completada: ${data.created || 0} creados, ` +
                    `${data.updated || 0} actualizados y ` +
                    `${data.skipped || 0} omitidos.`;

                const reloadWarning = segmentsLoaded
                    ? ''
                    : ' No se pudo recargar la lista; la audiencia importada se conservó en ella.';

                toast(
                    `${summary}` +
                    `${audienceLimitReached
                        ? ' Se alcanzó el máximo de 5 audiencias; la nueva audiencia quedó en la lista, pero no se seleccionó.'
                        : ''}` +
                    `${reloadWarning}`
                );

                showStep(2);
                return true;

            } catch (error) {
                console.error('Error al importar archivo:', error);
                toast(
                    'No se pudo importar el archivo. Verifica la conexión con el servidor.'
                );
                return false;

            } finally {
                importingRecipients = false;
                nextButton.disabled = false;
            }
        }

        document.getElementById('wizardBack').addEventListener('click', () => showStep(Math.max(1, state.step - 1)));
        document.getElementById('wizardNext').addEventListener('click', async (event) => {
            if (importingRecipients) return;
            if (state.step === 1) {
                if (!document.getElementById('campaignName').value.trim()) {
                    return toast('Escribe un nombre de campaña.');
                }

                if (!state.include.length && !selectedRecipientsFile) {
                    return toast('Selecciona una audiencia o carga un archivo .xlsx.');
                }

                if (selectedRecipientsFile) {
                    return importRecipientsFile(event.currentTarget);
                }

                return showStep(2);
            }
            if (state.step === 2) {
                if (!state.templateId) return toast('Selecciona una plantilla.');
                return showStep(3);
            }
            launch();
        });
        document.getElementById('wizardTest').addEventListener('click', () => toast('Prueba enviada a la cuenta institucional de demostración.'));
        document.querySelectorAll('.wizard-step').forEach((btn) => {
            btn.addEventListener('click', () => showStep(Number(btn.dataset.step)));
        });

        async function launch() {
            const sendMode = document.getElementById('sendMode').value;
            const scheduleAt = document.getElementById('scheduleAt').value;

            const name = document.getElementById('campaignName').value.trim();

            if (!state.include.length) {
                toast('Selecciona al menos una audiencia.');
                return;
            }

            if (!state.templateId || !Number.isInteger(Number(state.templateId))) {
                toast('La plantilla seleccionada no está disponible en el backend.');
                return;
            }

            try {
                const payload = {
                    name: name,
                    template: Number(state.templateId),
                    segment: state.include[0],
                    default_params: state.vars,
                };

                if (sendMode === 'later' && scheduleAt) {
                    payload.scheduled_at = scheduleAt;
                }

                const response = await fetch('/campanas/api/campaigns/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(payload),
                });

                if (!response.ok) {
                    const error = await response.json();
                    console.error('Error al crear campaña:', error);
                    toast('No se pudo crear la campaña en el backend.');
                    return;
                }

                const backendCampaign = await response.json();

                toast('Campaña creada correctamente en el backend.');

                window.location.href = `/campanas/detalle/?id=${encodeURIComponent(backendCampaign.id)}`;

            } catch (error) {
                console.error('Error de conexión:', error);
                toast('No se pudo conectar con el backend.');
            }
        }

        showStep(1);
    }

    function initTemplatesPage() {
        const newTemplateBtn = document.getElementById('newTemplateBtn');
        const templateList = document.getElementById('templateList');
        if (!newTemplateBtn || !templateList) return;

        const modalId = 'createTemplateModal';
        if (!document.getElementById(modalId)) {
            document.body.insertAdjacentHTML('beforeend', `
                <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="createTemplateModalLabel" aria-hidden="true">
                    <div class="modal-dialog modal-lg modal-dialog-centered">
                        <div class="modal-content">
                            <form id="createTemplateForm">
                                <div class="modal-header">
                                    <h2 class="modal-title fs-5" id="createTemplateModalLabel">Nueva plantilla</h2>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>
                                </div>
                                <div class="modal-body">
                                    <div id="createTemplateError" class="alert alert-danger d-none" role="alert"></div>
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <label for="templateName" class="form-label">Nombre interno</label>
                                            <input id="templateName" name="name" class="form-control" maxlength="150" required>
                                        </div>
                                        <div class="col-md-6">
                                            <label for="templateMetaName" class="form-label">Nombre en Meta</label>
                                            <input id="templateMetaName" name="meta_template_name" class="form-control" maxlength="150" required>
                                        </div>
                                        <div class="col-md-4">
                                            <label for="templateLanguage" class="form-label">Idioma</label>
                                            <input id="templateLanguage" name="language" class="form-control" maxlength="10" value="es_CO" required>
                                        </div>
                                        <div class="col-md-4">
                                            <label for="templateCategory" class="form-label">Categoría</label>
                                            <select id="templateCategory" name="category" class="form-select" required>
                                                <option value="utility" selected>Utilidad</option>
                                                <option value="marketing">Marketing</option>
                                                <option value="authentication">Autenticación</option>
                                            </select>
                                        </div>
                                        <div class="col-md-4">
                                            <label for="templateStatus" class="form-label">Estado</label>
                                            <select id="templateStatus" name="status" class="form-select" required>
                                                <option value="draft" selected>Borrador</option>
                                                <option value="pending">Pendiente de aprobación</option>
                                                <option value="approved">Aprobada</option>
                                                <option value="rejected">Rechazada</option>
                                            </select>
                                        </div>
                                        <div class="col-12">
                                            <label for="templateBody" class="form-label">Contenido del mensaje</label>
                                            <textarea id="templateBody" name="body_text" class="form-control" rows="5" required></textarea>

                                            <div id="templateVariables" class="mt-3"></div>
                                        </div>
                                    </div>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
                                    <button type="submit" class="btn btn-success" id="saveTemplateBtn">Guardar plantilla</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            `);
        }

        const modalElement = document.getElementById(modalId);
        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        const form = document.getElementById('createTemplateForm');
        const formError = document.getElementById('createTemplateError');
        const saveButton = document.getElementById('saveTemplateBtn');
        const modalTitle = document.getElementById('createTemplateModalLabel');
        const templateVariables = document.getElementById('templateVariables');
        let editingTemplateId = null;

        function renderVariableTypes(variableTypes = {}) {
            const bodyText = form.querySelector('[name="body_text"]').value || '';

            const matches = [...bodyText.matchAll(/\{\{(\d+)\}\}/g)];
            const variableNumbers = [...new Set(matches.map(match => match[1]))]
                .sort((a, b) => Number(a) - Number(b));

            if (variableNumbers.length === 0) {
                templateVariables.innerHTML = '';
                return;
            }

            templateVariables.innerHTML = `
                <div class="border rounded p-3 bg-light">
                    <h3 class="h6 fw-bold mb-3">Variables detectadas</h3>

                    ${variableNumbers.map(number => `
                        <div class="row align-items-center mb-2">
                            <div class="col-sm-4">
                                <label for="variableType${number}" class="form-label mb-0">
                                    Variable {{${number}}}
                                </label>
                            </div>

                            <div class="col-sm-8">
                                <select
                                    id="variableType${number}"
                                    class="form-select template-variable-type"
                                    data-variable-number="${number}"
                                    required>
                                    <option value="">Selecciona un tipo</option>
                                    <option value="text" ${variableTypes[number] === 'text' ? 'selected' : ''}>
                                        Texto
                                    </option>
                                    <option value="number" ${variableTypes[number] === 'number' ? 'selected' : ''}>
                                        Número
                                    </option>
                                    <option value="date" ${variableTypes[number] === 'date' ? 'selected' : ''}>
                                        Fecha
                                    </option>
                                    <option value="datetime" ${variableTypes[number] === 'datetime' ? 'selected' : ''}>
                                        Fecha y hora
                                    </option>
                                </select>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        form.querySelector('[name="body_text"]').addEventListener('input', () => {
            renderVariableTypes();
        });

        async function loadTemplates(successMessage = '') {
            templateList.innerHTML = `
                <div class="col-12 text-center py-5">
                    <div class="spinner-border text-success" role="status"></div>
                    <p class="text-muted mt-2 mb-0">Cargando plantillas...</p>
                </div>
            `;
            try {
                const response = await fetch('/campanas/api/templates/', {
                    headers: { Accept: 'application/json' },
                    credentials: 'same-origin',
                });
                if (!response.ok) {
                    throw new Error(`Error HTTP ${response.status}`);
                }
                const data = await response.json();
                const templates = Array.isArray(data) ? data : data.results;
                if (!Array.isArray(templates)) {
                    throw new Error('La respuesta de plantillas no tiene un formato válido.');
                }

                const messageMarkup = successMessage
                    ? `<div class="col-12"><div class="alert alert-success" role="status">${escapeHtml(successMessage)}</div></div>`
                    : '';
                if (templates.length === 0) {
                    templateList.innerHTML = `${messageMarkup}
                        <div class="col-12">
                            <div class="alert alert-info">No hay plantillas registradas.</div>
                        </div>
                    `;
                    return;
                }

                templateList.innerHTML = messageMarkup + templates.map((template) => `
                    <div class="col-md-6 col-xl-4">
                        <div class="card outbound-card h-100 shadow-sm">
                            <div class="card-body d-flex flex-column">
                                <div class="d-flex justify-content-between align-items-start mb-2">
                                    <h3 class="h6 fw-bold mb-0">${escapeHtml(template.name)}</h3>
                                    <span class="badge text-bg-light">${escapeHtml(template.category)}</span>
                                </div>
                                <p class="small text-muted mb-2">${escapeHtml(template.meta_template_name)}</p>
                                <div class="bg-light rounded p-3 mb-3 flex-grow-1">
                                    <p class="small mb-0">${escapeHtml(template.body_text)}</p>
                                </div>
                                <div class="small text-muted mb-3">
                                    Variables: ${escapeHtml(template.param_count)}
                                    · Estado: ${escapeHtml(template.status)}
                                </div>
                                <div class="d-flex gap-2">
                                    <button type="button" class="btn btn-outline-success btn-sm flex-grow-1" data-template-id="${escapeHtml(template.id)}">
                                        <i class="bi bi-pencil me-1"></i>Editar
                                    </button>
                                    <button type="button" class="btn btn-outline-danger btn-sm" data-delete-template="${escapeHtml(template.id)}" title="Eliminar">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Error al cargar plantillas:', error);
                templateList.innerHTML = `
                    ${successMessage ? `<div class="col-12"><div class="alert alert-success" role="status">${escapeHtml(successMessage)}</div></div>` : ''}
                    <div class="col-12"><div class="alert alert-danger">No fue posible cargar las plantillas.</div></div>
                `;
            }
        }

        newTemplateBtn.addEventListener('click', () => {
            editingTemplateId = null;
            form.reset();
            formError.textContent = '';
            formError.classList.add('d-none');
            modalTitle.textContent = 'Nueva plantilla';
            saveButton.textContent = 'Guardar plantilla';
            modal.show();
        });

        templateList.addEventListener('click', async (event) => {
            const editButton = event.target.closest('[data-template-id]');
            if (!editButton || !templateList.contains(editButton)) return;

            editingTemplateId = editButton.dataset.templateId;
            form.reset();
            formError.textContent = '';
            formError.classList.add('d-none');
            modalTitle.textContent = 'Editar plantilla';
            saveButton.textContent = 'Guardar cambios';
            saveButton.disabled = true;
            modal.show();

            try {
                const response = await fetch(`/campanas/api/templates/${encodeURIComponent(editingTemplateId)}/`, {
                    headers: { Accept: 'application/json' },
                    credentials: 'same-origin',
                });
                if (!response.ok) {
                    const responseText = await response.text();
                    let backendError = responseText;
                    try {
                        backendError = JSON.parse(responseText);
                    } catch (parseError) {
                        console.warn('La respuesta de error no era JSON:', parseError);
                    }
                    console.error('Error al cargar plantilla:', backendError);
                    formError.textContent = typeof backendError === 'string'
                        ? backendError
                        : (backendError.detail || JSON.stringify(backendError));
                    formError.classList.remove('d-none');
                    return;
                }

                const template = await response.json();
                form.querySelector('[name="name"]').value = template.name || '';
                form.querySelector('[name="meta_template_name"]').value = template.meta_template_name || '';
                form.querySelector('[name="language"]').value = template.language || '';
                form.querySelector('[name="category"]').value = template.category || '';
                form.querySelector('[name="body_text"]').value = template.body_text || '';
                renderVariableTypes(template.variable_types || {});
                form.querySelector('[name="status"]').value = template.status || '';
            } catch (error) {
                console.error('Error al cargar plantilla:', error);
                formError.textContent = 'No fue posible cargar la plantilla. Intenta nuevamente.';
                formError.classList.remove('d-none');
            } finally {
                saveButton.disabled = false;
            }
        });

        templateList.addEventListener('click', async (event) => {
            const deleteButton = event.target.closest('[data-delete-template]');
            if (!deleteButton || !templateList.contains(deleteButton) || deleteButton.disabled) return;

            const templateId = deleteButton.dataset.deleteTemplate;
            if (!window.confirm('¿Estás seguro de que deseas eliminar esta plantilla? Esta acción no se puede deshacer.')) {
                return;
            }

            deleteButton.disabled = true;
            try {
                const response = await fetch(`/campanas/api/templates/${encodeURIComponent(templateId)}/`, {
                    method: 'DELETE',
                    headers: {
                        Accept: 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    credentials: 'same-origin',
                });

                if (!response.ok) {
                    const responseText = await response.text();
                    let backendError = responseText;
                    try {
                        backendError = JSON.parse(responseText);
                    } catch (parseError) {
                        console.warn('La respuesta de error no era JSON:', parseError);
                    }
                    console.error('Error al eliminar plantilla:', backendError);
                    const message = typeof backendError === 'string'
                        ? backendError
                        : (backendError.detail || JSON.stringify(backendError));
                    templateList.insertAdjacentHTML('afterbegin', `
                        <div class="col-12">
                            <div class="alert alert-danger" role="alert">${escapeHtml(message || 'No fue posible eliminar la plantilla.')}</div>
                        </div>
                    `);
                    return;
                }

                await loadTemplates('Plantilla eliminada correctamente.');
            } catch (error) {
                console.error('Error al eliminar plantilla:', error);
                templateList.insertAdjacentHTML('afterbegin', `
                    <div class="col-12">
                        <div class="alert alert-danger" role="alert">No fue posible conectar con el servidor. Intenta nuevamente.</div>
                    </div>
                `);
            } finally {
                deleteButton.disabled = false;
            }
        });

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            formError.textContent = '';
            formError.classList.add('d-none');
            saveButton.disabled = true;

            const formData = new FormData(form);

            const variableTypes = {};
            const variableTypeSelects = form.querySelectorAll('.template-variable-type');

            for (const select of variableTypeSelects) {
                const variableNumber = select.dataset.variableNumber;
                const type = select.value;

                if (!type) {
                    formError.textContent = `Debes seleccionar un tipo para la variable {{${variableNumber}}}.`;
                    formError.classList.remove('d-none');
                    saveButton.disabled = false;
                    return;
                }

                variableTypes[variableNumber] = type;
            }

            const payload = {
                name: formData.get('name'),
                meta_template_name: formData.get('meta_template_name'),
                language: formData.get('language'),
                category: formData.get('category'),
                body_text: formData.get('body_text'),
                variable_types: variableTypes,
                status: formData.get('status'),
            };

            try {
                const isEditing = editingTemplateId !== null;
                const response = await fetch(
                    isEditing
                        ? `/campanas/api/templates/${encodeURIComponent(editingTemplateId)}/`
                        : '/campanas/api/templates/',
                    {
                        method: isEditing ? 'PATCH' : 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            Accept: 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify(payload),
                    }
                );

                if (!response.ok) {
                    const responseText = await response.text();
                    let backendError = responseText;
                    try {
                        backendError = JSON.parse(responseText);
                    } catch (parseError) {
                        console.warn('La respuesta de error no era JSON:', parseError);
                    }
                    console.error(isEditing ? 'Error al editar plantilla:' : 'Error al crear plantilla:', backendError);
                    const message = typeof backendError === 'string'
                        ? backendError
                        : (backendError.detail || JSON.stringify(backendError));
                    formError.textContent = message || (isEditing
                        ? 'No fue posible editar la plantilla.'
                        : 'No fue posible crear la plantilla.');
                    formError.classList.remove('d-none');
                    return;
                }

                modal.hide();
                form.reset();
                editingTemplateId = null;
                await loadTemplates(isEditing
                    ? 'Plantilla actualizada correctamente.'
                    : 'Plantilla creada correctamente.');
            } catch (error) {
                console.error(editingTemplateId !== null ? 'Error al editar plantilla:' : 'Error al crear plantilla:', error);
                formError.textContent = editingTemplateId !== null
                    ? 'No fue posible actualizar la plantilla. Intenta nuevamente.'
                    : 'No fue posible conectar con el servidor. Intenta nuevamente.';
                formError.classList.remove('d-none');
            } finally {
                saveButton.disabled = false;
            }
        });

        loadTemplates();
    }

    function renderSegments() {
        const grid = document.getElementById('segmentsGrid');
        grid.innerHTML = SEGMENTS.map((s) => `
            <div class="col-md-6 col-lg-4">
                <div class="card outbound-card h-100">
                    <div class="card-body d-flex flex-column">
                        <h2 class="h5">${s.name}</h2>
                        <p class="text-muted small mb-2">Origen: ${s.source}</p>
                        <p class="fw-bold text-success mb-3">${s.size.toLocaleString('es-CO')} personas</p>
                        <a class="btn btn-entry mt-auto" href="/campanas/nueva/?segment=${s.id}">Iniciar campaña</a>
                    </div>
                </div>
            </div>
        `).join('');
    }

    function renderLogs() {
        const search = document.getElementById('logSearch');
        const channel = document.getElementById('logChannel');
        const draw = () => {
            const q = (search.value || '').toLowerCase();
            const rows = SEED_LOGS.filter((l) => {
                const hay = `${l.person} ${l.campaign} ${l.event} ${l.detail}`.toLowerCase();
                return (!q || hay.includes(q)) && (!channel.value || l.channel === channel.value);
            });
            document.getElementById('logsTableBody').innerHTML = rows.map((l) => `
                <tr>
                    <td>${l.at}</td>
                    <td class="fw-semibold">${l.person}</td>
                    <td>${channelBadge(l.channel)}</td>
                    <td>${l.campaign}</td>
                    <td>${l.event}</td>
                    <td>${l.detail}</td>
                </tr>
            `).join('');
        };
        search.addEventListener('input', draw);
        channel.addEventListener('change', draw);
        draw();
    }

    return { renderDashboard, renderCampaignCards, renderCampaignsPage, renderCampaignDetail, initWizard, initTemplatesPage, renderSegments, renderLogs };
})();
