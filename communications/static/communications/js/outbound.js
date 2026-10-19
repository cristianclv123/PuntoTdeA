const OutboundUI = (() => {

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(';').shift();
        }
        return null;
    }

    const { CHANNELS, TEMPLATES, loadCampaigns, saveCampaigns } = window.OutboundDemo;

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
        return `<span class="channel-chip"><span class="channel-icon ${escapeHtml(channel)}"><i class="bi ${escapeHtml(meta.icon)}"></i></span>${escapeHtml(meta.label)}</span>`;
    }

    function statusPill(status, label = status) {
        const statusClass = CAMPAIGN_STATUS_CLASSES[status] || status;
        return `<span class="status-pill status-${escapeHtml(statusClass)}">${escapeHtml(label)}</span>`;
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
        const campaigns = [];
        const visitedUrls = new Set();
        const apiPath = '/campanas/api/campaigns/';
        let nextUrl = '/campanas/api/campaigns/';
        let requestBase = new URL(nextUrl, window.location.origin);

        while (nextUrl) {
            const requestUrl = new URL(nextUrl, requestBase);
            if (requestUrl.origin !== window.location.origin || requestUrl.pathname !== apiPath) {
                throw new Error('La paginación de campañas devolvió una URL fuera de la API.');
            }
            requestUrl.hash = '';
            if (visitedUrls.has(requestUrl.href)) {
                throw new Error('La paginación de campañas contiene un ciclo.');
            }
            visitedUrls.add(requestUrl.href);

            const response = await fetch(requestUrl, {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
            });
            if (!response.ok) {
                throw new Error(`No se pudieron cargar las campañas (${response.status}).`);
            }
            const payload = await response.json();
            if (Array.isArray(payload)) {
                campaigns.push(...payload);
                nextUrl = null;
            } else if (payload && Array.isArray(payload.results)) {
                campaigns.push(...payload.results);
                nextUrl = payload.next || null;
                if (nextUrl && typeof nextUrl !== 'string') {
                    throw new Error('La paginación de campañas devolvió un enlace inválido.');
                }
                requestBase = requestUrl;
            } else {
                throw new Error('La API devolvió una respuesta de campañas inválida.');
            }
        }

        return campaigns;
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
                            <div class="small" style="color: var(--text-muted); font-size: 0.75rem;">Destinatarios no pendientes ni de baja</div>
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

        list.innerHTML = `
            <div class="text-center py-4" style="color: var(--text-muted);">
                <div class="spinner-border spinner-border-sm text-success me-2" role="status"></div>
                Cargando listado de campañas…
            </div>
        `;
        empty.classList.add('d-none');
        error.classList.add('d-none');

        try {
            const campaigns = await fetchCampaigns();
            count.textContent = `${campaigns.length} campaña${campaigns.length === 1 ? '' : 's'}`;
            list.innerHTML = campaigns.map(renderCampaignCard).join('');
            empty.classList.toggle('d-none', campaigns.length > 0);
        } catch (requestError) {
            list.innerHTML = '';
            count.textContent = 'Error';
            if (errorText) errorText.textContent = requestError.message || 'No fue posible cargar las campañas.';
            error.classList.remove('d-none');
        }
    }

    function campaignUrl(id) {
        return `/campanas/detalle/?id=${encodeURIComponent(id)}`;
    }

    async function renderDashboard() {
        const kpiGrid = document.getElementById('kpiGrid');
        const recentBody = document.getElementById('recentCampaignsBody');
        const channelList = document.getElementById('channelList');
        const activityFeed = document.getElementById('activityFeed');
        if (!kpiGrid || !recentBody || !channelList || !activityFeed) return;

        const loading = `
            <div class="text-center text-muted small py-3">
                <span class="spinner-border spinner-border-sm text-success me-1" role="status"></span>
                Cargando campañas…
            </div>
        `;
        kpiGrid.innerHTML = `<div class="col-12">${loading}</div>`;
        recentBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">${loading}</td></tr>`;
        channelList.innerHTML = loading;
        activityFeed.innerHTML = '<p class="small text-muted mb-0">La actividad reciente no está disponible en esta vista.</p>';

        try {
            const campaigns = await fetchCampaigns();
            const total = (field) => campaigns.reduce(
                (sum, campaign) => sum + (Number(campaign[field]) || 0),
                0,
            );
            const totalRecipients = total('total_recipients');
            const sent = total('sent_count');
            const delivered = total('delivered_count');
            const failed = total('failed_count');
            const kpis = [
                { label: 'Destinatarios', value: totalRecipients },
                { label: 'Destinatarios no pendientes ni de baja', value: sent },
                { label: 'Entregados', value: delivered },
                { label: 'Fallidos', value: failed },
            ];
            kpiGrid.innerHTML = kpis.map((kpi) => `
                <div class="col-6 col-lg-3"><div class="kpi-card"><div class="kpi-label">${kpi.label}</div><div class="kpi-value">${kpi.value.toLocaleString('es-CO')}</div></div></div>
            `).join('');

            recentBody.innerHTML = campaigns.slice(0, 4).map((campaign) => `
                <tr data-href="${campaignUrl(campaign.id)}">
                    <td class="fw-semibold">${escapeHtml(campaign.name)}</td>
                    <td>${channelBadge(campaign.channel)}</td>
                    <td>${escapeHtml(campaign.segment_name || '—')}</td>
                    <td>${statusPill(campaign.status, CAMPAIGN_STATUS_LABELS[campaign.status] || campaign.status)}</td>
                    <td>${pct(Number(campaign.read_count) || 0, Number(campaign.delivered_count) || 0)}</td>
                </tr>
            `).join('');
            if (!campaigns.length) {
                recentBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No hay campañas registradas.</td></tr>';
            }

            const channelCounts = campaigns.reduce((counts, campaign) => {
                counts[campaign.channel] = (counts[campaign.channel] || 0) + 1;
                return counts;
            }, {});
            channelList.innerHTML = Object.entries(channelCounts).length
                ? Object.entries(channelCounts).map(([channel, count]) => `
                    <div class="channel-row">${channelBadge(channel)}<span class="ms-auto small text-muted">${count} campaña${count === 1 ? '' : 's'}</span></div>
                `).join('')
                : '<p class="small text-muted mb-0">No hay campañas registradas.</p>';

            bindRowLinks();
        } catch (requestError) {
            const message = escapeHtml(requestError.message || 'No fue posible cargar las campañas.');
            kpiGrid.innerHTML = `<div class="col-12"><div class="alert alert-danger mb-0">No fue posible cargar los indicadores: ${message}</div></div>`;
            recentBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-4">${message}</td></tr>`;
            channelList.innerHTML = `<p class="small text-danger mb-0">${message}</p>`;
        }
    }

    function bindRowLinks(root = document) {
        root.querySelectorAll('tr[data-href]').forEach((row) => {
            if (row.dataset.linkBound) return;
            row.dataset.linkBound = '1';
            row.addEventListener('click', () => { window.location.href = row.dataset.href; });
        });
    }

    let campaignsPageItems = [];

    async function renderCampaignsPage() {
        const search = document.getElementById('filterSearch');
        const channel = document.getElementById('filterChannel');
        const status = document.getElementById('filterStatus');
        const clear = document.getElementById('clearFilters');
        const body = document.getElementById('campaignsTableBody');
        const empty = document.getElementById('campaignsEmpty');
        if (!search || !channel || !status || !clear || !body || !empty) return;

        const draw = () => {
            const q = (search.value || '').toLowerCase();
            const list = campaignsPageItems.filter((campaign) => {
                const hay = `${campaign.name || ''} ${campaign.segment_name || ''}`.toLowerCase();
                const okQ = !q || hay.includes(q);
                const okC = !channel.value || campaign.channel === channel.value;
                const okS = !status.value || campaign.status === status.value;
                return okQ && okC && okS;
            });
            body.innerHTML = list.map((campaign) => {
                const executionDate = campaign.scheduled_at || campaign.sent_at;
                const formattedDate = executionDate && !Number.isNaN(Date.parse(executionDate))
                    ? new Date(executionDate).toLocaleString('es-CO')
                    : (executionDate || '—');
                const statusLabel = CAMPAIGN_STATUS_LABELS[campaign.status] || campaign.status;
                return `
                <tr data-href="${campaignUrl(campaign.id)}">
                    <td class="fw-semibold">${escapeHtml(campaign.name)}</td>
                    <td>${channelBadge(campaign.channel)}</td>
                    <td>${escapeHtml(campaign.segment_name || '—')}</td>
                    <td>${escapeHtml(formattedDate)}</td>
                    <td>${pct(Number(campaign.read_count) || 0, Number(campaign.delivered_count) || 0)}</td>
                    <td>—</td>
                    <td>—</td>
                    <td>${statusPill(campaign.status, statusLabel)}</td>
                </tr>
                `;
            }).join('');
            empty.classList.toggle('d-none', list.length > 0);
            bindRowLinks();
        };
        if (!body.dataset.filtersBound) {
            body.dataset.filtersBound = '1';
            [search, channel, status].forEach((el) => {
                el.addEventListener(el === search ? 'input' : 'change', draw);
            });
            clear.addEventListener('click', () => {
                search.value = '';
                channel.value = '';
                status.value = '';
                draw();
            });
        }

        empty.classList.add('d-none');
        body.innerHTML = `
            <tr>
                <td colspan="8" class="text-center text-muted py-4">
                    <span class="spinner-border spinner-border-sm text-success me-2" role="status"></span>
                    Cargando listado de campañas…
                </td>
            </tr>
        `;
        try {
            campaignsPageItems = await fetchCampaigns();
            draw();
        } catch (requestError) {
            body.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">${escapeHtml(requestError.message || 'No fue posible cargar las campañas.')}</td></tr>`;
        }
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
        const body = escapeHtml(tpl.body || '').replace(/\{\{(\d+)\}\}/g, (placeholder, index) => {
            const value = vars[index];
            return value === undefined || value === null || value === ''
                ? placeholder
                : escapeHtml(value);
        });
        const header = tpl.header_type === 'text' && tpl.header_text
            ? `<div class="wa-header fw-semibold mb-2">${escapeHtml(tpl.header_text)}</div>`
            : '';
        const buttons = (tpl.buttons || [])
            .map((button) => `<span>${escapeHtml((button && button.text) ? button.text : button)}</span>`)
            .join('');
        if (channel === 'whatsapp') {
            return `<div class="wa-bubble">${header}${body}<span class="wa-meta">TdeA · ahora</span></div>${buttons ? `<div class="wa-buttons">${buttons}</div>` : ''}`;
        }
        return `<div class="wa-bubble" style="background:#fff">${header}${body}</div>`;
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
            pendingAudienceFile: null,
            audienceFile: null,
            audienceFileIsOriginal: false,
            personalizationColumns: [],
            personalizationValidation: null,
            personalizationReportOffsets: { valid: 0, rejected: 0 },
            templateLoadError: '',
        };

        document.addEventListener('change', (event) => {
            const input = event.target;
            if (
                input instanceof HTMLInputElement
                && input.type === 'file'
                && input.name === 'file'
                && input.closest('dialog[data-ap-dialog="create"]')
            ) {
                state.pendingAudienceFile = input.files && input.files[0]
                    ? input.files[0]
                    : null;
            }
        }, true);

        document.addEventListener('close', (event) => {
            if (
                event.target instanceof HTMLDialogElement
                && event.target.matches('dialog[data-ap-dialog="create"]')
            ) {
                state.pendingAudienceFile = null;
            }
        }, true);

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
                    if (state.pendingAudienceFile) {
                        state.audienceFile = state.pendingAudienceFile;
                        state.audienceFileIsOriginal = true;
                        state.pendingAudienceFile = null;
                    } else {
                        state.audienceFile = null;
                        state.audienceFileIsOriginal = false;
                        document.getElementById('personalizationFile').value = '';
                    }
                    updatePersonalizationFileSource();
                    resetPersonalizationValidation();
                    state.personalizationColumns = [];
                    document.getElementById('personalizationMapping').classList.add('d-none');
                    if (state.audienceFile) inspectPersonalizationFile();
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
            if (!templates.length) {
                const message = state.templateLoadError
                    ? 'No fue posible cargar las plantillas de Meta. Intenta nuevamente más tarde.'
                    : 'No hay plantillas aprobadas';
                grid.innerHTML = `<div class="alert ${state.templateLoadError ? 'alert-danger' : 'alert-info'} mb-0">${escapeHtml(message)}</div>`;
                return;
            }
            grid.innerHTML = templates.map((t) => `
                <button type="button" class="template-card ${String(t.id) === state.templateId ? 'is-selected' : ''}" data-tpl="${escapeHtml(t.id)}">
                    <div class="small text-muted mb-1">${escapeHtml(t.type)}</div>
                    <div class="fw-semibold">${escapeHtml(t.name)}</div>
                    ${t.isSample ? '<span class="template-sample">PLANTILLA DE PRUEBA META</span>' : ''}
                    <p class="small mb-0 mt-2 text-muted">${escapeHtml(t.body)}</p>
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
                state.templateLoadError = '';
                const results = Array.isArray(data.templates) ? data.templates : [];
                const approved = results.filter(
                    (template) => (
                        String(template.status || '').toUpperCase() === 'APPROVED'
                        && !template.is_sample
                        && String(template.name || '').trim().toLowerCase() !== 'hello_world'
                    )
                );
                templates = approved
                    .map((template) => ({
                        id: String(template.meta_id || ''),
                        name: template.name || '',
                        category: template.category || '',
                        language: template.language || 'es_CO',
                        type: TEMPLATE_CATEGORY_LABELS[template.category] || template.category || 'Plantilla',
                        body: template.body_text || '',
                        header_type: template.header_type || 'none',
                        header_text: template.header_text || '',
                        buttons: Array.isArray(template.buttons) ? template.buttons : [],
                        isSample: Boolean(template.is_sample),
                    }));
                renderTemplates();
            } catch (error) {
                state.templateLoadError = error.message || 'Error de conexión.';
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
            resetPersonalizationValidation();
            if (state.personalizationColumns.length) {
                renderPersonalizationColumns(state.personalizationColumns);
            }
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
            resetPersonalizationValidation();
            updatePreview();
        });

        document.getElementById('sendMode').addEventListener('change', (e) => {
            document.getElementById('scheduleAt').disabled = e.target.value !== 'later';
        });

        function currentTpl() {
            return templates.find((t) => String(t.id) === state.templateId);
        }

        function updatePreview() {
            const previewVars = { ...state.vars };
            const template = currentTpl();
            if (template && state.personalizationColumns.length) {
                for (const variable of new Set(extractVars(template.body).map((item) => String(Number(item))))) {
                    const mode = document.querySelector(`[data-variable-mode="${variable}"]`);
                    if (!mode) continue;
                    if (mode.value === 'column') {
                        const columnIndex = document.querySelector(`[data-variable-column="${variable}"]`)?.value;
                        const column = state.personalizationColumns.find(
                            (item) => String(item.index) === String(columnIndex),
                        );
                        if (column) previewVars[variable] = `{{${column.label}}}`;
                    } else {
                        const fixedValue = document.querySelector(`[data-variable-fixed="${variable}"]`)?.value;
                        previewVars[variable] = fixedValue || `{{${variable}}}`;
                    }
                }
            }
            document.getElementById('messagePreview').innerHTML = previewHtml(
                state.channel,
                template,
                previewVars,
            );
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
                state.personalizationValidation
                    ? `Excel validado: ${state.personalizationValidation.valid_count} destinatarios válidos de ${size.toLocaleString('es-CO')} en la audiencia.`
                    : `Audiencia estimada: ${size.toLocaleString('es-CO')} destinatarios.`;

            const validation = state.personalizationValidation;
            const confirmationPanel = document.getElementById('partialConfirmationPanel');
            confirmationPanel.classList.toggle(
                'd-none',
                !validation || !validation.rejected_count || !validation.valid_count,
            );
            document.getElementById('partialConfirmationText').textContent = validation && validation.rejected_count
                ? `${validation.rejected_count} filas se excluirán. La API volverá a comprobar la validación antes de crear destinatarios.`
                : '';
            document.getElementById('confirmPartialSend').checked = false;
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

        function selectedTemplateSnapshot(template) {
            return {
                name: template.name || '',
                language: template.language || 'es_CO',
                category: template.category || '',
                body_text: template.body || '',
                header_type: template.header_type || 'none',
                header_text: template.header_text || '',
                buttons: Array.isArray(template.buttons) ? template.buttons : [],
            };
        }

        function resetPersonalizationValidation() {
            state.personalizationValidation = null;
            state.personalizationReportOffsets = { valid: 0, rejected: 0 };
            const report = document.getElementById('personalizationReport');
            if (report) report.replaceChildren();
            const confirmation = document.getElementById('partialConfirmationPanel');
            if (confirmation) confirmation.classList.add('d-none');
            const confirmationCheckbox = document.getElementById('confirmPartialSend');
            if (confirmationCheckbox) confirmationCheckbox.checked = false;
        }

        function getPersonalizationFile() {
            return state.audienceFile || document.getElementById('personalizationFile').files[0] || null;
        }

        function updatePersonalizationFileSource() {
            const source = document.getElementById('personalizationFileSource');
            const uploadField = document.getElementById('personalizationUploadField');
            const file = getPersonalizationFile();
            const hasOriginal = Boolean(file && state.audienceFileIsOriginal);
            source.classList.toggle('d-none', !hasOriginal);
            source.textContent = hasOriginal
                ? `Se reutilizará el archivo original de la audiencia: ${file.name}`
                : '';
            uploadField.classList.toggle('d-none', hasOriginal || !state.segment);
        }

        function renderPersonalizationColumns(columns) {
            state.personalizationColumns = columns;
            const mapping = document.getElementById('personalizationMapping');
            const documentColumn = document.getElementById('personalizationDocumentColumn');
            const variableMappings = document.getElementById('personalizationVariableMappings');
            mapping.classList.remove('d-none');
            documentColumn.replaceChildren();
            variableMappings.replaceChildren();

            columns.forEach((column) => {
                const option = document.createElement('option');
                option.value = String(column.index);
                option.textContent = column.label;
                documentColumn.append(option);
            });

            const template = currentTpl();
            const variables = template ? [...new Set(extractVars(template.body).map((item) => String(Number(item))))] : [];
            variables.forEach((variable) => {
                const group = document.createElement('div');
                group.className = 'row g-2 align-items-end mb-2';

                const labelColumn = document.createElement('div');
                labelColumn.className = 'col-md-3';
                const label = document.createElement('label');
                label.className = 'form-label small mb-1';
                label.textContent = `Variable {{${variable}}}`;
                labelColumn.append(label);
                const assignedColumn = document.createElement('span');
                assignedColumn.className = 'form-text d-block';
                assignedColumn.dataset.variablePreview = variable;
                labelColumn.append(assignedColumn);

                const sourceColumn = document.createElement('div');
                sourceColumn.className = 'col-md-3';
                const source = document.createElement('select');
                source.className = 'form-select form-select-sm';
                source.dataset.variableMode = variable;
                source.setAttribute('aria-label', `Origen de la variable ${variable}`);
                source.innerHTML = '<option value="column">Columna Excel</option><option value="fixed">Valor fijo</option>';
                sourceColumn.append(source);

                const valueColumn = document.createElement('div');
                valueColumn.className = 'col-md-6';
                const columnSelect = document.createElement('select');
                columnSelect.className = 'form-select form-select-sm';
                columnSelect.dataset.variableColumn = variable;
                columns.forEach((column) => {
                    const option = document.createElement('option');
                    option.value = String(column.index);
                    option.textContent = column.label;
                    columnSelect.append(option);
                });
                const fixedInput = document.createElement('input');
                fixedInput.className = 'form-control form-control-sm d-none';
                fixedInput.type = 'text';
                fixedInput.dataset.variableFixed = variable;
                fixedInput.setAttribute('aria-label', `Valor fijo para la variable ${variable}`);
                fixedInput.placeholder = `Valor fijo para {{${variable}}}`;
                valueColumn.append(columnSelect, fixedInput);

                source.addEventListener('change', () => {
                    const isFixed = source.value === 'fixed';
                    columnSelect.classList.toggle('d-none', isFixed);
                    fixedInput.classList.toggle('d-none', !isFixed);
                    resetPersonalizationValidation();
                    updatePersonalizationPreviewLabel(variable);
                    updatePreview();
                });
                columnSelect.addEventListener('change', () => {
                    resetPersonalizationValidation();
                    updatePersonalizationPreviewLabel(variable);
                    updatePreview();
                });
                fixedInput.addEventListener('input', () => {
                    resetPersonalizationValidation();
                    updatePersonalizationPreviewLabel(variable);
                    updatePreview();
                });

                group.append(labelColumn, sourceColumn, valueColumn);
                variableMappings.append(group);
                updatePersonalizationPreviewLabel(variable);
            });
            updatePreview();
        }

        function updatePersonalizationPreviewLabel(variable) {
            const previewLabel = document.querySelector(`[data-variable-preview="${variable}"]`);
            const mode = document.querySelector(`[data-variable-mode="${variable}"]`);
            if (!previewLabel || !mode) return;
            if (mode.value === 'fixed') {
                const value = document.querySelector(`[data-variable-fixed="${variable}"]`).value.trim();
                previewLabel.textContent = value ? `Vista previa: ${value}` : 'Vista previa: valor fijo pendiente';
                return;
            }
            const selectedColumn = document.querySelector(`[data-variable-column="${variable}"]`);
            const column = state.personalizationColumns.find(
                (item) => String(item.index) === String(selectedColumn.value),
            );
            previewLabel.textContent = column
                ? `Vista previa: {{${column.label}}}`
                : 'Vista previa: selecciona una columna';
        }

        function renderPersonalizationReport(report) {
            const container = document.getElementById('personalizationReport');
            container.replaceChildren();
            const summary = document.createElement('p');
            summary.className = 'small fw-semibold mb-2';
            summary.textContent = `Filas válidas: ${report.valid_count}. Filas rechazadas: ${report.rejected_count}.`;
            container.append(summary);

            const pageSize = 100;
            [
                ['valid', 'Filas válidas', report.valid_rows || []],
                ['rejected', 'Filas rechazadas', report.rejected_rows || []],
            ].forEach(([kind, heading, rows]) => {
                if (!rows.length) return;
                const section = document.createElement('section');
                section.className = 'mb-3';
                const title = document.createElement('h4');
                title.className = 'small fw-bold';
                title.textContent = heading;
                section.append(title);

                const tableWrap = document.createElement('div');
                tableWrap.className = 'table-responsive';
                const table = document.createElement('table');
                table.className = 'table table-sm align-middle';
                const head = document.createElement('thead');
                const headRow = document.createElement('tr');
                const headers = kind === 'valid'
                    ? ['Fila', 'Documento', 'Contacto', 'Vista previa']
                    : ['Fila', 'Documento', 'Motivo'];
                headers.forEach((text) => {
                    const cell = document.createElement('th');
                    cell.scope = 'col';
                    cell.textContent = text;
                    headRow.append(cell);
                });
                head.append(headRow);
                const body = document.createElement('tbody');
                const start = state.personalizationReportOffsets[kind];
                const page = rows.slice(start, start + pageSize);
                page.forEach((item) => {
                    const row = document.createElement('tr');
                    const values = kind === 'valid'
                        ? [item.row, item.document_number, item.contact_name, item.message]
                        : [item.row, item.document_number || '—', item.reason];
                    values.forEach((value) => {
                        const cell = document.createElement('td');
                        cell.textContent = value == null ? '' : String(value);
                        row.append(cell);
                    });
                    body.append(row);
                });
                table.append(head, body);
                tableWrap.append(table);
                section.append(tableWrap);

                if (start + pageSize < rows.length) {
                    const more = document.createElement('button');
                    more.type = 'button';
                    more.className = 'btn btn-outline-secondary btn-sm';
                    more.textContent = `Mostrar más (${rows.length - start - pageSize} restantes)`;
                    more.addEventListener('click', () => {
                        state.personalizationReportOffsets[kind] += pageSize;
                        renderPersonalizationReport(report);
                    });
                    section.append(more);
                }
                container.append(section);
            });
        }

        document.getElementById('personalizationFile').addEventListener('change', () => {
            const input = document.getElementById('personalizationFile');
            state.audienceFile = input.files[0] || null;
            state.audienceFileIsOriginal = false;
            updatePersonalizationFileSource();
            resetPersonalizationValidation();
            state.personalizationColumns = [];
            document.getElementById('personalizationMapping').classList.add('d-none');
            updatePreview();
        });

        async function inspectPersonalizationFile(showToast = true) {
            const file = getPersonalizationFile();
            if (!file) {
                if (showToast) toast('Selecciona un archivo .xlsx.');
                return;
            }
            const button = document.getElementById('inspectPersonalizationFile');
            button.disabled = true;
            try {
                const form = new FormData();
                form.append('file', file);
                const response = await fetch('/campanas/api/campaigns/personalization/inspect/', {
                    method: 'POST',
                    headers: {
                        Accept: 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    credentials: 'same-origin',
                    body: form,
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || Object.values(data).flat().join(' ') || 'No se pudieron leer las columnas.');
                }
                renderPersonalizationColumns(data.columns || []);
                if (showToast) toast('Columnas del Excel cargadas.');
            } catch (error) {
                console.error('Error al inspeccionar Excel:', error);
                if (showToast) toast(error.message || 'No se pudo leer el archivo Excel.');
            } finally {
                button.disabled = false;
            }
        }

        document.getElementById('inspectPersonalizationFile').addEventListener('click', () => {
            inspectPersonalizationFile();
        });

        document.getElementById('personalizationDocumentColumn').addEventListener('change', resetPersonalizationValidation);

        document.getElementById('validatePersonalization').addEventListener('click', async (event) => {
            const file = getPersonalizationFile();
            const template = currentTpl();
            if (!file || !template || !state.segment) {
                return toast('Selecciona el Excel, la audiencia y una plantilla antes de validar.');
            }
            if (!state.personalizationColumns.length) {
                return toast('Lee primero las columnas del archivo.');
            }

            const variables = [...new Set(extractVars(template.body).map((item) => String(Number(item))))];
            const mappings = {};
            for (const variable of variables) {
                const mode = document.querySelector(`[data-variable-mode="${variable}"]`);
                if (!mode) return toast(`Configura el origen de la variable {{${variable}}}.`);
                mappings[variable] = mode.value === 'column'
                    ? {
                        source: 'column',
                        column: Number(document.querySelector(`[data-variable-column="${variable}"]`).value),
                    }
                    : {
                        source: 'fixed',
                        value: document.querySelector(`[data-variable-fixed="${variable}"]`).value,
                    };
            }

            const button = event.currentTarget;
            button.disabled = true;
            try {
                const form = new FormData();
                form.append('file', file);
                form.append('segment', String(state.segment.id));
                form.append('template', state.templateId);
                form.append('template_name', template.name || '');
                form.append('template_language', template.language || 'es_CO');
                form.append('template_snapshot', JSON.stringify(selectedTemplateSnapshot(template)));
                form.append('default_params', JSON.stringify(state.vars));
                form.append('document_column', document.getElementById('personalizationDocumentColumn').value);
                form.append('variable_mappings', JSON.stringify(mappings));

                const response = await fetch('/campanas/api/campaigns/personalization/validate/', {
                    method: 'POST',
                    headers: {
                        Accept: 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    credentials: 'same-origin',
                    body: form,
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || Object.values(data).flat().join(' ') || 'No se pudo validar el archivo.');
                }
                state.personalizationValidation = data;
                renderPersonalizationReport(data);
                fillReview();
                toast('Validación del Excel completada.');
            } catch (error) {
                console.error('Error al validar personalización:', error);
                toast(error.message || 'No se pudo validar el archivo.');
            } finally {
                button.disabled = false;
            }
        });

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
                if (getPersonalizationFile() && !state.personalizationValidation) {
                    return toast('Valida el Excel o quita el archivo antes de continuar.');
                }
                if (state.personalizationValidation && !state.personalizationValidation.valid_count) {
                    return toast('El archivo no tiene filas válidas para la campaña.');
                }
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
            const personalization = state.personalizationValidation;
            const confirmPartial = document.getElementById('confirmPartialSend').checked;
            if (personalization && personalization.rejected_count && !confirmPartial) {
                toast('Confirma expresamente que continuarás solo con las filas válidas.');
                return;
            }

            try {
                const payload = {
                    name: name,
                    template: state.templateId,
                    template_name: selectedTemplate.name || '',
                    template_language: selectedTemplate.language || 'es_CO',
                    template_snapshot: selectedTemplateSnapshot(selectedTemplate),
                    segment: state.segment.id,
                    default_params: state.vars,
                };

                if (personalization) {
                    payload.personalization_validation_id = personalization.validation_id;
                    payload.confirm_partial = confirmPartial;
                }

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
                    toast(error.detail || Object.values(error).flat().join(' ') || 'No se pudo crear la campaña en el backend.');
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
                            <label class="field-label" for="templateHeaderType">Encabezado opcional</label>
                            <select id="templateHeaderType" class="field-select">
                                <option value="none">Ninguno</option>
                                <option value="text">Texto estático</option>
                                <option value="image">Imagen</option>
                                <option value="video">Video</option>
                                <option value="document">Documento PDF</option>
                            </select>
                            <div id="templateHeaderFields" class="template-header-fields d-none">
                                <div id="templateHeaderTextField" class="field-group d-none">
                                    <label class="field-label" for="templateHeaderText">Texto del encabezado</label>
                                    <input id="templateHeaderText" class="field-input" maxlength="60">
                                </div>
                                <div id="templateHeaderFileField" class="field-group d-none">
                                    <label class="field-label" for="templateHeaderFile">Archivo</label>
                                    <input id="templateHeaderFile" class="field-input" type="file">
                                    <span id="templateHeaderFileName" class="template-file-name d-none"></span>
                                    <div id="templateHeaderFileError" class="template-field-error d-none" role="alert"></div>
                                </div>
                                <p id="templateTextHeaderNote" class="template-text-header-note">
                                    Máximo 60 caracteres, sin variables ni caracteres especiales de Markdown.
                                </p>
                                <div id="templateHeaderMediaWarning" class="template-local-warning d-none" role="note">
                                    Los encabezados multimedia todavía no se pueden guardar ni enviar a Meta. Selecciona «Ninguno» o «Texto estático».
                                </div>
                            </div>
                        </div>
                        <div class="field-group">
                            <label class="field-label" for="templateBodyInput">Contenido del mensaje</label>
                            <textarea id="templateBodyInput" class="field-textarea" rows="4"></textarea>
                        </div>
                        <div id="templateVariablesBox"></div>
                        <section class="template-button-editor" aria-labelledby="templateButtonSectionTitle">
                            <div class="template-button-editor-head">
                                <h4 id="templateButtonSectionTitle">Botón URL opcional</h4>
                                <button type="button" class="btn btn-outline-success btn-sm" id="templateAddButtonToggle">
                                    <i class="bi bi-plus-lg me-1"></i> Agregar botón
                                </button>
                            </div>
                            <p class="template-button-count" id="templateButtonCount">0 de 3 botones</p>
                            <div id="templateButtonList" class="template-button-list"></div>
                            <div id="templateButtonForm" class="template-button-form d-none">
                                <div class="template-fields">
                                    <div class="field-group">
                                        <label class="field-label" for="templateButtonText">Nombre del botón</label>
                                        <input id="templateButtonText" class="field-input" maxlength="25" autocomplete="off" required aria-describedby="templateButtonTextError">
                                        <div id="templateButtonTextError" class="template-field-error d-none" role="alert"></div>
                                    </div>
                                    <div class="field-group">
                                        <label class="field-label" for="templateButtonUrl">URL del botón</label>
                                        <input id="templateButtonUrl" class="field-input" type="url" inputmode="url" placeholder="https://ejemplo.com" autocomplete="url" required aria-describedby="templateButtonUrlError">
                                        <div id="templateButtonUrlError" class="template-field-error d-none" role="alert"></div>
                                    </div>
                                </div>
                                <div class="template-button-form-actions">
                                    <button type="button" class="btn btn-outline-secondary btn-sm" id="templateButtonCancel">Cancelar</button>
                                    <button type="button" class="btn btn-success btn-sm" id="templateButtonSave">Agregar</button>
                                </div>
                            </div>
                        </section>
                        <section class="template-live-preview" aria-labelledby="templatePreviewTitle">
                            <h4 id="templatePreviewTitle">Vista previa local</h4>
                            <div class="template-preview-phone">
                                <div class="template-preview-message" id="templatePreviewMessage" aria-live="polite"></div>
                            </div>
                            <p class="template-preview-note">Los valores de ejemplo y archivos se muestran solo en este navegador; no se envían al servidor desde la vista previa.</p>
                        </section>
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
        const headerTypeInput = document.getElementById('templateHeaderType');
        const headerFields = document.getElementById('templateHeaderFields');
        const headerTextField = document.getElementById('templateHeaderTextField');
        const headerTextInput = document.getElementById('templateHeaderText');
        const headerTextNote = document.getElementById('templateTextHeaderNote');
        const headerMediaWarning = document.getElementById('templateHeaderMediaWarning');
        const headerFileField = document.getElementById('templateHeaderFileField');
        const headerFileInput = document.getElementById('templateHeaderFile');
        const headerFileName = document.getElementById('templateHeaderFileName');
        const headerFileError = document.getElementById('templateHeaderFileError');
        const buttonToggle = document.getElementById('templateAddButtonToggle');
        const buttonCount = document.getElementById('templateButtonCount');
        const buttonList = document.getElementById('templateButtonList');
        const buttonForm = document.getElementById('templateButtonForm');
        const buttonTextInput = document.getElementById('templateButtonText');
        const buttonUrlInput = document.getElementById('templateButtonUrl');
        const buttonTextError = document.getElementById('templateButtonTextError');
        const buttonUrlError = document.getElementById('templateButtonUrlError');
        const buttonSave = document.getElementById('templateButtonSave');
        const buttonCancel = document.getElementById('templateButtonCancel');
        const previewMessage = document.getElementById('templatePreviewMessage');
        const templateButtons = [];
        let editingButtonIndex = null;
        let headerObjectUrl = '';
        let headerFile = null;

        const releaseHeaderObjectUrl = () => {
            if (headerObjectUrl) {
                URL.revokeObjectURL(headerObjectUrl);
                headerObjectUrl = '';
            }
        };

        const clearHeaderFile = () => {
            releaseHeaderObjectUrl();
            headerFile = null;
            headerFileInput.value = '';
            headerFileName.textContent = '';
            headerFileName.classList.add('d-none');
            headerFileError.textContent = '';
            headerFileError.classList.add('d-none');
        };

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

        function renderTemplatePreview() {
            previewMessage.replaceChildren();
            const headerType = headerTypeInput.value;
            if (headerType !== 'none') {
                const header = document.createElement('div');
                header.className = 'template-preview-header';
                if (headerType === 'text') {
                    header.textContent = headerTextInput.value.trim() || 'Texto del encabezado';
                } else if (headerObjectUrl && headerType === 'image') {
                    const image = document.createElement('img');
                    image.src = headerObjectUrl;
                    image.alt = 'Vista previa del encabezado de imagen';
                    header.append(image);
                } else if (headerObjectUrl && headerType === 'video') {
                    const video = document.createElement('video');
                    video.controls = true;
                    video.preload = 'metadata';
                    video.src = headerObjectUrl;
                    video.setAttribute('aria-label', 'Vista previa local del video');
                    const extension = headerFile?.name.split('.').pop().toLowerCase();
                    const mimeType = headerFile?.type || (extension === 'mov' ? 'video/quicktime' : 'video/mp4');
                    if (!video.canPlayType(mimeType)) {
                        const message = document.createElement('span');
                        message.textContent = 'El navegador no puede reproducir este formato; el archivo sigue siendo local.';
                        header.append(message);
                    } else {
                        header.append(video);
                    }
                } else if (headerType === 'document') {
                    header.classList.add('template-preview-header--document');
                    const icon = document.createElement('i');
                    icon.className = 'bi bi-file-earmark-pdf';
                    icon.setAttribute('aria-hidden', 'true');
                    const label = document.createElement('span');
                    label.textContent = headerFile?.name || 'Documento PDF';
                    header.append(icon, label);
                } else {
                    header.textContent = headerType === 'image' ? 'Imagen sin seleccionar' : 'Video sin seleccionar';
                }
                previewMessage.append(header);
            }

            const body = document.createElement('div');
            body.className = 'template-preview-body';
            body.textContent = (bodyInput.value || 'Escribe el contenido del mensaje.')
                .replace(/\{\{(\d+)\}\}/g, (_, number) => `Ejemplo ${number}`);
            previewMessage.append(body);

            if (templateButtons.length) {
                const buttonsContainer = document.createElement('div');
                buttonsContainer.className = 'template-preview-buttons';

                templateButtons.forEach((item) => {
                    const button = document.createElement('a');
                    button.className = 'template-preview-button';
                    button.textContent = typeof item?.text === 'string' ? item.text : '';

                    if (isValidButton(item)) {
                        const destination = new URL(item.url.trim());
                        button.href = destination.href;
                        button.target = '_blank';
                        button.rel = 'noopener noreferrer';
                        button.setAttribute(
                            'aria-label',
                            `Abrir enlace externo: ${item.text.trim()}`
                        );
                        const icon = document.createElement('i');
                        icon.className = 'bi bi-box-arrow-up-right';
                        icon.setAttribute('aria-hidden', 'true');
                        button.append(icon);
                    } else {
                        button.setAttribute('aria-disabled', 'true');
                        button.setAttribute(
                            'aria-label',
                            `${button.textContent || 'Enlace'} no disponible`
                        );
                    }

                    buttonsContainer.append(button);
                });

                previewMessage.append(buttonsContainer);
            }
        }

        function updateHeaderFields() {
            const headerType = headerTypeInput.value;
            headerFields.classList.toggle('d-none', headerType === 'none');
            headerTextField.classList.toggle('d-none', headerType !== 'text');
            headerTextNote.classList.toggle('d-none', headerType !== 'text');
            headerFileField.classList.toggle('d-none', !['image', 'video', 'document'].includes(headerType));
            headerMediaWarning.classList.toggle(
                'd-none',
                !['image', 'video', 'document'].includes(headerType)
            );
            headerFileInput.accept = {
                image: '.jpg,.jpeg,.png',
                video: '.mp4,.mov',
                document: '.pdf,application/pdf',
            }[headerType] || '';
            clearHeaderFile();
            renderTemplatePreview();
        }

        function renderTemplateButtons() {
            buttonList.replaceChildren();
            templateButtons.forEach((item, index) => {
                const row = document.createElement('div');
                row.className = 'template-button-row';
                const description = document.createElement('span');
                description.textContent = `${item.text || 'Botón'}${item.url ? ` · ${item.url}` : ''}`;

                const actions = document.createElement('div');
                actions.className = 'template-button-row-actions';
                const edit = document.createElement('button');
                edit.type = 'button';
                edit.className = 'btn btn-outline-secondary btn-sm';
                edit.dataset.buttonAction = 'edit';
                edit.dataset.buttonIndex = String(index);
                edit.textContent = 'Editar';
                edit.setAttribute('aria-label', `Editar botón ${item.text || index + 1}`);
                const remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'btn btn-outline-danger btn-sm';
                remove.dataset.buttonAction = 'remove';
                remove.dataset.buttonIndex = String(index);
                remove.textContent = 'Eliminar';
                remove.setAttribute('aria-label', `Eliminar botón ${item.text || index + 1}`);
                actions.append(edit, remove);
                row.append(description, actions);
                buttonList.append(row);
            });
            buttonCount.textContent = `${templateButtons.length} de 3 botones`;
            buttonToggle.disabled = (templateButtons.length >= 3 && editingButtonIndex === null)
                || !buttonForm.classList.contains('d-none');
            renderTemplatePreview();
        }

        function clearButtonErrors() {
            [[buttonTextError, buttonTextInput], [buttonUrlError, buttonUrlInput]].forEach(([error, input]) => {
                error.textContent = '';
                error.classList.add('d-none');
                input.removeAttribute('aria-invalid');
            });
        }

        function closeButtonForm() {
            editingButtonIndex = null;
            buttonForm.classList.add('d-none');
            buttonTextInput.value = '';
            buttonUrlInput.value = '';
            buttonSave.textContent = 'Agregar';
            clearButtonErrors();
            renderTemplateButtons();
        }

        function showButtonFieldError(errorElement, input, message) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
            input.setAttribute('aria-invalid', 'true');
        }

        function validateButtonFields() {
            clearButtonErrors();
            const text = buttonTextInput.value.trim();
            const rawUrl = buttonUrlInput.value.trim();
            let url = null;
            if (!text) {
                showButtonFieldError(buttonTextError, buttonTextInput, 'Escribe el nombre del botón.');
            }
            try {
                url = new URL(rawUrl);
                if (url.protocol !== 'https:' || !url.hostname || url.username || url.password) {
                    url = null;
                }
            } catch {
                url = null;
            }
            if (!url) {
                showButtonFieldError(buttonUrlError, buttonUrlInput, 'Ingresa una URL absoluta HTTPS sin credenciales.');
            }
            if (!text || !url) return null;
            return { text, url: url.href };
        }

        function isValidButton(item) {
            if (!item || typeof item.text !== 'string' || !item.text.trim() || typeof item.url !== 'string') {
                return false;
            }
            try {
                const url = new URL(item.url.trim());
                return url.protocol === 'https:' && Boolean(url.hostname) && !url.username && !url.password;
            } catch {
                return false;
            }
        }

        function validateHeaderFile(file, headerType) {
            const extension = file.name.split('.').pop().toLowerCase();
            const allowed = {
                image: { extensions: ['jpg', 'jpeg', 'png'], mimeTypes: ['image/jpeg', 'image/png'] },
                video: { extensions: ['mp4', 'mov'], mimeTypes: ['video/mp4', 'video/quicktime'] },
                document: { extensions: ['pdf'], mimeTypes: ['application/pdf'] },
            }[headerType];
            if (!allowed || !allowed.extensions.includes(extension)) {
                return `Selecciona ${headerType === 'image' ? 'una imagen JPG, JPEG o PNG' : headerType === 'video' ? 'un video MP4 o MOV' : 'un documento PDF'}.`;
            }
            if (file.type && !allowed.mimeTypes.includes(file.type.toLowerCase())) {
                return 'El tipo de archivo no coincide con la extensión permitida.';
            }
            return '';
        }

        bodyInput.addEventListener('input', () => {
            renderVariables();
            renderTemplatePreview();
        });
        headerTypeInput.addEventListener('change', updateHeaderFields);
        headerTextInput.addEventListener('input', renderTemplatePreview);
        headerFileInput.addEventListener('change', () => {
            const file = headerFileInput.files[0];
            releaseHeaderObjectUrl();
            headerFile = null;
            headerFileName.textContent = '';
            headerFileName.classList.add('d-none');
            headerFileError.textContent = '';
            headerFileError.classList.add('d-none');
            if (!file) {
                renderTemplatePreview();
                return;
            }
            const error = validateHeaderFile(file, headerTypeInput.value);
            if (error) {
                headerFileError.textContent = error;
                headerFileError.classList.remove('d-none');
                headerFileInput.value = '';
                renderTemplatePreview();
                return;
            }
            headerFile = file;
            headerFileInput.value = '';
            headerObjectUrl = URL.createObjectURL(file);
            headerFileName.textContent = file.name;
            headerFileName.classList.remove('d-none');
            renderTemplatePreview();
        });

        buttonToggle.addEventListener('click', () => {
            if (templateButtons.length >= 3 && editingButtonIndex === null) return;
            editingButtonIndex = null;
            buttonTextInput.value = '';
            buttonUrlInput.value = '';
            buttonSave.textContent = 'Agregar';
            clearButtonErrors();
            buttonForm.classList.remove('d-none');
            buttonToggle.disabled = true;
            buttonTextInput.focus();
        });
        buttonCancel.addEventListener('click', closeButtonForm);
        buttonSave.addEventListener('click', () => {
            const value = validateButtonFields();
            if (!value) return;
            if (editingButtonIndex === null) {
                if (templateButtons.length >= 3) return;
                templateButtons.push(value);
            } else {
                templateButtons[editingButtonIndex] = value;
            }
            closeButtonForm();
        });
        buttonList.addEventListener('click', (event) => {
            const action = event.target.closest('[data-button-action]');
            if (!action || !buttonList.contains(action)) return;
            const index = Number(action.dataset.buttonIndex);
            if (!Number.isInteger(index) || index < 0 || index >= templateButtons.length) return;
            if (action.dataset.buttonAction === 'edit') {
                editingButtonIndex = index;
                buttonTextInput.value = templateButtons[index].text;
                buttonUrlInput.value = templateButtons[index].url;
                buttonSave.textContent = 'Guardar cambios';
                clearButtonErrors();
                buttonForm.classList.remove('d-none');
                buttonToggle.disabled = true;
                buttonTextInput.focus();
            } else if (action.dataset.buttonAction === 'remove') {
                templateButtons.splice(index, 1);
                if (editingButtonIndex === index) closeButtonForm();
                else {
                    if (editingButtonIndex !== null && index < editingButtonIndex) editingButtonIndex -= 1;
                    renderTemplateButtons();
                }
            }
        });

        dialog.addEventListener('close', () => {
            clearHeaderFile();
            headerTypeInput.value = 'none';
            headerTextInput.value = '';
            updateHeaderFields();
        });

        function openDialog(nextMode, options = {}) {
            mode = nextMode;
            editingId = options.id || null;
            dialogError.classList.add('d-none');
            dialogError.textContent = '';

            nameInput.value = options.name || '';
            categoryInput.value = options.category || 'utility';
            bodyInput.value = options.bodyText || '';
            templateButtons.splice(0, templateButtons.length, ...(
                Array.isArray(options.buttons)
                    ? options.buttons
                        .filter((item) => item && typeof item === 'object')
                        .map((item) => ({
                            text: typeof item.text === 'string' ? item.text : '',
                            url: typeof item.url === 'string' ? item.url : '',
                        }))
                    : []
            ));
            buttonForm.classList.add('d-none');
            editingButtonIndex = null;
            headerTypeInput.value = ['none', 'text', 'image', 'video', 'document'].includes(options.headerType)
                ? options.headerType
                : 'none';
            headerTextInput.value = options.headerText || '';
            updateHeaderFields();
            renderTemplateButtons();

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
            saveDraftBtn.disabled = false;
            saveMetaBtn.disabled = false;
            buttonToggle.disabled = templateButtons.length >= 3;

            saveMetaBtn.textContent = editingMeta
                ? 'Guardar cambios'
                : (editingDraft ? 'Enviar a Meta' : 'Guardar y enviar a Meta');

            renderVariables(options.variableTypes || {});
            renderTemplatePreview();
            dialog.showModal();
        }

        function collectPayload() {
            const headerType = headerTypeInput.value;
            if (['image', 'video', 'document'].includes(headerType)) {
                throw new Error('Los encabezados multimedia no se pueden guardar ni enviar todavía. Selecciona «Ninguno» o «Texto estático».');
            }
            const headerText = headerType === 'text' ? headerTextInput.value.trim() : '';
            if (headerType === 'text' && !headerText) {
                throw new Error('Escribe el texto del encabezado.');
            }
            if (headerText.length > 60) {
                throw new Error('El encabezado no puede superar 60 caracteres.');
            }
            if (headerText.includes('{{') || headerText.includes('}}')) {
                throw new Error('El encabezado estático no admite variables.');
            }
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
            for (const [index, item] of templateButtons.entries()) {
                if (!isValidButton(item)) {
                    throw new Error(`El botón ${index + 1} debe tener un nombre y una URL HTTPS válida sin credenciales.`);
                }
            }
            if (templateButtons.length > 3) {
                throw new Error('Una plantilla admite máximo tres botones URL. Elimina los adicionales antes de guardar.');
            }
            return {
                name,
                category: categoryInput.value,
                body_text: bodyText,
                variable_types: variableTypes,
                header_type: headerType,
                header_text: headerText,
                buttons: templateButtons.map((item) => ({ text: item.text.trim(), url: item.url.trim() })),
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
                    buttons: payload.buttons,
                    header_type: payload.header_type,
                    header_text: payload.header_text,
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
                        headerType: template.header_type,
                        headerText: template.header_text,
                        buttons: template.buttons,
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
                        headerType: template.header_type,
                        headerText: template.header_text,
                        buttons: template.buttons,
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
                    headerType: template.header_type,
                    headerText: template.header_text,
                    buttons: template.buttons,
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

    return {
        renderDashboard,
        renderCampaignCards,
        renderCampaignsPage,
        renderCampaignDetail,
        initWizard,
        initAudiencesPage: () => initWizard(true),
        initTemplatesPage,
    };
})();
