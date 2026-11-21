const profile = () => document.getElementById('profile-pick')?.value;

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
    else if (b.classList.contains('view')) {
      await post('/viewed', {profile: b.dataset.profile, hunt: b.dataset.hunt, key: b.dataset.key, viewed: b.dataset.viewed === '1'});
      b.closest('article').remove();
    }
    else if (b.dataset.toggle) document.getElementById(b.dataset.toggle).classList.toggle('hidden');
    else if (b.dataset.delete) {
      if (!confirm('Delete this hunt? Its listings stay in the database.')) return;
      location.href = (await post('/api/hunt/delete', {profile: profile(), slug: b.dataset.delete})).go;
    }
    else if (b.dataset.search !== undefined) {
      toast((await post('/api/search', {profile: profile(), hunt: b.dataset.search})).message); watch();
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
