(function () {
  const ASSISTANT_URL = '/asistente/';

  const fab = document.getElementById('lp-chat-fab');
  const widget = document.getElementById('lp-chat-widget');
  const closeBtn = document.getElementById('lp-chat-widget-close');
  const messages = document.getElementById('lp-chat-widget-messages');
  const confirmActions = document.getElementById('lp-chat-widget-confirm');
  const helpActions = document.getElementById('lp-chat-widget-help');
  const form = document.getElementById('lp-chat-widget-form');
  const input = document.getElementById('lp-chat-widget-input');
  const newQuestionBtn = document.getElementById('lp-chat-widget-new-question');
  const advisorBtn = document.getElementById('lp-chat-widget-advisor');

  if (!fab || !widget || !form) return;

  let started = false;
  let currentState = 'waiting_question';

  function addMessage(text, author) {
    const bubble = document.createElement('div');
    bubble.className = `lp-chat-bubble ${author}`;
    bubble.textContent = text;
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
  }

  function showActionsFor(state) {
    confirmActions.hidden = state !== 'waiting_confirmation';
    helpActions.hidden = state !== 'help_options';
  }

  function applyState(data) {
    currentState = data.state;
    if (data.message) addMessage(data.message, 'bot');
    showActionsFor(currentState);
    const finished = currentState === 'ended' || currentState === 'pending';
    form.hidden = finished;
    if (finished) {
      confirmActions.hidden = true;
      helpActions.hidden = true;
    }
  }

  async function start() {
    const response = await fetch(ASSISTANT_URL, { headers: { Accept: 'application/json' } });
    const data = await response.json();
    started = true;
    applyState(data);
  }

  async function send(payload, visibleText) {
    if (visibleText) addMessage(visibleText, 'user');
    const response = await fetch(ASSISTANT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      addMessage(data.error || 'No fue posible procesar tu mensaje.', 'bot');
      return;
    }
    applyState(data);
  }

  async function openWidget() {
    widget.hidden = false;
    fab.setAttribute('aria-expanded', 'true');
    if (!started) {
      await start();
    }
    input.focus();
  }

  function closeWidget() {
    widget.hidden = true;
    fab.setAttribute('aria-expanded', 'false');
  }

  fab.addEventListener('click', () => {
    if (widget.hidden) openWidget();
    else closeWidget();
  });

  closeBtn.addEventListener('click', closeWidget);

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (!value) return;
    input.value = '';
    const action = currentState === 'waiting_advisor_question' ? 'advisor_question' : 'question';
    send({ action, question: value }, value);
  });

  confirmActions.querySelectorAll('[data-help]').forEach((button) => {
    button.addEventListener('click', () => {
      showActionsFor('');
      send({ action: 'confirm', needs_more_help: button.dataset.help === 'yes' }, button.textContent);
    });
  });

  newQuestionBtn.addEventListener('click', () => {
    showActionsFor('');
    input.focus();
  });

  advisorBtn.addEventListener('click', () => {
    showActionsFor('');
    send({ action: 'escalate', reason: 'Solicitud desde el widget de la landing' }, 'Hablar con un asesor');
  });
})();
