import {test} from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';
import assets from './assets.generated.mjs';

const request = (path, options) => new Request('https://tashkeel.tahachelly.com' + path, options);
test('all static assets and the page work when Render is unreachable', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {calls++; throw new Error('Render asleep');};
  try {
    for (const path of Object.keys(assets)) {
      const response = await worker.fetch(request(path + '?version=1'));
      assert.equal(response.status, 200, path);
      assert.equal(response.headers.get('X-Tashkeel-Frontend'), 'cloudflare');
      assert.deepEqual(Buffer.from(await response.arrayBuffer()), Buffer.from(assets[path][1], 'base64'));
    }
    assert.equal((await worker.fetch(request('/missing'))).status, 404);
    assert.equal((await worker.fetch(request('/toString'))).status, 404);
    assert.equal(await (await worker.fetch(request('/', {method: 'HEAD'}))).text(), '');
    assert.equal((await worker.fetch(request('/', {method: 'POST'}))).status, 405);
    assert.equal(calls, 0);
  } finally {globalThis.fetch = original;}
});
test('startup HTML becomes a retryable JSON response', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response('<html>Render starting</html>', {headers: {'Content-Type': 'text/html'}});
  try {
    for (const path of ['/health', '/api/document', '/api/tashkeel']) {
      const response = await worker.fetch(request(path));
      assert.equal(response.status, 503);
      assert.equal(response.headers.get('Cache-Control'), 'no-store');
      assert.ok((await response.json()).detail);
    }
  } finally {globalThis.fetch = original;}
});
test('forwards submissions once and preserves binary document downloads', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  const bytes = new Uint8Array([80, 75, 0, 255, 1]);
  globalThis.fetch = async (url, options) => {
    calls++;
    assert.equal(String(url), 'https://tashkeel.onrender.com/api/document');
    assert.equal(options.method, 'POST');
    assert.equal(await new Response(options.body).text(), 'document upload');
    return new Response(bytes, {headers: {'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'Content-Disposition': 'attachment; filename="tashkeel.docx"'}});
  };
  try {
    const response = await worker.fetch(request('/api/document', {method: 'POST', body: 'document upload'}));
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()), bytes);
    assert.match(response.headers.get('Content-Disposition'), /tashkeel.docx/);
    assert.equal(calls, 1);
  } finally {globalThis.fetch = original;}
});
