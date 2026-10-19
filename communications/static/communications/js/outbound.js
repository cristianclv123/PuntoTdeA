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

        const errorText = document.getElementById('campaignsErrorText');
        const errorClose = error.querySelector('.btn-close');
        if (errorClose && !errorClose.dataset.bound) {
            errorClose.dataset.bound = '1';
            errorClose.addEventListener('click', () => error.classList.add('d-none'));
        }

        try {
            const campaigns = await fetchCampaigns();
            count.textContent = `${campaigns.length} campaña${campaigns.length === 1 ? '' : 's'}`;
            list.innerHTML = campaigns.map(renderCampaignCard).join('');
            empty.classList.toggle('d-none', campaigns.length > 0);
        } catch (requestError) {
            list.innerHTML = '';
            count.textContent = 'Error';
            if (errorText) errorText.textContent = requestError.message;
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
                    templateSnapshot: data.template_snapshot || {},
                    templateLanguage: data.template_language || 'es_CO',
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
        const snapshot = campaign.templateSnapshot || {};
        if (campaign.templateName || snapshot.body_text) {
            tpl = {
                name: campaign.templateName || '',
                body: snapshot.body_text || '',
                buttons: Array.isArray(snapshot.buttons)
                    ? snapshot.buttons
                        .map((button) => (typeof button === 'string' ? button : (button && button.text) || ''))
                        .filter(Boolean)
                    : [],
            };
        }

        const canSend = campaign.status === 'draft' || campaign.status === 'scheduled';

        root.innerHTML = `
        <div class="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-4">
            <div>
                <h2 class="h4 mb-1">${campaign.name}</h2>
                <div class="d-flex flex-wrap gap-2">
                    ${channelBadge(campaign.channel)}
                    ${statusPill(campaign.status)}
                </div>
            </div>
            ${canSend ? `
                <button type="button" id="sendCampaignBtn" class="btn btn-success">
                    <i class="bi bi-send me-1"></i> Enviar ahora
                </button>
            ` : ''}
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

        if (canSend) {
            const sendBtn = document.getElementById('sendCampaignBtn');
            if (sendBtn) {
                sendBtn.addEventListener('click', async () => {
                    sendBtn.disabled = true;
                    sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Enviando…';
                    try {
                        const sendResponse = await fetch(`/campanas/api/campaigns/${encodeURIComponent(campaign.id)}/send/`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': getCookie('csrftoken'),
                            },
                            credentials: 'same-origin',
                        });
                        const sendData = await sendResponse.json().catch(() => ({}));
                        if (!sendResponse.ok) {
                            console.error('Error al enviar campaña:', sendData);
                            toast(sendData.detail || 'No se pudo enviar la campaña.');
                            sendBtn.disabled = false;
                            sendBtn.innerHTML = '<i class="bi bi-send me-1"></i> Enviar ahora';
                        } else {
                            toast(`Campaña enviada. Destinatarios: ${sendData.total_recipients ?? 0}.`);
                            renderCampaignDetail();
                        }
                    } catch (error) {
                        console.error('Error de conexión al enviar:', error);
                        toast('No se pudo conectar con el servidor.');
                        sendBtn.disabled = false;
                        sendBtn.innerHTML = '<i class="bi bi-send me-1"></i> Enviar ahora';
                    }
                });
            }
        }
    }

    function previewHtml(channel, tpl, vars = {}) {
        if (!tpl) return '<p class="small text-muted">Sin plantilla.</p>';
        let body = tpl.body;
        Object.entries(vars).forEach(([k, v]) => {
            body = body.replaceAll(`{{${k}}}`, v || `{{${k}}}`);
        });
        const buttons = (tpl.buttons || []).map((b) => `<span>${escapeHtml((b && b.text) ? b.text : b)}</span>`).join('');
        if (channel === 'whatsapp') {
            return `<div class="wa-bubble">${body}<span class="wa-meta">TdeA · ahora</span></div>${buttons ? `<div class="wa-buttons">${buttons}</div>` : ''}`;
        }
        return `<div class="wa-bubble" style="background:#fff">${body}</div>`;
    }

    function extractVars(body) {
        return [...body.matchAll(/\{\{([^}]+)\}\}/g)].map((m) => m[1]);
    }

    function initWizard(audiencesOnly = false) {
        if (audiencesOnly) {
            renderAudiencesPage();
            return;
        }

        let templates = [];
        const TEMPLATE_CATEGORY_LABELS = {
            marketing: 'Marketing',
            utility: 'Utilidad',
            authentication: 'Autenticación',
        };
        const state = {
            step: 1,
            channel: 'whatsapp',
            segment: null,
            templateId: '',
            vars: {},
        };

        // Selector de audiencia compartido (crear nueva / escoger existente).
        // Reemplaza la antigua carga de archivo "inline" y los chips de segmentos.
        const audiencePickerEl = document.getElementById('campaignAudiencePicker');
        let audiencePicker = null;
        if (audiencePickerEl && window.AudiencePicker) {
            audiencePicker = window.AudiencePicker.mount(audiencePickerEl, {
                apiBase: '/campanas/api',
                context: 'campaña',
                onChange: (segment) => {
                    state.segment = segment
                        ? {
                            id: Number(segment.id),
                            name: segment.name,
                            contact_count: segment.contact_count,
                        }
                        : null;
                },
            });
        }

        const picker = document.getElementById('channelPicker');
        picker.innerHTML = Object.entries(CHANNELS).map(([key, meta]) => `
            <button type="button" class="channel-option ${key === state.channel ? 'is-selected' : ''}" data-channel="${key}">
                <span class="channel-icon ${key} mx-auto mb-2"><i class="bi ${meta.icon}"></i></span>
                <div class="fw-semibold">${meta.label}</div>
            </button>
        `).join('');

        async function renderAudiencesPage() {
            const grid = document.getElementById('segmentsGrid');
            const status = document.getElementById('audiencesStatus');
            const panel = document.getElementById('audienceContactsPanel');
            if (!grid || !status || !panel) return;

            const contactsStatus = document.getElementById('audienceContactsStatus');
            const contactsHead = document.getElementById('audienceContactsHead');
            const contactsBody = document.getElementById('audienceContactsBody');
            const contactsTable = document.getElementById('audienceContactsTableWrap');
            const loadMoreButton = document.getElementById('loadMoreAudienceContacts');
            const sourceLabels = {
                excel_import: 'Importación Excel (Campus)',
                manual: 'Selección manual',
                dynamic: 'Regla dinámica',
            };
            const contactColumns = [
                ['full_name', 'Nombre'],
                ['document_number', 'Documento'],
                ['phone', 'Teléfono'],
                ['email', 'Correo'],
                ['academic_program', 'Programa académico'],
                ['semester', 'Semestre'],
                ['role', 'Perfil'],
                ['whatsapp_opt_in', 'Consentimiento WhatsApp'],
                ['source', 'Origen del contacto'],
            ];
            let audiences = [];
            let nextContactsUrl = null;
            let activeRequest = 0;

            function formatDate(value) {
                if (!value) return '—';
                const date = new Date(value);
                return Number.isNaN(date.getTime()) ? escapeHtml(value) : date.toLocaleString('es-CO');
            }

            async function loadContacts(url, append = false) {
                const requestId = ++activeRequest;
                loadMoreButton.disabled = true;
                contactsStatus.innerHTML = `
                    <div class="text-center py-3">
                        <div class="spinner-border spinner-border-sm text-success me-2" role="status"></div>
                        <span>Cargando contactos...</span>
                    </div>
                `;
                if (!append) {
                    contactsTable.classList.add('d-none');
                    contactsBody.innerHTML = '';
                }

                try {
                    const response = await fetch(url, {
                        headers: { Accept: 'application/json' },
                        credentials: 'same-origin',
                    });
                    if (!response.ok) {
                        throw new Error(`Error HTTP ${response.status}: ${await response.text()}`);
                    }
                    const data = await response.json();
                    if (requestId !== activeRequest) return;

                    const contacts = Array.isArray(data) ? data : (data.results || []);
                    nextContactsUrl = Array.isArray(data) ? null : data.next;
                    if (!append) {
                        contactsHead.innerHTML = `<tr>${contactColumns.map(([, label]) =>
                            `<th scope="col">${escapeHtml(label)}</th>`
                        ).join('')}</tr>`;
                    }
                    if (!contacts.length && !append) {
                        contactsStatus.innerHTML = '<div class="alert alert-info mb-0">Esta audiencia todavía no tiene contactos.</div>';
                        loadMoreButton.classList.add('d-none');
                        return;
                    }

                    contactsBody.insertAdjacentHTML('beforeend', contacts.map((contact) => `
                        <tr>${contactColumns.map(([field]) =>
                            `<td>${escapeHtml(contact[field] ?? '—')}</td>`
                        ).join('')}</tr>
                    `).join(''));
                    contactsStatus.innerHTML = '';
                    contactsTable.classList.remove('d-none');
                    loadMoreButton.classList.toggle('d-none', !nextContactsUrl);
                } catch (error) {
                    if (requestId !== activeRequest) return;
                    console.error('Error al cargar contactos de la audiencia:', error);
                    contactsStatus.innerHTML = '<div class="alert alert-danger mb-0">No fue posible cargar los contactos. Intenta nuevamente.</div>';
                    loadMoreButton.classList.toggle('d-none', !nextContactsUrl);
                } finally {
                    if (requestId === activeRequest) loadMoreButton.disabled = false;
                }
            }

            function renderAudienceCards() {
                if (!audiences.length) {
                    grid.innerHTML = '<div class="col-12"><div class="alert alert-info">No hay audiencias cargadas.</div></div>';
                    return;
                }
                grid.innerHTML = audiences.map((audience) => `
                    <div class="col-md-6 col-xl-4">
                        <article class="card outbound-card audience-card h-100">
                            <div class="card-body d-flex flex-column">
                                <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
                                    <h2 class="h6 fw-bold mb-0">${escapeHtml(audience.name)}</h2>
                                    <span class="badge text-bg-light">${escapeHtml(sourceLabels[audience.source_type] || audience.source_type || 'Sin origen')}</span>
                                </div>
                                <p class="small text-muted flex-grow-1 mb-3">${escapeHtml(audience.description || 'Sin descripción')}</p>
                                <div class="small text-muted mb-3">
                                    <div><strong>Contactos:</strong> ${Number(audience.contact_count || 0).toLocaleString('es-CO')}</div>
                                    <div><strong>Creada:</strong> ${formatDate(audience.created_at)}</div>
                                </div>
                                <button type="button" class="btn btn-outline-success btn-sm" data-view-audience="${escapeHtml(audience.id)}">
                                    <i class="bi bi-eye me-1"></i> Ver contactos
                                </button>
                            </div>
                        </article>
                    </div>
                `).join('');
            }

            grid.addEventListener('click', async (event) => {
                const button = event.target.closest('[data-view-audience]');
                if (!button || !grid.contains(button)) return;
                const audienceId = button.dataset.viewAudience;
                const audience = audiences.find((item) => String(item.id) === audienceId);
                if (!audience) return;

                document.querySelectorAll('.audience-card').forEach((card) => {
                    card.classList.toggle('is-selected', card === button.closest('.audience-card'));
                });
                document.getElementById('audienceContactsTitle').textContent = `Contactos: ${audience.name}`;
                document.getElementById('audienceContactsDescription').textContent =
                    `${sourceLabels[audience.source_type] || audience.source_type || 'Origen no especificado'} · ${formatDate(audience.created_at)}`;
                document.getElementById('audienceContactsCount').textContent =
                    `${Number(audience.contact_count || 0).toLocaleString('es-CO')} contactos`;
                panel.classList.remove('d-none');
                panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                nextContactsUrl = `/campanas/api/segments/${encodeURIComponent(audienceId)}/contacts/`;
                await loadContacts(nextContactsUrl);
            });

            loadMoreButton.addEventListener('click', () => {
                if (nextContactsUrl) loadContacts(nextContactsUrl, true);
            });

            status.innerHTML = `
                <div class="text-center text-muted py-5">
                    <div class="spinner-border text-success mb-2" role="status"></div>
                    <p class="mb-0">Cargando audiencias...</p>
                </div>
            `;
            try {
                const response = await fetch('/campanas/api/segments/', {
                    headers: { Accept: 'application/json' },
                    credentials: 'same-origin',
                });
                if (!response.ok) {
                    throw new Error(`Error HTTP ${response.status}: ${await response.text()}`);
                }
                const data = await response.json();
                audiences = Array.isArray(data) ? data : (data.results || []);
                if (!Array.isArray(audiences)) {
                    throw new Error('La respuesta de audiencias no tiene un formato válido.');
                }
                status.innerHTML = '';
                renderAudienceCards();
            } catch (error) {
                console.error('Error al cargar audiencias:', error);
                grid.innerHTML = '';
                status.innerHTML = '<div class="alert alert-danger">No fue posible cargar las audiencias. Intenta nuevamente.</div>';
            }
        }

        picker.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-channel]');
            if (!btn) return;
            state.channel = btn.dataset.channel;
            state.templateId = '';
            picker.querySelectorAll('.channel-option').forEach((el) => el.classList.toggle('is-selected', el === btn));
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
                    ${t.isSample ? '<span class="template-sample">PLANTILLA DE PRUEBA META</span>' : ''}
                    <p class="small mb-0 mt-2 text-muted">${t.body}</p>
                </button>
            `).join('');
        }

        async function loadTemplates() {
            try {
                const response = await fetch('/campanas/api/templates/meta/', {
                    headers: { Accept: 'application/json' },
                    credentials: 'same-origin',
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok || data.success === false) {
                    throw new Error(data.message || `No se pudieron cargar las plantillas (${response.status}).`);
                }
                const results = Array.isArray(data.templates) ? data.templates : [];
                const approved = results.filter(
                    (template) => String(template.status || '').toUpperCase() === 'APPROVED'
                );
                // Las plantillas de muestra (`hello_world`) solo se ofrecen si
                // son la única aprobada: Meta solo las deja enviar desde el
                // número de prueba público (131058), así que se ocultan en
                // cuanto hay una plantilla propia.
                const offerable = approved.some((template) => !template.is_sample)
                    ? approved.filter((template) => !template.is_sample)
                    : approved;
                templates = offerable
                    .map((template) => ({
                        id: String(template.meta_id || ''),
                        name: template.name || '',
                        category: template.category || '',
                        language: template.language || 'es_CO',
                        type: TEMPLATE_CATEGORY_LABELS[template.category] || template.category || 'Plantilla',
                        body: template.body_text || '',
                        buttons: Array.isArray(template.buttons) ? template.buttons : [],
                        isSample: Boolean(template.is_sample),
                    }));
                renderTemplates();
            } catch (error) {
                templates = [];
                renderTemplates();
                console.error('Error al cargar plantillas:', error);
                toast('No fue posible cargar las plantillas de Meta.');
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
            const tpl = currentTpl();

            const audienceName = state.segment ? state.segment.name : 'Ninguna';
            const size = state.segment ? Number(state.segment.contact_count || 0) : 0;

            document.getElementById('reviewList').innerHTML = `
                <dt class="col-sm-4">Nombre</dt>
                <dd class="col-sm-8">${name}</dd>

                <dt class="col-sm-4">Canal</dt>
                <dd class="col-sm-8">${CHANNELS[state.channel].label}</dd>

                <dt class="col-sm-4">Audiencia</dt>
                <dd class="col-sm-8">${audienceName}</dd>

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

        document.getElementById('wizardBack').addEventListener('click', () => showStep(Math.max(1, state.step - 1)));
        document.getElementById('wizardNext').addEventListener('click', async () => {
            if (state.step === 1) {
                if (!document.getElementById('campaignName').value.trim()) {
                    return toast('Escribe un nombre de campaña.');
                }

                if (!state.segment) {
                    return toast('Crea o escoge una audiencia de destino.');
                }

                return showStep(2);
            }
            if (state.step === 2) {
                if (!state.templateId) return toast('Selecciona una plantilla.');
                return showStep(3);
            }
            launch();
        });
        const wizardTestButton = document.getElementById('wizardTest');
        wizardTestButton.addEventListener('click', async () => {
            if (!state.templateId) {
                toast('Selecciona una plantilla antes de enviar la prueba.');
                return;
            }

            const originalText = wizardTestButton.textContent;
            wizardTestButton.disabled = true;
            wizardTestButton.textContent = 'Enviando...';
            try {
                const response = await fetch('/campanas/test-send/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        Accept: 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        template: state.templateId,
                        params: state.vars,
                    }),
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    toast(data.message || 'No se pudo enviar el mensaje de prueba.');
                    return;
                }
                toast(data.message || 'Mensaje de prueba enviado correctamente.');
            } catch (error) {
                console.error('Error al enviar mensaje de prueba:', error);
                toast('No se pudo enviar el mensaje de prueba. Verifica la conexión con el servidor.');
            } finally {
                wizardTestButton.disabled = false;
                wizardTestButton.textContent = originalText;
            }
        });
        document.querySelectorAll('.wizard-step').forEach((btn) => {
            btn.addEventListener('click', () => showStep(Number(btn.dataset.step)));
        });

        async function launch() {
            const sendMode = document.getElementById('sendMode').value;
            const scheduleAt = document.getElementById('scheduleAt').value;

            const name = document.getElementById('campaignName').value.trim();

            if (!state.segment) {
                toast('Crea o escoge una audiencia de destino.');
                return;
            }

            if (!state.templateId) {
                toast('Selecciona una plantilla.');
                return;
            }

            const selectedTemplate = currentTpl();
            if (!selectedTemplate) {
                toast('La plantilla seleccionada ya no está disponible en Meta.');
                return;
            }

            try {
                const payload = {
                    name: name,
                    template: state.templateId,
                    template_name: selectedTemplate.name || '',
                    template_language: selectedTemplate.language || 'es_CO',
                    template_snapshot: {
                        name: selectedTemplate.name || '',
                        language: selectedTemplate.language || 'es_CO',
                        category: selectedTemplate.category || '',
                        body_text: selectedTemplate.body || '',
                        buttons: Array.isArray(selectedTemplate.buttons) ? selectedTemplate.buttons : [],
                    },
                    segment: state.segment.id,
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

                if (sendMode !== 'later') {
                    toast('Campaña creada. Enviando a Meta…');
                    try {
                        const sendResponse = await fetch(`/campanas/api/campaigns/${encodeURIComponent(backendCampaign.id)}/send/`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': getCookie('csrftoken'),
                            },
                            credentials: 'same-origin',
                        });
                        const sendData = await sendResponse.json().catch(() => ({}));
                        if (!sendResponse.ok) {
                            console.error('Error al enviar campaña:', sendData);
                            toast('Campaña creada pero no se pudo enviar. Inténtalo desde el detalle.');
                        } else {
                            toast(`Campaña enviada. Destinatarios: ${sendData.total_recipients ?? 0}.`);
                        }
                    } catch (sendError) {
                        console.error('Error de conexión al enviar:', sendError);
                        toast('Campaña creada pero no se pudo enviar. Inténtalo desde el detalle.');
                    }
                } else {
                    toast('Campaña programada correctamente.');
                }

                window.location.href = `/campanas/detalle/?id=${encodeURIComponent(backendCampaign.id)}`;

            } catch (error) {
                console.error('Error de conexión:', error);
                toast('No se pudo conectar con el backend.');
            }
        }

        showStep(1);
    }

    function initAudiencesPage() {
        initWizard(true);
    }

    function initTemplatesPage() {
        const newTemplateBtn = document.getElementById('newTemplateBtn');
        const templateList = document.getElementById('templateList');
        const refreshBtn = document.getElementById('refreshTemplatesBtn');
        const alertBox = document.getElementById('templatesAlert');
        if (!newTemplateBtn || !templateList) return;

        const CATEGORY_LABELS = {
            marketing: 'Marketing',
            utility: 'Utilidad',
            authentication: 'Autenticación',
        };

        const META_STATUS_LABELS = {
            APPROVED: 'Aprobada',
            PENDING: 'Pendiente',
            REJECTED: 'Rechazada',
            PAUSED: 'Pausada',
            DISABLED: 'Deshabilitada',
            IN_APPEAL: 'En apelación',
            PENDING_DELETION: 'Pendiente de eliminación',
            DELETED: 'Eliminada',
            LIMIT_EXCEEDED: 'Límite excedido',
        };

        // Orden y etiquetas en plural para el filtro por estado de Meta.
        const META_STATUS_FILTERS = [
            ['APPROVED', 'Aprobadas'],
            ['PENDING', 'Pendientes'],
            ['REJECTED', 'Rechazadas'],
            ['PAUSED', 'Pausadas'],
            ['DISABLED', 'Deshabilitadas'],
            ['IN_APPEAL', 'En apelación'],
            ['PENDING_DELETION', 'Pendientes de eliminación'],
            ['DELETED', 'Eliminadas'],
            ['LIMIT_EXCEEDED', 'Límite excedido'],
        ];

        const filterTabs = Array.from(document.querySelectorAll('#templatesFilterTabs [data-filter]'));
        const statusFilters = document.getElementById('templateStatusFilters');

        let drafts = [];
        let metaTemplates = [];
        let mode = 'create';
        let editingId = null;
        let activeFilter = 'all';
        let activeStatus = 'all';

        function showAlert(message, kind = 'ok') {
            if (!alertBox) return;
            alertBox.innerHTML = `
                <div class="wa-alert ${kind} is-dismissible">
                    <span>${escapeHtml(message)}</span>
                    <button type="button" class="wa-alert-close" data-dismiss-alert aria-label="Cerrar mensaje" title="Cerrar">&#215;</button>
                </div>`;
        }

        if (alertBox) {
            alertBox.addEventListener('click', (event) => {
                if (event.target.closest('[data-dismiss-alert]')) clearAlert();
            });
        }

        function clearAlert() {
            if (alertBox) alertBox.innerHTML = '';
        }

        function extractError(data, fallback) {
            if (!data || typeof data !== 'object') return fallback;
            if (typeof data.message === 'string' && data.message) return data.message;
            if (typeof data.detail === 'string' && data.detail) return data.detail;
            const parts = Object.entries(data).map(([field, messages]) => {
                const value = Array.isArray(messages) ? messages.join(' ') : messages;
                return `${field}: ${value}`;
            });
            return parts.length ? parts.join(' ') : fallback;
        }

        async function requestJson(url, options = {}) {
            const { headers: extraHeaders, ...rest } = options;
            const response = await fetch(url, {
                credentials: 'same-origin',
                ...rest,
                headers: {
                    Accept: 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                    ...(extraHeaders || {}),
                },
            });
            const data = await response.json().catch(() => ({}));
            return { response, data };
        }

        function templateCard(kind, template) {
            const isDraft = kind === 'draft';
            const isSample = !isDraft && Boolean(template.is_sample);
            const id = isDraft ? template.id : template.meta_id;
            const source = isDraft
                ? '<span class="template-source template-source--draft" title="Borrador local" aria-label="Borrador local"><i class="bi bi-file-earmark-text" aria-hidden="true"></i></span>'
                : '<span class="template-source template-source--meta" title="Plantilla de Meta" aria-label="Plantilla de Meta"><i class="bi bi-whatsapp" aria-hidden="true"></i></span>';
            const category = CATEGORY_LABELS[template.category] || template.category || 'Sin categoría';
            const statusRow = isDraft
                ? `<div class="d-flex align-items-center gap-2 flex-wrap">
                       <span class="template-status template-status--draft">Borrador</span>
                       <span class="template-category">${escapeHtml(category)} · ${escapeHtml(template.param_count ?? 0)} variable(s)</span>
                   </div>`
                : `<div class="d-flex align-items-center gap-2 flex-wrap">
                       <span class="template-status template-status--${escapeHtml(String(template.status || 'pending').toLowerCase())}">${escapeHtml(META_STATUS_LABELS[String(template.status || '').toUpperCase()] || template.status || 'Sin estado')}</span>
                       <span class="template-category">${escapeHtml(category)}</span>
                       ${isSample ? '<span class="template-sample">PLANTILLA DE PRUEBA META</span>' : ''}
                   </div>`;
            const rejection = !isDraft && template.rejected_reason
                ? `<div class="template-rejection">${escapeHtml(template.rejected_reason)}</div>`
                : '';
            const metaLine = !isDraft
                ? `<div class="template-meta-line">ID Meta: ${escapeHtml(template.meta_id)} · ${escapeHtml(template.language || '')}</div>`
                : '';
            const sendButton = isDraft
                ? `<button type="button" class="btn btn-outline-success btn-sm" data-action="send" data-kind="draft" data-id="${escapeHtml(template.id)}">
                       <i class="bi bi-send me-1"></i>Enviar a Meta
                   </button>`
                : '';
            const duplicateButton = !isDraft
                ? `<button type="button" class="btn btn-outline-primary btn-sm" data-action="duplicate" data-kind="meta" data-id="${escapeHtml(template.meta_id)}">
                       <i class="bi bi-files me-1"></i>Duplicar como borrador
                   </button>`
                : '';

            // Las plantillas de muestra de Meta (`hello_world`) no se pueden
            // editar ni eliminar: Meta responde 2388094. Se dejan los botones
            // deshabilitados con el motivo en el tooltip.
            const sampleHint = 'Las plantillas de muestra de Meta no se pueden editar ni eliminar.';
            const editButton = isSample
                ? `<button type="button" class="btn btn-outline-secondary btn-sm" disabled title="${sampleHint}">
                       <i class="bi bi-pencil"></i>
                   </button>`
                : `<button type="button" class="btn btn-outline-secondary btn-sm" data-action="edit" data-kind="${kind}" data-id="${escapeHtml(id)}" title="Editar">
                       <i class="bi bi-pencil"></i>
                   </button>`;
            const deleteButton = isSample
                ? `<button type="button" class="btn btn-outline-danger btn-sm" disabled title="${sampleHint}">
                       <i class="bi bi-trash"></i>
                   </button>`
                : `<button type="button" class="btn btn-outline-danger btn-sm" data-action="delete" data-kind="${kind}" data-id="${escapeHtml(id)}" data-name="${escapeHtml(template.name || '')}" title="Eliminar">
                       <i class="bi bi-trash"></i>
                   </button>`;

            return `
                <div class="col-md-6 col-xl-4">
                    <article class="template-card h-100">
                        <div class="template-card-head">
                            <h3>${escapeHtml(template.name)}</h3>
                            ${source}
                        </div>
                        ${statusRow}
                        <p class="template-body">${escapeHtml(template.body_text || 'Sin contenido')}</p>
                        ${rejection}
                        ${metaLine}
                        <div class="template-actions">
                            ${sendButton}
                            ${duplicateButton}
                            ${editButton}
                            ${deleteButton}
                        </div>
                    </article>
                </div>`;
        }

        function renderList() {
            const visibleDrafts = (activeFilter === 'all' || activeFilter === 'draft') ? drafts : [];
            let visibleMeta = (activeFilter === 'all' || activeFilter === 'meta') ? metaTemplates : [];
            if (activeFilter === 'meta' && activeStatus !== 'all') {
                visibleMeta = visibleMeta.filter(
                    (template) => String(template.status || '').toUpperCase() === activeStatus
                );
            }
            const cards = [
                ...visibleDrafts.map((template) => templateCard('draft', template)),
                ...visibleMeta.map((template) => templateCard('meta', template)),
            ];
            if (!cards.length) {
                const emptyMessage = (activeFilter === 'all')
                    ? 'Todavía no hay plantillas ni borradores.'
                    : 'No hay plantillas que coincidan con el filtro seleccionado.';
                templateList.innerHTML = `<div class="col-12"><div class="wa-alert warn">${emptyMessage}</div></div>`;
                return;
            }
            templateList.innerHTML = cards.join('');
        }

        function updateFilterTabs() {
            filterTabs.forEach((tab) => {
                tab.classList.toggle('is-active', tab.dataset.filter === activeFilter);
            });
        }

        function renderStatusFilters() {
            if (!statusFilters) return;
            if (activeFilter !== 'meta') {
                statusFilters.hidden = true;
                statusFilters.innerHTML = '';
                return;
            }

            if (!metaTemplates.length) {
                statusFilters.hidden = true;
                statusFilters.innerHTML = '';
                return;
            }

            const counts = {};
            metaTemplates.forEach((template) => {
                const status = String(template.status || '').toUpperCase();
                counts[status] = (counts[status] || 0) + 1;
            });

            // Si el estado elegido ya no existe, volvemos a "Todos".
            if (activeStatus !== 'all' && !counts[activeStatus]) {
                activeStatus = 'all';
            }

            const knownOrder = META_STATUS_FILTERS.map(([value]) => value);
            const chips = [
                `<button type="button" class="template-status-chip${activeStatus === 'all' ? ' is-active' : ''}" data-status="all">Todos (${metaTemplates.length})</button>`,
            ];

            META_STATUS_FILTERS.forEach(([value, label]) => {
                if (!counts[value]) return;
                chips.push(`<button type="button" class="template-status-chip${activeStatus === value ? ' is-active' : ''}" data-status="${value}">${label} (${counts[value]})</button>`);
            });

            Object.keys(counts)
                .filter((status) => status && !knownOrder.includes(status))
                .sort()
                .forEach((status) => {
                    chips.push(`<button type="button" class="template-status-chip${activeStatus === status ? ' is-active' : ''}" data-status="${escapeHtml(status)}">${escapeHtml(status)} (${counts[status]})</button>`);
                });

            statusFilters.innerHTML = chips.join('');
            statusFilters.hidden = false;
        }

        async function fetchDrafts() {
            const response = await fetch('/campanas/api/templates/', {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
            });
            if (!response.ok) {
                throw new Error(`No se pudieron cargar los borradores (${response.status}).`);
            }
            const data = await response.json();
            const results = Array.isArray(data) ? data : (data.results || []);
            return Array.isArray(results) ? results : [];
        }

        async function fetchMetaTemplates() {
            const response = await fetch('/campanas/api/templates/meta/', {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.success === false) {
                throw new Error(data.message || `Meta no devolvió las plantillas (${response.status}).`);
            }
            return Array.isArray(data.templates) ? data.templates : [];
        }

        async function load(successMessage = '') {
            clearAlert();
            templateList.innerHTML = `
                <div class="col-12 text-center py-5">
                    <div class="spinner-border text-success" role="status"></div>
                    <p class="text-muted mt-2 mb-0">Cargando plantillas...</p>
                </div>`;
            try {
                const draftResults = await fetchDrafts();
                let metaResults = [];
                let metaError = '';
                try {
                    metaResults = await fetchMetaTemplates();
                } catch (error) {
                    console.error('Error al cargar las plantillas de Meta:', error);
                    metaError = error.message || 'Meta no respondió.';
                }
                drafts = draftResults;
                metaTemplates = metaResults;
                updateFilterTabs();
                renderStatusFilters();
                renderList();
                if (metaError) {
                    showAlert(`No se pudieron leer las plantillas de Meta: ${metaError}`, 'warn');
                } else if (successMessage) {
                    showAlert(successMessage, 'ok');
                }
            } catch (error) {
                console.error('Error al cargar los borradores:', error);
                templateList.innerHTML = '';
                showAlert(error.message || 'No fue posible cargar los borradores.', 'bad');
            }
        }

        // ---- Diálogo de crear / editar ----
        const panel = templateList.closest('.outbound-panel') || document.body;
        const dialogId = 'templateDialog';
        if (!document.getElementById(dialogId)) {
            panel.insertAdjacentHTML('beforeend', `
                <dialog class="template-dialog" id="${dialogId}">
                    <form class="template-dialog-form" id="templateForm">
                        <div class="template-dialog-head">
                            <h3 id="templateDialogTitle">Nueva plantilla</h3>
                            <button type="button" class="template-dialog-close" id="templateDialogClose" aria-label="Cerrar">
                                <i class="bi bi-x-lg"></i>
                            </button>
                        </div>
                        <div id="templateDialogError" class="template-dialog-error d-none" role="alert"></div>
                        <div class="template-fields">
                            <div class="field-group">
                                <label class="field-label" for="templateNameInput">Nombre del borrador</label>
                                <input id="templateNameInput" class="field-input" maxlength="150">
                            </div>
                            <div class="field-group">
                                <label class="field-label" for="templateCategoryInput">Categoría</label>
                                <select id="templateCategoryInput" class="field-select">
                                    <option value="utility">Utilidad</option>
                                    <option value="marketing">Marketing</option>
                                    <option value="authentication">Autenticación</option>
                                </select>
                            </div>
                        </div>
                        <div class="field-group">
                            <label class="field-label" for="templateBodyInput">Contenido del mensaje</label>
                            <textarea id="templateBodyInput" class="field-textarea" rows="4"></textarea>
                        </div>
                        <div id="templateVariablesBox"></div>
                        <div class="template-dialog-actions">
                            <button type="button" class="btn btn-outline-secondary" id="templateCancel">Cancelar</button>
                            <div class="d-flex flex-wrap gap-2">
                                <button type="button" class="btn btn-outline-success" id="templateSaveDraft">Guardar como borrador</button>
                                <button type="button" class="btn btn-success" id="templateSaveMeta">Guardar y enviar a Meta</button>
                            </div>
                        </div>
                    </form>
                </dialog>`);
        }

        const dialog = document.getElementById(dialogId);
        const form = document.getElementById('templateForm');
        const dialogTitle = document.getElementById('templateDialogTitle');
        const dialogError = document.getElementById('templateDialogError');
        const nameInput = document.getElementById('templateNameInput');
        const categoryInput = document.getElementById('templateCategoryInput');
        const bodyInput = document.getElementById('templateBodyInput');
        const variablesBox = document.getElementById('templateVariablesBox');
        const saveDraftBtn = document.getElementById('templateSaveDraft');
        const saveMetaBtn = document.getElementById('templateSaveMeta');

        form.addEventListener('submit', (event) => event.preventDefault());
        document.getElementById('templateDialogClose').addEventListener('click', () => dialog.close());
        document.getElementById('templateCancel').addEventListener('click', () => dialog.close());

        function showDialogError(message) {
            dialogError.textContent = message;
            dialogError.classList.remove('d-none');
        }

        function renderVariables(variableTypes = {}) {
            const body = bodyInput.value || '';
            const numbers = [...new Set([...body.matchAll(/\{\{(\d+)\}\}/g)].map((match) => match[1]))]
                .sort((a, b) => Number(a) - Number(b));
            if (!numbers.length) {
                variablesBox.innerHTML = '';
                return;
            }
            variablesBox.innerHTML = `
                <div class="template-variables">
                    <div class="field-label mb-2">Ejemplos por variable</div>
                    ${numbers.map((number) => `
                        <div class="field-group mb-2">
                            <label class="field-label" for="variableType${number}">Variable {{${number}}}</label>
                            <select id="variableType${number}" class="field-select template-variable-type" data-variable-number="${number}">
                                <option value="">Selecciona un tipo</option>
                                <option value="text" ${variableTypes[number] === 'text' ? 'selected' : ''}>Texto</option>
                                <option value="number" ${variableTypes[number] === 'number' ? 'selected' : ''}>Número</option>
                                <option value="date" ${variableTypes[number] === 'date' ? 'selected' : ''}>Fecha</option>
                                <option value="datetime" ${variableTypes[number] === 'datetime' ? 'selected' : ''}>Fecha y hora</option>
                            </select>
                        </div>`).join('')}
                </div>`;
        }

        bodyInput.addEventListener('input', () => renderVariables());

        function openDialog(nextMode, options = {}) {
            mode = nextMode;
            editingId = options.id || null;
            dialogError.classList.add('d-none');
            dialogError.textContent = '';

            nameInput.value = options.name || '';
            categoryInput.value = options.category || 'utility';
            bodyInput.value = options.bodyText || '';

            const editingMeta = mode === 'edit-meta';
            const editingDraft = mode === 'edit-draft';

            dialogTitle.textContent = editingMeta
                ? 'Editar plantilla en Meta'
                : (editingDraft ? 'Editar borrador' : 'Nueva plantilla');

            // En una plantilla de Meta no se pueden cambiar nombre ni categoría.
            nameInput.disabled = editingMeta;
            categoryInput.disabled = editingMeta;

            saveDraftBtn.classList.toggle('d-none', editingMeta);
            saveDraftBtn.textContent = editingDraft ? 'Guardar borrador' : 'Guardar como borrador';

            saveMetaBtn.textContent = editingMeta
                ? 'Guardar cambios'
                : (editingDraft ? 'Enviar a Meta' : 'Guardar y enviar a Meta');

            renderVariables(options.variableTypes || {});
            dialog.showModal();
        }

        function collectPayload() {
            const name = nameInput.value.trim();
            if (!name && mode !== 'edit-meta') {
                throw new Error('Escribe un nombre para el borrador.');
            }
            const bodyText = bodyInput.value;
            if (!bodyText.trim()) {
                throw new Error('El contenido del mensaje es obligatorio.');
            }
            const variableTypes = {};
            for (const select of variablesBox.querySelectorAll('.template-variable-type')) {
                if (!select.value) {
                    throw new Error(`Selecciona el tipo de la variable {{${select.dataset.variableNumber}}}.`);
                }
                variableTypes[select.dataset.variableNumber] = select.value;
            }
            return {
                name,
                category: categoryInput.value,
                body_text: bodyText,
                variable_types: variableTypes,
            };
        }

        async function createDraft(payload) {
            const { response, data } = await requestJson('/campanas/api/templates/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                throw new Error(extractError(data, 'No fue posible guardar el borrador.'));
            }
            return data;
        }

        async function updateDraft(id, payload) {
            const { response, data } = await requestJson(`/campanas/api/templates/${encodeURIComponent(id)}/`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                throw new Error(extractError(data, 'No fue posible actualizar el borrador.'));
            }
            return data;
        }

        async function sendDraftToMeta(id) {
            const { response, data } = await requestJson(`/campanas/api/templates/${encodeURIComponent(id)}/enviar-a-meta/`, {
                method: 'POST',
            });
            if (!response.ok || data.success === false) {
                throw new Error(data.message || extractError(data, 'Meta no aceptó la plantilla.'));
            }
            return data;
        }

        async function editMetaTemplate(id, payload) {
            const { response, data } = await requestJson(`/campanas/api/templates/meta/${encodeURIComponent(id)}/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    body_text: payload.body_text,
                    variable_types: payload.variable_types,
                }),
            });
            if (!response.ok || data.success === false) {
                throw new Error(data.message || extractError(data, 'Meta no aceptó la edición.'));
            }
            return data;
        }

        async function deleteDraft(id) {
            const { response, data } = await requestJson(`/campanas/api/templates/${encodeURIComponent(id)}/`, {
                method: 'DELETE',
            });
            if (!response.ok) {
                throw new Error(extractError(data, 'No fue posible eliminar el borrador.'));
            }
        }

        async function deleteMetaTemplate(id, name) {
            const query = name ? `?name=${encodeURIComponent(name)}` : '';
            const { response, data } = await requestJson(`/campanas/api/templates/meta/${encodeURIComponent(id)}/${query}`, {
                method: 'DELETE',
            });
            if (!response.ok || data.success === false) {
                throw new Error(data.message || extractError(data, 'Meta no eliminó la plantilla.'));
            }
            return data;
        }

        function confirmDialog(title, message) {
            return new Promise((resolve) => {
                const el = document.createElement('dialog');
                el.className = 'template-dialog';
                el.innerHTML = `
                    <form class="template-dialog-form">
                        <div class="template-dialog-head"><h3>${escapeHtml(title)}</h3></div>
                        <p class="small" style="margin:0;color:#d4d4d4;">${escapeHtml(message)}</p>
                        <div class="template-dialog-actions">
                            <button type="button" class="btn btn-outline-secondary" data-choice="cancel">Cancelar</button>
                            <button type="button" class="btn btn-danger" data-choice="confirm">Eliminar</button>
                        </div>
                    </form>`;
                let answered = false;
                el.addEventListener('click', (event) => {
                    const choice = event.target.closest('[data-choice]');
                    if (!choice) return;
                    answered = true;
                    el.close();
                    resolve(choice.dataset.choice === 'confirm');
                });
                el.addEventListener('cancel', () => {
                    answered = true;
                    resolve(false);
                });
                el.addEventListener('close', () => {
                    if (!answered) resolve(false);
                    el.remove();
                });
                document.body.appendChild(el);
                el.showModal();
            });
        }

        async function handleSaveDraft() {
            let payload;
            try {
                payload = collectPayload();
            } catch (error) {
                showDialogError(error.message);
                return;
            }

            saveDraftBtn.disabled = true;
            saveMetaBtn.disabled = true;
            try {
                if (mode === 'edit-draft') {
                    await updateDraft(editingId, payload);
                } else {
                    await createDraft(payload);
                }
                dialog.close();
                await load('Borrador guardado.');
            } catch (error) {
                showDialogError(error.message);
            } finally {
                saveDraftBtn.disabled = false;
                saveMetaBtn.disabled = false;
            }
        }

        async function handleSaveMeta() {
            let payload;
            try {
                payload = collectPayload();
            } catch (error) {
                showDialogError(error.message);
                return;
            }

            saveDraftBtn.disabled = true;
            saveMetaBtn.disabled = true;
            try {
                if (mode === 'edit-meta') {
                    await editMetaTemplate(editingId, payload);
                    dialog.close();
                    await load('Cambios enviados a Meta. La plantilla vuelve a revisión.');
                    return;
                }

                let draftId = editingId;
                if (mode === 'edit-draft') {
                    await updateDraft(draftId, payload);
                } else {
                    const created = await createDraft(payload);
                    draftId = created.id;
                }
                const result = await sendDraftToMeta(draftId);
                dialog.close();
                await load(result.message || 'Plantilla enviada a Meta.');
            } catch (error) {
                showDialogError(error.message);
            } finally {
                saveDraftBtn.disabled = false;
                saveMetaBtn.disabled = false;
            }
        }

        saveDraftBtn.addEventListener('click', handleSaveDraft);
        saveMetaBtn.addEventListener('click', handleSaveMeta);

        newTemplateBtn.addEventListener('click', () => openDialog('create'));

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => load());
        }

        templateList.addEventListener('click', async (event) => {
            const button = event.target.closest('[data-action]');
            if (!button || !templateList.contains(button) || button.disabled) return;
            const action = button.dataset.action;
            const kind = button.dataset.kind;
            const id = button.dataset.id;

            if (action === 'edit') {
                if (kind === 'draft') {
                    const template = drafts.find((item) => String(item.id) === String(id));
                    if (!template) return;
                    openDialog('edit-draft', {
                        id: template.id,
                        name: template.name,
                        category: template.category,
                        bodyText: template.body_text,
                        variableTypes: template.variable_types || {},
                    });
                } else {
                    const template = metaTemplates.find((item) => String(item.meta_id) === String(id));
                    if (!template) return;
                    openDialog('edit-meta', {
                        id: template.meta_id,
                        name: template.name,
                        category: template.category,
                        bodyText: template.body_text,
                        variableTypes: Object.fromEntries((template.indexes || []).map((index) => [index, 'text'])),
                    });
                }
                return;
            }

            if (action === 'duplicate') {
                const template = metaTemplates.find((item) => String(item.meta_id) === String(id));
                if (!template) return;
                openDialog('create', {
                    name: `${template.name} (copia)`,
                    category: template.category,
                    bodyText: template.body_text,
                    variableTypes: Object.fromEntries((template.indexes || []).map((index) => [index, 'text'])),
                });
                showAlert('Duplicando una plantilla de Meta como borrador local.', 'warn');
                return;
            }

            if (action === 'send') {
                const original = button.innerHTML;
                button.disabled = true;
                button.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Enviando...';
                try {
                    const result = await sendDraftToMeta(id);
                    await load(result.message || 'Plantilla enviada a Meta.');
                } catch (error) {
                    button.disabled = false;
                    button.innerHTML = original;
                    showAlert(error.message || 'No fue posible enviar la plantilla a Meta.', 'bad');
                }
                return;
            }

            if (action === 'delete') {
                const kindLabel = kind === 'draft' ? 'borrador local' : 'plantilla de Meta';
                const confirmed = await confirmDialog(
                    'Eliminar plantilla',
                    `¿Eliminar este ${kindLabel}? Esta acción no se puede deshacer.`
                );
                if (!confirmed) return;
                try {
                    if (kind === 'draft') {
                        await deleteDraft(id);
                        await load('Borrador eliminado.');
                    } else {
                        await deleteMetaTemplate(id, button.dataset.name || '');
                        await load('Plantilla eliminada de Meta.');
                    }
                } catch (error) {
                    showAlert(error.message || 'No fue posible eliminar la plantilla.', 'bad');
                }
            }
        });

        filterTabs.forEach((tab) => {
            tab.addEventListener('click', () => {
                activeFilter = tab.dataset.filter;
                activeStatus = 'all';
                updateFilterTabs();
                renderStatusFilters();
                renderList();
            });
        });

        if (statusFilters) {
            statusFilters.addEventListener('click', (event) => {
                const chip = event.target.closest('[data-status]');
                if (!chip) return;
                activeStatus = chip.dataset.status;
                renderStatusFilters();
                renderList();
            });
        }

        load();
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

    return { renderDashboard, renderCampaignCards, renderCampaignsPage, renderCampaignDetail, initWizard, initAudiencesPage, initTemplatesPage, renderSegments, renderLogs };
})();
