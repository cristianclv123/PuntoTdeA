import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import test from 'node:test';

const scriptPath = fileURLToPath(
    new URL('../static/communications/js/outbound.js', import.meta.url),
);
const source = readFileSync(scriptPath, 'utf8');

function loadUI(context) {
    const normalizedSource = source.replace(/\r\n/g, '\n');
    const testableSource = normalizedSource.replace(
        '    return {\n        renderDashboard,',
        '    return {\n        channelBadge,\n        statusPill,\n        renderDashboard,',
    );
    assert.ok(
        testableSource.includes('        channelBadge,\n        statusPill,'),
        'el harness debe exponer los helpers privados solo durante la prueba',
    );
    vm.runInNewContext(`${testableSource}\nglobalThis.OutboundUIUnderTest = OutboundUI;`, context);
    return context.OutboundUIUnderTest;
}

function createElement(initial = {}) {
    const listeners = new Map();
    return {
        innerHTML: '',
        textContent: '',
        value: '',
        files: [],
        dataset: {},
        classList: {
            add() {},
            remove() {},
            toggle() {},
        },
        addEventListener(type, callback) {
            listeners.set(type, callback);
        },
        trigger(type, event = {}) {
            return listeners.get(type)?.(event);
        },
        querySelectorAll: () => [],
        replaceChildren() {},
        append() {},
        appendChild() {},
        setAttribute() {},
        ...initial,
    };
}

test('el detalle de campaña escapa los datos dinámicos antes de insertarlos', async () => {
    const root = { innerHTML: '' };
    const campaign = {
        id: 17,
        name: '<script>alert(1)</script>',
        channel: 'whatsapp',
        template_name: 'Campaña <b>Especial</b>',
        template_snapshot: { body_text: 'Hola' },
        segment: 5,
        segment_name: 'Segmento "Clientes" & Aliados',
        total_recipients: 1,
        sent_count: 1,
        delivered_count: 1,
        read_count: 0,
        failed_count: 0,
        scheduled_at: '<img src=x onerror=alert(1)>',
        type: "Tipo 'especial' & <svg/onload=alert(1)>",
        status: 'sent',
    };

    const context = {
        window: {
            OutboundDemo: {
                CHANNELS: { whatsapp: { label: 'WhatsApp', icon: 'bi-whatsapp' } },
                TEMPLATES: [],
                loadCampaigns: () => [],
                saveCampaigns: () => {},
            },
        },
        document: {
            getElementById: (id) => id === 'campaignDetailRoot' ? root : null,
        },
        fetch: async (url) => {
            assert.equal(url, '/campanas/api/campaigns/17/');
            return { ok: true, json: async () => campaign };
        },
        URLSearchParams,
        console: { log() {}, warn() {}, error() {} },
        Date,
        Intl,
        Math,
        Number,
        String,
        Array,
        Object,
        encodeURIComponent,
    };

    loadUI(context);
    context.window.location = { search: '?id=17' };
    await context.OutboundUIUnderTest.renderCampaignDetail();

    assert.match(root.innerHTML, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
    assert.match(root.innerHTML, /Campaña &lt;b&gt;Especial&lt;\/b&gt;/);
    assert.match(root.innerHTML, /Segmento &quot;Clientes&quot; &amp; Aliados/);
    assert.match(root.innerHTML, /&lt;img src=x onerror=alert\(1\)&gt;/);
    assert.match(root.innerHTML, /Tipo &#039;especial&#039; &amp; &lt;svg\/onload=alert\(1\)&gt;/);
    assert.doesNotMatch(root.innerHTML, /<script>alert\(1\)<\/script>/);
    assert.doesNotMatch(root.innerHTML, /<img src=x onerror=alert\(1\)>/);
    assert.doesNotMatch(root.innerHTML, /<svg\/onload=alert\(1\)>/);
});

test('el resumen del asistente representa como texto los nombres dinámicos', async () => {
    const elements = new Map();
    const getElement = (id) => {
        if (!elements.has(id)) elements.set(id, createElement());
        return elements.get(id);
    };
    getElement('campaignName').value = '<script>alert(1)</script>';

    let audienceChange;
    const context = {
        window: {
            OutboundDemo: {
                CHANNELS: { whatsapp: { label: 'WhatsApp', icon: 'bi-whatsapp' } },
                TEMPLATES: [],
                loadCampaigns: () => [],
                saveCampaigns: () => {},
            },
            AudiencePicker: {
                mount: (_element, options) => {
                    audienceChange = options.onChange;
                    return {};
                },
            },
        },
        document: {
            cookie: '',
            getElementById: getElement,
            querySelectorAll: () => [],
            addEventListener() {},
        },
        fetch: async () => ({
            ok: true,
            json: async () => ({
                templates: [{
                    meta_id: 'tpl-1',
                    name: 'Campaña <b>Especial</b>',
                    status: 'APPROVED',
                    category: 'utility',
                    body_text: 'Mensaje',
                    language: 'es_CO',
                }],
            }),
        }),
        URLSearchParams,
        HTMLInputElement: class HTMLInputElement {},
        HTMLDialogElement: class HTMLDialogElement {},
        console: { log() {}, warn() {}, error() {} },
        Date,
        Intl,
        Math,
        Number,
        String,
        Array,
        Object,
        encodeURIComponent,
    };

    const ui = loadUI(context);
    ui.initWizard();
    await new Promise((resolve) => setTimeout(resolve, 0));

    audienceChange({ id: 5, name: 'Segmento "Clientes" & Aliados', contact_count: 10 });
    getElement('templateGrid').trigger('click', {
        target: { closest: () => ({ dataset: { tpl: 'tpl-1' } }) },
    });
    getElement('wizardNext').trigger('click');
    await getElement('wizardNext').trigger('click');

    const review = getElement('reviewList').innerHTML;
    assert.match(review, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
    assert.match(review, /Segmento &quot;Clientes&quot; &amp; Aliados/);
    assert.match(review, /Campaña &lt;b&gt;Especial&lt;\/b&gt;/);
    assert.doesNotMatch(review, /<script>alert\(1\)<\/script>/);
    assert.doesNotMatch(review, /<b>Especial<\/b>/);
});

test('channelBadge y statusPill escapan valores hostiles y conservan los legítimos', () => {
    const context = {
        window: {
            OutboundDemo: {
                CHANNELS: { whatsapp: { label: 'WhatsApp', icon: 'bi-whatsapp' } },
                TEMPLATES: [],
                loadCampaigns: () => [],
                saveCampaigns: () => {},
            },
        },
        document: {},
        Number,
        String,
        Array,
        Object,
    };
    const ui = loadUI(context);
    const hostileChannel = '"><img src=x onerror=alert(1)>';
    const hostileStatus = '"><svg onload=alert(1)>';
    const hostileLabel = '<script>alert(1)</script>';

    const channelHtml = ui.channelBadge(hostileChannel);
    const statusHtml = ui.statusPill(hostileStatus, hostileLabel);
    assert.match(channelHtml, /&quot;&gt;&lt;img src=x onerror=alert\(1\)&gt;/);
    assert.match(channelHtml, /class="channel-icon &quot;&gt;&lt;img src=x onerror=alert\(1\)&gt;"/);
    assert.match(statusHtml, /status-&quot;&gt;&lt;svg onload=alert\(1\)&gt;/);
    assert.match(statusHtml, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
    assert.doesNotMatch(`${channelHtml}${statusHtml}`, /<(?:img|svg|script)\b/i);
    assert.match(ui.channelBadge('whatsapp'), /class="channel-icon whatsapp"/);
    assert.match(ui.statusPill('sent', 'Enviada'), /status-enviada">Enviada<\/span>/);
});

test('el detalle normaliza contadores válidos y conserva porcentajes y formato', async () => {
    const root = { innerHTML: '' };
    const campaign = {
        id: 'local-valid',
        name: 'Campaña válida',
        channel: 'whatsapp',
        templateName: 'Plantilla',
        segments: [],
        totalRecipients: 1234,
        sent: 4,
        delivered: 2,
        read: 1,
        clicks: 1,
        replies: 9,
        executedAt: '-',
        type: 'marketing',
        status: 'sent',
    };
    const context = {
        window: {
            OutboundDemo: {
                CHANNELS: { whatsapp: { label: 'WhatsApp', icon: 'bi-whatsapp' } },
                TEMPLATES: [],
                loadCampaigns: () => [campaign],
                saveCampaigns: () => {},
            },
        },
        document: { getElementById: (id) => id === 'campaignDetailRoot' ? root : null },
        fetch: async () => ({ ok: false }),
        URLSearchParams,
        console: { log() {}, warn() {}, error() {} },
        Date,
        Intl,
        Math,
        Number,
        String,
        Array,
        Object,
        encodeURIComponent,
    };
    const ui = loadUI(context);
    context.window.location = { search: '?id=local-valid' };
    await ui.renderCampaignDetail();

    assert.match(root.innerHTML, /<div class="kpi-value">4<\/div>/);
    assert.match(root.innerHTML, /<div class="kpi-value">2<\/div>/);
    assert.match(root.innerHTML, /<div class="kpi-value">50%<\/div>/);
    assert.match(root.innerHTML, /<div class="kpi-value">9<\/div>/);
    assert.ok(root.innerHTML.includes(`${(1234).toLocaleString('es-CO')} destinatarios`));
});

test('el detalle neutraliza contadores HTML, no numéricos, nulos, NaN e infinitos', async () => {
    const root = { innerHTML: '' };
    const campaign = {
        id: 'local-hostile',
        name: 'Campaña',
        channel: 'whatsapp',
        templateName: 'Plantilla',
        segments: [],
        totalRecipients: '<img src=x onerror=alert(1)>',
        sent: '7<script>alert(1)</script>',
        delivered: {},
        read: Infinity,
        clicks: NaN,
        replies: null,
        executedAt: '-',
        type: 'marketing',
        status: 'sent',
    };
    const context = {
        window: {
            OutboundDemo: {
                CHANNELS: { whatsapp: { label: 'WhatsApp', icon: 'bi-whatsapp' } },
                TEMPLATES: [],
                loadCampaigns: () => [campaign],
                saveCampaigns: () => {},
            },
        },
        document: { getElementById: (id) => id === 'campaignDetailRoot' ? root : null },
        fetch: async () => ({ ok: false }),
        URLSearchParams,
        console: { log() {}, warn() {}, error() {} },
        Date,
        Intl,
        Math,
        Number,
        String,
        Array,
        Object,
        encodeURIComponent,
    };
    const ui = loadUI(context);
    context.window.location = { search: '?id=local-hostile' };
    await ui.renderCampaignDetail();

    assert.equal((root.innerHTML.match(/<div class="kpi-value">0<\/div>/g) || []).length, 3);
    assert.equal((root.innerHTML.match(/<div class="kpi-value">0%<\/div>/g) || []).length, 2);
    assert.ok(root.innerHTML.includes('0 destinatarios'));
    assert.doesNotMatch(root.innerHTML, /<img|<script|NaN|Infinity/);

    campaign.totalRecipients = null;
    campaign.sent = 0;
    campaign.delivered = Number.MIN_VALUE;
    campaign.read = Number.MAX_VALUE;
    campaign.clicks = 0;
    campaign.replies = Infinity;
    await ui.renderCampaignDetail();
    assert.equal((root.innerHTML.match(/<div class="kpi-value">0%<\/div>/g) || []).length, 2);
    assert.ok(root.innerHTML.includes('0 destinatarios'));
    assert.doesNotMatch(root.innerHTML, /NaN|Infinity/);
});
