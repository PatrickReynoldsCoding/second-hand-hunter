const profile = () => document.getElementById('profile-pick')?.value;
const mode = () => document.querySelector('.mode-pick')?.value || 'rules';

// Remember the chosen check mode and keep every picker on the page in step.
function setMode(value) {
  document.querySelectorAll('.mode-pick').forEach(pick => { pick.value = value; });
  try { localStorage.setItem('checkMode', value); } catch {}
}
try { setMode(localStorage.getItem('checkMode') || 'rules'); } catch { setMode('rules'); }
document.addEventListener('change', async e => {
  const pick = e.target;
  if (pick.classList.contains('mode-pick')) setMode(pick.value);
  if (pick.classList.contains('stage-pick')) {
    try {
      await post('/api/status', {profile: pick.dataset.profile, hunt: pick.dataset.hunt, key: pick.dataset.key,
        status: 'interested', stage: pick.value});
      location.reload();
    } catch (error) { toast(error.message); }
  }
});

async function post(path, body) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Something went wrong');
  return data;
}

function toast(text) {
  let box = document.getElementById('toast');
  if (!box) { box = document.createElement('div'); box.id = 'toast'; document.body.append(box); }
  box.textContent = text;
  clearTimeout(box.timer);
  box.timer = setTimeout(() => box.remove(), 4000);
}

function formData(form, submitter) {
  const data = {profile: form.dataset.profile, sites: []};
  for (const field of form.elements) {
    if (!field.name || field.tagName === 'BUTTON') continue;
    if (field.name === 'sites') { if (field.checked) data.sites.push(field.value); }
    else if (field.type === 'checkbox') data[field.name] = field.checked;
    else data[field.name] = field.value;
  }
  if (submitter?.name) data[submitter.name] = submitter.value;
  data.mode = mode();
  return data;
}

document.addEventListener('submit', async e => {
  const form = e.target.closest('form.api'); if (!form) return;
  e.preventDefault();
  try {
    const result = await post(form.dataset.api, formData(form, e.submitter));
    if (result.message) toast(result.message);
    sessionStorage.setItem('pendingToast', result.message || '');
    if (result.go) location.href = result.go;
  } catch (error) { toast(error.message); }
});

document.addEventListener('click', async e => {
  const b = e.target.closest('button'); if (!b) return;
  try {
    if (b.classList.contains('copy')) { await navigator.clipboard.writeText(b.dataset.text); b.textContent = 'Copied'; }
    else if (b.dataset.status !== undefined) {
      await post('/api/status', {profile: b.dataset.profile, hunt: b.dataset.hunt, key: b.dataset.key, status: b.dataset.status});
      b.closest('article').remove();
      toast(b.textContent === 'Back to review' ? 'Moved back to review' : `Moved to ${b.textContent}`);
    }
    else if (b.dataset.browser) {
      toast((await post('/api/browser', {profile: profile(), site: b.dataset.browser, hunt: b.dataset.hunt, mode: mode()})).message); watch();
    }
    else if (b.dataset.toggle) document.getElementById(b.dataset.toggle).classList.toggle('hidden');
    else if (b.dataset.delete) {
      if (!confirm('Delete this hunt? Its listings stay in the database.')) return;
      location.href = (await post('/api/hunt/delete', {profile: profile(), slug: b.dataset.delete})).go;
    }
    else if (b.dataset.search !== undefined) {
      toast((await post('/api/search', {profile: profile(), hunt: b.dataset.search, mode: mode()})).message); watch();
    }
  } catch (error) { toast(error.message); }
});

document.getElementById('profile-pick')?.addEventListener('change', e => {
  location.href = '/?profile=' + encodeURIComponent(e.target.value);
});

async function watch() {
  const status = document.getElementById('status'); if (!status) return;
  const data = await (await fetch('/api/status')).json();
  status.textContent = data.message;
  if (data.running) setTimeout(watch, 3000);
  else if (status.dataset.wasRunning) location.reload();
  status.dataset.wasRunning = data.running ? '1' : '';
}

const pending = sessionStorage.getItem('pendingToast');
if (pending) { toast(pending); sessionStorage.removeItem('pendingToast'); }
watch();

// --- Photo viewer: click a card to see larger photos ---
const viewer = document.getElementById('viewer');
let detail = null, index = 0;

function show(i) {
  if (!detail || !detail.photos.length) return;
  index = (i + detail.photos.length) % detail.photos.length;
  document.getElementById('viewer-photo').src = detail.photos[index];
  document.getElementById('viewer-count').textContent = `${index + 1} / ${detail.photos.length}`;
  document.querySelectorAll('#viewer-thumbs img').forEach((img, n) => img.classList.toggle('on', n === index));
}

function openViewer(card) {
  detail = JSON.parse(card.dataset.detail);
  document.getElementById('viewer-title').textContent = detail.title;
  document.getElementById('viewer-facts').textContent = detail.facts;
  document.getElementById('viewer-reason').textContent = detail.reason;
  document.getElementById('viewer-description').textContent = detail.description;
  const site = document.getElementById('viewer-site');
  site.href = detail.url; site.textContent = `Open on ${detail.site} ↗`;
  const thumbs = document.getElementById('viewer-thumbs');
  thumbs.replaceChildren(...detail.thumbs.map((src, n) => {
    const img = document.createElement('img'); img.src = src; img.alt = ''; img.dataset.index = n; return img;
  }));
  viewer.classList.toggle('single', detail.photos.length < 2);
  viewer.classList.toggle('nophotos', !detail.photos.length);
  viewer.showModal();
  show(0);
}

document.addEventListener('click', e => {
  const card = e.target.closest('article[data-detail]');
  if (card && !e.target.closest('button, a, select, label, details')) openViewer(card);
  if (!viewer.open) return;
  if (e.target === viewer || e.target.closest('[data-close]')) viewer.close();
  const step = e.target.closest('[data-step]'); if (step) show(index + Number(step.dataset.step));
  const thumb = e.target.closest('#viewer-thumbs img'); if (thumb) show(Number(thumb.dataset.index));
  if (e.target.id === 'viewer-fullscreen') {
    document.fullscreenElement ? document.exitFullscreen() : document.getElementById('viewer-stage').requestFullscreen();
  }
});

document.addEventListener('keydown', e => {
  if (!viewer.open) return;
  if (e.key === 'ArrowLeft') show(index - 1);
  if (e.key === 'ArrowRight') show(index + 1);
});
