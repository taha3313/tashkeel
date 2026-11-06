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
  for (const id of ['submit-text', 'submit-word', 'sample', 'input', 'document', 'text-tab', 'word-tab', 'jais-mode']) $(id).disabled = value;
  $('submit-word').setAttribute('aria-busy', value && !$('word-panel').hidden);
  $('submit-text').setAttribute('aria-busy', value && !$('text-panel').hidden);
  $('submit-text').querySelector('span').textContent = value && !$('text-panel').hidden ? 'جارٍ التشكيل…' : 'شكّل النص';
  $('submit-word').querySelector('span').textContent = value && !$('word-panel').hidden ? 'جارٍ التشكيل…' : 'شكّل المستند';
  if (!value) $('submit-word').disabled = !validWordFile($('document').files[0]);
}
async function request(path, options, onReady = () => {}) {
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
  onReady();
  const headers = new Headers(options.headers);
  if ($('jais-mode').checked) headers.set('X-Tashkeel-Mode', 'jais');
  const response = await fetch(path, { ...options, headers, signal });
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
function validWordFile(file) { return Boolean(file && /\.docx$/i.test(file.name) && file.size <= 5 * 1024 * 1024); }
function wordState(state) {
  $('word-panel').dataset.state = state;
  const loading = state === 'starting' || state === 'processing';
  $('word-result').setAttribute('aria-busy', String(loading));
  const states = {
    empty: ['بانتظار الملف', 'نتيجتك ستظهر هنا', 'اختر مستندك، ثم اضغط «شكّل المستند». سيظهر رابط التحميل هنا عند اكتمال التشكيل.'],
    selected: ['جاهز للتشكيل', 'مستندك جاهز للبدء', 'اضغط «شكّل المستند» لإضافة الحركات. بعد اكتمال التشكيل، يمكنك تحميل نسخة جديدة.'],
    starting: ['جارٍ التجهيز', 'نجهّز الخدمة لمستندك…', 'قد يستغرق التشغيل الأول نحو دقيقة. أبقِ هذه الصفحة مفتوحة؛ ستبدأ المعالجة تلقائيًا.'],
    processing: ['قيد المعالجة', 'جارٍ تشكيل المستند…', 'نرسل المستند ونضيف الحركات إلى نصّه. سيظهر زر التحميل هنا فور اكتمال المعالجة.'],
    ready: ['جاهز للتحميل', 'اكتمل تشكيل مستندك', 'نسختك المشكّلة جاهزة. حمّلها من الزر أدناه وافتحها في Word لمراجعتها.'],
    error: ['لم يكتمل', 'تعذّر تجهيز النتيجة', 'راجع رسالة الخطأ أدناه. يمكنك إعادة المحاولة أو اختيار مستند آخر.'],
  };
  const [badge, title, help] = states[state];
  $('word-badge').textContent = badge;
  $('word-state-title').textContent = title;
  $('word-state-help').textContent = help;
  $('word-action-hint').textContent = loading ? 'أبقِ الصفحة مفتوحة' : state === 'ready' ? 'اختر ملفًا آخر لتشكيل مستند جديد' : state === 'selected' ? 'الخطوة التالية: تشكيل المستند' : state === 'error' ? 'اختر ملفًا صالحًا أو أعد المحاولة' : 'اختر ملفًا للبدء';
  $('word-state-symbol').setAttribute('d', state === 'ready' ? 'm5 12 4 4L19 6' : state === 'error' ? 'M12 5v9m0 4v.1' : 'M12 3v12m-5-5 5 5 5-5M5 16v4h14v-4');
  const active = state === 'ready' ? 'step-download' : loading || state === 'selected' ? 'step-process' : 'step-select';
  for (const id of ['step-select', 'step-process', 'step-download']) {
    if (id === active) $(id).setAttribute('aria-current', 'step');
    else $(id).removeAttribute('aria-current');
    $(id).classList.toggle('is-complete', state === 'ready' || (id === 'step-select' && (loading || state === 'selected')));
  }
}
$('document').onchange = () => {
  const file = $('document').files[0];
  clearMessages();
  $('download-word').hidden = true;
  $('download-word').removeAttribute('href');
  $('word-result-name').hidden = true;
  if (wordUrl) { URL.revokeObjectURL(wordUrl); wordUrl = undefined; }
  $('selected-file').hidden = !file;
  $('filename').textContent = file?.name || 'لم يتم اختيار ملف';
  $('file-size').textContent = file ? new Intl.NumberFormat('ar', {maximumFractionDigits: 1}).format(file.size / 1024) + ' كيلوبايت' : '';
  $('upload-title').textContent = file ? 'تم اختيار المستند' : 'اختر مستند Word';
  $('upload-hint').textContent = file ? 'يمكنك اختيار ملف آخر أو سحبه هنا' : 'أو اسحبه إلى هنا';
  $('file-pick').textContent = file ? 'تغيير الملف' : 'اختيار ملف';
  const valid = validWordFile(file);
  $('submit-word').disabled = !valid;
  wordState(valid ? 'selected' : file ? 'error' : 'empty');
  if (file && !valid) {
    $('document').setAttribute('aria-invalid', 'true');
    fail(new Error(!/\.docx$/i.test(file.name) ? 'اختر ملف Word بصيغة .docx.' : 'الحد الأقصى لحجم الملف ٥ ميغابايت.'));
  }
};
$('word-form').onsubmit = async event => {
  event.preventDefault(); if (busy) return;
  clearMessages(); $('download-word').hidden = true;
  const file = $('document').files[0];
  if (!file || !/\.docx$/i.test(file.name)) { $('document').setAttribute('aria-invalid', 'true'); fail(new Error('اختر ملف Word بصيغة .docx.')); return; }
  if (file.size > 5 * 1024 * 1024) { $('document').setAttribute('aria-invalid', 'true'); fail(new Error('الحد الأقصى لحجم الملف ٥ ميغابايت.')); return; }
  setBusy(true); wordState('starting'); $('word-result-name').hidden = true;
  $('word-result').scrollIntoView({block: 'nearest'});
  try {
    const form = new FormData(); form.append('file', file);
    const response = await request('/api/document', {method: 'POST', body: form}, () => wordState('processing'));
    if (wordUrl) URL.revokeObjectURL(wordUrl);
    wordUrl = URL.createObjectURL(await response.blob());
    $('download-word').href = wordUrl;
    $('download-word').download = file.name.replace(/\.docx$/i, '-tashkeel.docx');
    $('download-word').hidden = false;
    $('word-result-name').textContent = $('download-word').download;
    $('word-result-name').hidden = false;
    wordState('ready');
    $('download-word').focus();
  } catch (error) { $('status').textContent = ''; wordState('error'); fail(error); }
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
  const transfer = new DataTransfer(); transfer.items.add(file);
  $('document').files = transfer.files;
  $('document').dispatchEvent(new Event('change'));
});
