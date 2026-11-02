import assets from './assets.generated.mjs';

const security = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Content-Security-Policy': "default-src 'self'; style-src 'self'; font-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
};
function unavailable() {
  return Response.json({detail: 'الخدمة قيد التشغيل أو غير متاحة مؤقتًا. أعد المحاولة بعد قليل.'}, {
    status: 503, headers: {...security, 'Cache-Control': 'no-store', 'Retry-After': '3'},
  });
}
export default {
  async fetch(request) {
    const incoming = new URL(request.url);
    if (incoming.pathname === '/health' || incoming.pathname.startsWith('/api/')) {
      const upstream = new URL(incoming.pathname + incoming.search, 'https://tashkeel.onrender.com');
      const headers = new Headers(request.headers);
      headers.delete('host');
      try {
        const response = await fetch(upstream, {
          method: request.method, headers,
          body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
          redirect: 'manual',
        });
        // Never pass Render's HTML startup screen off as an API result/document.
        if ((response.headers.get('Content-Type') || '').includes('text/html') ||
            (response.status >= 300 && response.status < 400)) {
          await response.body?.cancel();
          return unavailable();
        }
        const output = new Response(response.body, response);
        output.headers.set('Cache-Control', 'no-store');
        for (const [name, value] of Object.entries(security)) output.headers.set(name, value);
        return output;
      } catch {
        return unavailable();
      }
    }
    if (!['GET', 'HEAD'].includes(request.method)) return new Response(null, {status: 405, headers: {Allow: 'GET, HEAD'}});
    const asset = Object.hasOwn(assets, incoming.pathname) ? assets[incoming.pathname] : null;
    if (!asset) return new Response('Not found', {status: 404, headers: security});
    const [type, encoded] = asset;
    return new Response(request.method === 'HEAD' ? null : Uint8Array.from(atob(encoded), c => c.charCodeAt(0)), {
      headers: {...security, 'Content-Type': type, 'Cache-Control': 'public, max-age=0, must-revalidate', 'X-Tashkeel-Frontend': 'cloudflare'},
    });
  },
};
