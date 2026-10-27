(() => {
  const input = document.querySelector('[data-q]');
  const box = document.getElementById('suggest');
  if (!input || !box) return;
  let items = [], active = -1, timer, ctl;

  const close = () => { box.hidden = true; box.innerHTML = ''; items = []; active = -1; };
  const mark = i => [...box.children].forEach((li, n) => li.setAttribute('aria-selected', n === i));
  const go = text => { input.value = text; input.form.submit(); };

  function render(list) {
    close();
    if (!list.length) return;
    items = list;
    list.forEach(text => {
      const li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.textContent = text;
      li.addEventListener('mousedown', e => { e.preventDefault(); go(text); });
      box.appendChild(li);
    });
    box.hidden = false;
  }

  async function fetchSuggestions() {
    const q = input.value.trim();
    if (!q) return close();
    ctl && ctl.abort();
    ctl = new AbortController();
    try {
      const r = await fetch('/api/suggest?q=' + encodeURIComponent(input.value), { signal: ctl.signal });
      render((await r.json()).suggestions);
    } catch (_) { /* لغو یا خطای شبکه */ }
  }

  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(fetchSuggestions, 120); });
  input.addEventListener('blur', close);
  input.addEventListener('keydown', e => {
    if (box.hidden || !items.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); active = (active + 1) % items.length; mark(active); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); active = (active - 1 + items.length) % items.length; mark(active); }
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); go(items[active]); }
    else if (e.key === 'Escape') close();
  });
  document.addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement !== input) { e.preventDefault(); input.focus(); input.select(); }
  });
})();
