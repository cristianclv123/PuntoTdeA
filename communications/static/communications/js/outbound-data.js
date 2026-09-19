window.OutboundDemo = (() => {
    const CHANNELS = {
        whatsapp: { label: 'WhatsApp', icon: 'bi-whatsapp', account: 'TdeA WhatsApp +57 604 444 00 00' },
    };

    const SEGMENTS = [
        { id: 'est-activos', name: 'Estudiantes activos', size: 8420, source: 'Backend CRUD' },
        { id: 'aspirantes', name: 'Aspirantes 2026-1', size: 2104, source: 'Backend CRUD' },
        { id: 'egresados', name: 'Egresados', size: 15680, source: 'Backend CRUD' },
        { id: 'docentes', name: 'Docentes', size: 612, source: 'Backend CRUD' },
        { id: 'admin', name: 'Administrativos', size: 340, source: 'Backend CRUD' },
        { id: 'opt-out', name: 'Excluidos de informativos', size: 188, source: 'Preferencias' },
    ];

    const TEMPLATES = {
        whatsapp: [
            { id: 'wa-matricula', name: 'Recordatorio de matrícula', type: 'utilidad', body: 'Hola {{nombre}}, el periodo de matrícula {{periodo}} cierra el {{fecha}}. Completa el proceso en Punto TdeA.', buttons: ['Ir a matrícula', 'Hablar con bienestar'] },
            { id: 'wa-bienestar', name: 'Convocatoria bienestar', type: 'marketing', body: '{{nombre}}, hay una nueva convocatoria de {{programa}}. Cupos limitados.', buttons: ['Ver convocatoria'] },
            { id: 'wa-cita', name: 'Recordatorio de cita', type: 'utilidad', body: 'Hola {{nombre}}, tienes cita el {{fecha}} a las {{hora}}. Responde SI para confirmar.' },
            { id: 'wa-aviso', name: 'Aviso operativo', type: 'utilidad', body: 'TdeA informa: {{mensaje}}. Más info en Punto TdeA.' },
        ],
    };

    const SEED_CAMPAIGNS = [
        { id: 'c1', name: 'Matrícula 2026-1', channel: 'whatsapp', type: 'utilidad', segments: ['Estudiantes activos'], executedAt: '2026-08-28 08:00', status: 'enviada', sent: 8420, delivered: 8310, read: 7204, clicks: 2104, replies: 980, templateId: 'wa-matricula' },
        { id: 'c2', name: 'Citas de admisión', channel: 'whatsapp', type: 'utilidad', segments: ['Aspirantes 2026-1'], executedAt: '2026-09-02 10:30', status: 'enviada', sent: 2104, delivered: 2088, read: 1980, clicks: 0, replies: 640, templateId: 'wa-cita' },
        { id: 'c3', name: 'Boletín egresados', channel: 'whatsapp', type: 'marketing', segments: ['Egresados'], executedAt: '2026-09-10 07:00', status: 'programada', sent: 0, delivered: 0, read: 0, clicks: 0, replies: 0, templateId: 'wa-bienestar' },
        { id: 'c4', name: 'Feria de facultades', channel: 'whatsapp', type: 'marketing', segments: ['Aspirantes 2026-1', 'Estudiantes activos'], executedAt: '2026-08-20 12:00', status: 'enviada', sent: 3200, delivered: 3180, read: 2410, clicks: 870, replies: 122, templateId: 'wa-bienestar' },
        { id: 'c5', name: 'Aviso de planta', channel: 'whatsapp', type: 'utilidad', segments: ['Docentes', 'Administrativos'], executedAt: '—', status: 'borrador', sent: 0, delivered: 0, read: 0, clicks: 0, replies: 0, templateId: 'wa-aviso' },
    ];

    const SEED_LOGS = [
        { at: '2026-09-04 09:12', person: 'Laura Restrepo', channel: 'whatsapp', campaign: 'Matrícula 2026-1', event: 'respuesta', detail: '¿Puedo fraccionar el pago?' },
        { at: '2026-09-04 09:08', person: 'Andrés Gómez', channel: 'whatsapp', campaign: 'Matrícula 2026-1', event: 'clic', detail: 'Ir a matrícula' },
        { at: '2026-09-04 08:55', person: 'Camila Hoyos', channel: 'whatsapp', campaign: 'Citas de admisión', event: 'respuesta', detail: 'SI' },
        { at: '2026-09-03 16:40', person: 'Julián Pérez', channel: 'whatsapp', campaign: 'Boletín egresados', event: 'programada', detail: 'Envío agendado' },
        { at: '2026-09-03 11:22', person: 'Sara Muñoz', channel: 'whatsapp', campaign: 'Feria de facultades', event: 'lectura', detail: 'Mensaje abierto' },
        { at: '2026-09-02 10:31', person: 'Mateo Cano', channel: 'whatsapp', campaign: 'Citas de admisión', event: 'entregado', detail: 'Entregado al dispositivo' },
        { at: '2026-08-28 08:02', person: 'Valentina Díaz', channel: 'whatsapp', campaign: 'Matrícula 2026-1', event: 'enviado', detail: 'Plantilla utilidad' },
    ];

    const STORAGE_KEY = 'puntotdea_outbound_campaigns';

    function loadCampaigns() {
        try {
            const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
            if (Array.isArray(stored) && stored.length) {
                return stored.map((c) => ({ ...c, channel: 'whatsapp' }));
            }
        } catch (e) { /* demo fallback */ }
        return [...SEED_CAMPAIGNS];
    }

    function saveCampaigns(list) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    }

    return { CHANNELS, SEGMENTS, TEMPLATES, SEED_LOGS, loadCampaigns, saveCampaigns };
})();
