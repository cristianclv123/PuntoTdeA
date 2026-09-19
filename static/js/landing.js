document.addEventListener('DOMContentLoaded', () => {
    console.log('PuntoTdeA Portal cargado correctamente.');

    // Interacción suave para las tarjetas de los módulos
    const cards = document.querySelectorAll('.module-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.classList.add('shadow-lg');
        });
        card.addEventListener('mouseleave', () => {
            card.classList.remove('shadow-lg');
        });
    });

    const chat = document.querySelector('[data-ask-url]');
    if (!chat) return;

    const form = chat.querySelector('[data-chat-form]');
    const input = form.querySelector('input[name="q"]');
    const messages = chat.querySelector('[data-chat-messages]');

    form.addEventListener('submit', async event => {
        event.preventDefault();
        const question = input.value.trim();
        if (!question) return;

        messages.insertAdjacentHTML('beforeend', `<div class="chat-message chat-message--user"><span class="fw-semibold">Tú:</span> ${escapeHtml(question)}</div>`);
        input.value = '';
        input.disabled = true;
        form.querySelector('button').disabled = true;
        const loading = document.createElement('div');
        loading.className = 'chat-message chat-message--bot text-muted';
        loading.textContent = 'Consultando la base de conocimiento...';
        messages.appendChild(loading);

        try {
            const response = await fetch(`${chat.dataset.askUrl}?q=${encodeURIComponent(question)}`);
            if (!response.ok) throw new Error('No fue posible consultar el asistente.');
            const data = await response.json();
            const image = data.sources?.find(source => source.image_url)?.image_url;
            const imageHtml = image ? `<img src="${escapeHtml(image)}" alt="" class="chat-source-image mt-2">` : '';
            loading.innerHTML = `<span class="fw-semibold">Asistente:</span> ${escapeHtml(data.answer)}${imageHtml}<small class="d-block mt-2 text-muted">Confianza: ${Math.round(data.confidence * 100)}%${data.needs_human_attention ? ' · Requiere validación humana' : ''}</small>`;
        } catch (error) {
            loading.textContent = error.message;
        } finally {
            input.disabled = false;
            form.querySelector('button').disabled = false;
            input.focus();
            messages.scrollTop = messages.scrollHeight;
        }
    });

    function escapeHtml(value) {
        return value.replace(/[&<>'"]/g, character => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        }[character]));
    }
});