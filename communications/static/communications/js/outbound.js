const OutboundUI = (() => {
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

    function campaignUrl(id) {
        return `/communications/campanas/detalle/?id=${encodeURIComponent(id)}`;
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

    function renderCampaignDetail() {
        const id = new URLSearchParams(window.location.search).get('id');
        const campaign = loadCampaigns().find((c) => c.id === id);
        const root = document.getElementById('campaignDetailRoot');
        if (!campaign) {
            root.innerHTML = '<div class="alert alert-warning">No se encontró la campaña. Vuelve al listado.</div>';
            return;
        }
        const templates = TEMPLATES[campaign.channel] || [];
        const tpl = templates.find((t) => t.id === campaign.templateId) || templates[0];
        root.innerHTML = `
            <div class="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-4">
                <div>
                    <h2 class="h4 mb-1">${campaign.name}</h2>
                    <div class="d-flex flex-wrap gap-2">${channelBadge(campaign.channel)} ${statusPill(campaign.status)}</div>
                </div>
            </div>
            <div class="row g-3 mb-4">
                ${[
                    ['Enviados', campaign.sent],
                    ['Entregados', campaign.delivered],
                    ['Lectura', pct(campaign.read, campaign.delivered)],
                    ['Clics', pct(campaign.clicks, campaign.delivered)],
                    ['Respuestas', campaign.replies],
                ].map(([label, value]) => `<div class="col"><div class="kpi-card"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div></div></div>`).join('')}
            </div>
            <div class="row g-4">
                <div class="col-lg-7">
                    <div class="card outbound-card">
                        <div class="card-body">
                            <h3 class="h6">Audiencias</h3>
                            <p>${campaign.segments.join(', ')}</p>
                            <h3 class="h6">Ejecución</h3>
                            <p class="mb-0">${campaign.executedAt} · tipo ${campaign.type}</p>
                        </div>
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="card outbound-card">
                        <div class="card-body">
                            <h3 class="h6 text-uppercase text-muted">Plantilla</h3>
                            <div class="phone-frame"><div class="phone-screen">${previewHtml(campaign.channel, tpl)}</div></div>
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
        const state = {
            step: 1,
            channel: 'whatsapp',
            include: [],
            exclude: [],
            templateId: '',
            vars: {},
        };
        const picker = document.getElementById('channelPicker');
        picker.innerHTML = Object.entries(CHANNELS).map(([key, meta]) => `
            <button type="button" class="channel-option ${key === state.channel ? 'is-selected' : ''}" data-channel="${key}">
                <span class="channel-icon ${key} mx-auto mb-2"><i class="bi ${meta.icon}"></i></span>
                <div class="fw-semibold">${meta.label}</div>
            </button>
        `).join('');

        const includeBox = document.getElementById('includeSegments');
        const excludeBox = document.getElementById('excludeSegments');
        includeBox.innerHTML = SEGMENTS.filter((s) => s.id !== 'opt-out').map((s) => chip(s, 'include')).join('');
        excludeBox.innerHTML = SEGMENTS.map((s) => chip(s, 'exclude')).join('');

        function chip(s, kind) {
            return `<button type="button" class="segment-chip" data-kind="${kind}" data-id="${s.id}">${s.name} · ${s.size.toLocaleString('es-CO')}</button>`;
        }

        function fillAccounts() {
            document.getElementById('senderAccount').innerHTML = `<option>${CHANNELS[state.channel].account}</option>`;
        }
        fillAccounts();

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

        document.querySelectorAll('.segment-chip').forEach((btn) => {
            btn.addEventListener('click', () => {
                const kind = btn.dataset.kind;
                const id = btn.dataset.id;
                const list = kind === 'include' ? state.include : state.exclude;
                const idx = list.indexOf(id);
                if (idx >= 0) list.splice(idx, 1);
                else if (kind === 'include' && list.length >= 5) {
                    toast('Puedes incluir hasta 5 audiencias.');
                    return;
                } else list.push(id);
                btn.classList.toggle('is-selected');
            });
        });

        function renderTemplates() {
            const grid = document.getElementById('templateGrid');
            const list = TEMPLATES[state.channel] || [];
            grid.innerHTML = list.map((t) => `
                <button type="button" class="template-card ${t.id === state.templateId ? 'is-selected' : ''}" data-tpl="${t.id}">
                    <div class="small text-muted mb-1">${t.type}</div>
                    <div class="fw-semibold">${t.name}</div>
                    <p class="small mb-0 mt-2 text-muted">${t.body}</p>
                </button>
            `).join('');
        }

        document.getElementById('templateGrid').addEventListener('click', (e) => {
            const card = e.target.closest('[data-tpl]');
            if (!card) return;
            state.templateId = card.dataset.tpl;
            document.querySelectorAll('.template-card').forEach((el) => el.classList.toggle('is-selected', el === card));
            const tpl = (TEMPLATES[state.channel] || []).find((t) => t.id === state.templateId);
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
            return (TEMPLATES[state.channel] || []).find((t) => t.id === state.templateId);
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
            const includeNames = SEGMENTS.filter((s) => state.include.includes(s.id)).map((s) => s.name);
            const size = SEGMENTS.filter((s) => state.include.includes(s.id)).reduce((a, s) => a + s.size, 0);
            const tpl = currentTpl();
            document.getElementById('reviewList').innerHTML = `
                <dt class="col-sm-4">Nombre</dt><dd class="col-sm-8">${name}</dd>
                <dt class="col-sm-4">Canal</dt><dd class="col-sm-8">${CHANNELS[state.channel].label}</dd>
                <dt class="col-sm-4">Tipo</dt><dd class="col-sm-8">${type}</dd>
                <dt class="col-sm-4">Audiencias</dt><dd class="col-sm-8">${includeNames.join(', ') || 'Ninguna'}</dd>
                <dt class="col-sm-4">Plantilla</dt><dd class="col-sm-8">${tpl ? tpl.name : 'Sin seleccionar'}</dd>
            `;
            document.getElementById('costEstimate').textContent = `Audiencia estimada: ${size.toLocaleString('es-CO')} destinatarios (dato de demostración).`;
        }

        document.getElementById('wizardBack').addEventListener('click', () => showStep(Math.max(1, state.step - 1)));
        document.getElementById('wizardNext').addEventListener('click', () => {
            if (state.step === 1) {
                if (!document.getElementById('campaignName').value.trim()) return toast('Escribe un nombre de campaña.');
                if (!state.include.length) return toast('Selecciona al menos una audiencia.');
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

        function launch() {
            const sendMode = document.getElementById('sendMode').value;
            const scheduleAt = document.getElementById('scheduleAt').value;
            const list = loadCampaigns();
            const includeNames = SEGMENTS.filter((s) => state.include.includes(s.id)).map((s) => s.name);
            const size = SEGMENTS.filter((s) => state.include.includes(s.id)).reduce((a, s) => a + s.size, 0);
            const campaign = {
                id: `c${Date.now()}`,
                name: document.getElementById('campaignName').value.trim(),
                channel: state.channel,
                type: document.getElementById('campaignType').value,
                segments: includeNames,
                executedAt: sendMode === 'later' && scheduleAt ? scheduleAt.replace('T', ' ') : new Date().toISOString().slice(0, 16).replace('T', ' '),
                status: sendMode === 'later' ? 'programada' : 'enviada',
                sent: sendMode === 'later' ? 0 : size,
                delivered: sendMode === 'later' ? 0 : Math.round(size * 0.98),
                read: sendMode === 'later' ? 0 : Math.round(size * 0.72),
                clicks: sendMode === 'later' ? 0 : Math.round(size * 0.18),
                replies: sendMode === 'later' ? 0 : Math.round(size * 0.09),
                templateId: state.templateId,
            };
            list.unshift(campaign);
            saveCampaigns(list);
            toast(sendMode === 'later' ? 'Campaña programada (demostración).' : 'Campaña lanzada (demostración).');
            window.location.href = campaignUrl(campaign.id);
        }

        const preset = new URLSearchParams(window.location.search).get('segment');
        if (preset) {
            const btn = document.querySelector(`[data-kind="include"][data-id="${preset}"]`);
            if (btn) btn.click();
        }
        showStep(1);
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
                        <a class="btn btn-entry mt-auto" href="/communications/campanas/nueva/?segment=${s.id}">Iniciar campaña</a>
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

    return { renderDashboard, renderCampaignsPage, renderCampaignDetail, initWizard, renderSegments, renderLogs };
})();
