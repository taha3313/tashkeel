// TLS/domain gateway only. Application and model run on the dedicated Render service.
export default {
  async fetch(request) {
    const incoming = new URL(request.url);
    const upstream = new URL(incoming.pathname + incoming.search, 'https://tashkeel.onrender.com');
    const headers = new Headers(request.headers);
    headers.delete('host');
    headers.set('X-Forwarded-Host', incoming.hostname);
    try {
      const response = await fetch(upstream, {
        method: request.method, headers,
        body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
        redirect: 'manual',
      });
      const output = new Response(response.body, response);
      if (incoming.pathname.startsWith('/api/')) output.headers.set('Cache-Control', 'no-store');
      const location = output.headers.get('Location');
      if (location?.startsWith('https://tashkeel.onrender.com/')) {
        output.headers.set('Location', location.replace('https://tashkeel.onrender.com', incoming.origin));
      }
      return output;
    } catch {
      return new Response('الخدمة غير متاحة مؤقتًا. أعد المحاولة بعد قليل.', {
        status: 502, headers: {'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store'},
      });
    }
  },
};
