const form = document.querySelector('#ask-form');
const question = document.querySelector('#question');
const submit = document.querySelector('#submit');
const status = document.querySelector('#status');
const result = document.querySelector('#result');
const chips = document.querySelectorAll('[data-question]');

function updateCount() {
  document.querySelector('#count').textContent = `${question.value.length.toLocaleString()} / 2,000`;
}

question.addEventListener('input', updateCount);
chips.forEach(button => button.addEventListener('click', () => {
  question.value = button.dataset.question;
  updateCount();
  question.focus();
}));

function showSources(sources) {
  const container = document.querySelector('#sources');
  container.replaceChildren();
  if (!sources.length) return;
  const heading = document.createElement('h3');
  heading.textContent = `Sources · ${sources.length}`;
  container.append(heading);
  sources.forEach(source => {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = source.title;
    details.append(summary);
    // Source and model text are displayed as text, never interpreted as HTML.
    try {
      const url = new URL(source.location);
      if (url.protocol === 'https:' || url.protocol === 'http:') {
        const link = document.createElement('a');
        link.className = 'source-link';
        link.href = url.href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = `View source at ${url.hostname} ↗`;
        details.append(link);
      }
    } catch { /* Local source references have no external link. */ }
    const content = document.createElement('p');
    content.className = 'source-content';
    try {
      content.textContent = JSON.stringify(JSON.parse(source.content), null, 2);
    } catch {
      content.textContent = source.content;
    }
    details.append(content);
    container.append(details);
  });
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text || submit.disabled) {
    question.focus();
    return;
  }
  submit.disabled = true;
  question.disabled = true;
  chips.forEach(button => { button.disabled = true; });
  submit.textContent = 'Finding an answer…';
  status.className = 'status';
  status.textContent = 'Checking the sources and putting your answer together…';
  result.hidden = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 680000);
  const slowMessage = setTimeout(() => {
    status.textContent = 'Still working. The hosted model can take a few minutes to respond.';
  }, 15000);

  try {
    const response = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text }),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) {
      const message = typeof data.detail === 'string' ? data.detail : 'Please check your question and try again.';
      throw new Error(message);
    }
    document.querySelector('#answer-title').textContent = text;
    document.querySelector('#answer').textContent = data.answer;
    const warnings = document.querySelector('#warnings');
    warnings.replaceChildren();
    data.warnings.forEach(message => {
      const warning = document.createElement('p');
      warning.className = 'warning';
      warning.textContent = message;
      warnings.append(warning);
    });
    showSources(data.sources);
    result.hidden = false;
    status.textContent = 'Answer ready.';
    result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (error) {
    status.className = 'status error';
    status.textContent = error.name === 'AbortError'
      ? 'The request took too long. Please try again.'
      : error instanceof TypeError || error instanceof SyntaxError
        ? 'Could not reach the chatbot. Please try again.'
        : error.message;
  } finally {
    clearTimeout(timeout);
    clearTimeout(slowMessage);
    submit.disabled = false;
    question.disabled = false;
    chips.forEach(button => { button.disabled = false; });
    submit.textContent = 'Ask a question ↗';
  }
});
