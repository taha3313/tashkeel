const $ = id => document.getElementById(id);
let busy = false;
let wordUrl;
const countFormat = new Intl.NumberFormat('ar');
function setMode(mode) {
  $('text-panel').hidden = mode !== 'text';
  $('word-panel').hidden = mode !== 'word';
  $('text-tab').setAttribute('aria-pressed', mode === 'text');
  $('word-tab').setAttribute('aria-pressed', mode === 'word');
  const url = new URL(location.href);
  url.searchParams.set('mode', mode);
  history.replaceState(null, '', url);
  clearMessages();
}
$('text-tab').onclick = () => setMode('text');
$('word-tab').onclick = () => setMode('word');
setMode(new URL(location.href).searchParams.get('mode') === 'word' ? 'word' : 'text');
function clearMessages() { $('error').hidden = true; $('status').textContent = ''; $('input').removeAttribute('aria-invalid'); $('document').removeAttribute('aria-invalid'); }
function fail(error) {
  const message = ['AbortError', 'TimeoutError'].includes(error.name) ? 'استغرقت المعالجة وقتًا طويلًا. أعد المحاولة بعد قليل.' : error instanceof TypeError ? 'تعذّر الاتصال بالخدمة. تحقق من اتصالك وأعد المحاولة.' : error.message;
  $('error').textContent = message || 'حدث خطأ. أعد المحاولة.'; $('error').hidden = false;
}
function textState(state) { $('text-panel').dataset.state = state; document.querySelector('.result-pane')?.setAttribute('aria-busy', String(state === 'loading')); }
function setBusy(value) {
  busy = value;
  for (const id of ['submit-text', 'submit-word', 'sample', 'input', 'document', 'text-tab', 'word-tab']) $(id).disabled = value;
  $('submit-text').setAttribute('aria-busy', value);
  $('submit-word').setAttribute('aria-busy', value);
}
async function request(path, options) {
  const signal = AbortSignal.timeout(240000);
  // Wait for readiness before sending text or uploading a document. Only GETs
  // are retried; inference submissions are never automatically replayed.
  const deadline = Date.now() + 180000;
  while (true) {
    signal.throwIfAborted();
    const health = await fetch('/health', {signal, cache: 'no-store'});
    const body = await health.json().catch(() => null);
    if (health.ok && body?.status === 'ok') break;
    if (Date.now() >= deadline) throw new Error('تعذّر تشغيل الخدمة. أعد المحاولة بعد قليل.');
    await new Promise(resolve => setTimeout(resolve, 3000));
  }
  const response = await fetch(path, { ...options, signal });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'تعذّر إكمال الطلب. راجع حجم النص أو الملف وأعد المحاولة.');
  }
  return response;
}
function count() { $('count').textContent = `${countFormat.format($('input').value.length)} / ٢٠٬٠٠٠ حرف`; }
$('input').oninput = count;
$('sample').onclick = () => { $('input').value = 'اللغة العربية لغة جميلة، تجمع بين دقة التعبير وجمال البيان.'; count(); $('input').focus(); };
$('text-form').onsubmit = async event => {
  event.preventDefault(); if (busy) return;
  clearMessages(); setBusy(true); textState('loading'); $('result-section').hidden = true;
  $('status').textContent = 'جارٍ تشكيل النص… قد يستغرق التشغيل الأول نحو دقيقة.';
  try {
    const response = await request('/api/tashkeel', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: $('input').value}) });
    $('output').value = (await response.json()).text;
    $('result-section').hidden = false; textState('ready');
    $('status').textContent = 'اكتمل التشكيل. يمكنك مراجعة النص وتعديله قبل النسخ أو التحميل.';
    $('output').focus();
  } catch (error) { $('status').textContent = ''; textState('error'); fail(error); }
  finally { setBusy(false); }
};
$('copy').onclick = async () => { try { await navigator.clipboard.writeText($('output').value); $('status').textContent = 'تم نسخ النص.'; } catch { $('output').select(); $('status').textContent = 'حدّدنا النص؛ انسخه من قائمة المتصفح.'; } };
$('download-text').onclick = () => {
  const url = URL.createObjectURL(new Blob([$('output').value], {type: 'text/plain;charset=utf-8'}));
  const link = document.createElement('a'); link.href = url; link.download = 'tashkeel.txt'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$('document').onchange = () => {
  $('filename').textContent = $('document').files[0]?.name || 'لم يتم اختيار ملف';
  $('download-word').hidden = true; if (wordUrl) URL.revokeObjectURL(wordUrl);
  clearMessages();
};
$('word-form').onsubmit = async event => {
  event.preventDefault(); if (busy) return;
  clearMessages(); $('download-word').hidden = true;
  const file = $('document').files[0];
  if (!file || !/\.docx$/i.test(file.name)) { $('document').setAttribute('aria-invalid', 'true'); fail(new Error('اختر ملف Word بصيغة .docx.')); return; }
  if (file.size > 5 * 1024 * 1024) { $('document').setAttribute('aria-invalid', 'true'); fail(new Error('الحد الأقصى لحجم الملف ٥ ميغابايت.')); return; }
  setBusy(true); $('status').textContent = 'جارٍ تشكيل المستند… قد يستغرق التشغيل الأول نحو دقيقة. أبقِ هذه الصفحة مفتوحة.';
  try {
    const form = new FormData(); form.append('file', file);
    const response = await request('/api/document', {method: 'POST', body: form});
    if (wordUrl) URL.revokeObjectURL(wordUrl);
    wordUrl = URL.createObjectURL(await response.blob());
    $('download-word').href = wordUrl;
    $('download-word').download = file.name.replace(/\.docx$/i, '-tashkeel.docx');
    $('download-word').hidden = false;
    $('status').textContent = 'اكتمل التشكيل. حمّل المستند وراجعه في Word.';
    $('download-word').focus();
  } catch (error) { $('status').textContent = ''; fail(error); }
  finally { setBusy(false); }
};

const dropZone = $('drop-zone');
for (const type of ['dragenter', 'dragover']) dropZone.addEventListener(type, event => {
  event.preventDefault();
  if (!busy) dropZone.classList.add('is-dragover');
});
for (const type of ['dragleave', 'drop']) dropZone.addEventListener(type, event => {
  event.preventDefault(); dropZone.classList.remove('is-dragover');
});
dropZone.addEventListener('drop', event => {
  if (busy || !event.dataTransfer?.files.length) return;
  const file = event.dataTransfer.files[0];
  if (!/\.docx$/i.test(file.name)) { $('document').value = ''; $('document').dispatchEvent(new Event('change')); fail(new Error('اختر ملف Word بصيغة .docx.')); $('document').setAttribute('aria-invalid', 'true'); return; }
  const transfer = new DataTransfer(); transfer.items.add(file);
  $('document').files = transfer.files;
  $('document').dispatchEvent(new Event('change'));
});
