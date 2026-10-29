import assert from 'node:assert/strict';
import test from 'node:test';
import worker from '../cloudflare-worker.js';

test('the static proxy preserves content types, caching, status, and query strings', async t => {
  let upstream;
  t.mock.method(globalThis, 'fetch', async url => {
    upstream = url;
    return new Response('wasm', {
      status: 206,
      headers: { 'Content-Type': 'application/wasm', 'Cache-Control': 'public, max-age=3600', ETag: '"runtime"' },
    });
  });
  const response = await worker.fetch(new Request('https://site.test/pyodide/314.0.7/pyodide.asm.wasm?v=1'));
  assert.equal(upstream, 'https://aelqazouiinsights.github.io/investment-management-with-python-and-machine-learning-specialization/pyodide/314.0.7/pyodide.asm.wasm?v=1');
  assert.equal(response.status, 206);
  assert.equal(response.headers.get('Content-Type'), 'application/wasm');
  assert.equal(response.headers.get('Cache-Control'), 'public, max-age=3600');
  assert.equal(response.headers.get('ETag'), '"runtime"');
  assert.equal(response.headers.get('Cross-Origin-Opener-Policy'), 'same-origin');
  assert.equal(response.headers.get('Cross-Origin-Embedder-Policy'), 'require-corp');
  assert.equal(await response.text(), 'wasm');
});

test('missing runtime assets remain HTTP 404 rather than becoming successful responses', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('Missing', { status: 404 }));
  const response = await worker.fetch(new Request('https://site.test/missing.whl'));
  assert.equal(response.status, 404);
});
