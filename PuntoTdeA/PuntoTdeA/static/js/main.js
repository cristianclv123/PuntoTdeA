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
});