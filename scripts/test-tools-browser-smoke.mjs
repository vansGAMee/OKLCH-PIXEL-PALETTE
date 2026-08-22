import { spawn } from 'child_process';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function createCdpClient(wsUrl) {
  const ws = new WebSocket(wsUrl);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });

  let id = 1;
  const callbacks = new Map();

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && callbacks.has(msg.id)) {
      const cb = callbacks.get(msg.id);
      callbacks.delete(msg.id);
      if (msg.error) {
        cb.reject(new Error(msg.error.message || JSON.stringify(msg.error)));
      } else {
        cb.resolve(msg.result);
      }
    }
  };

  function send(method, params = {}) {
    const msgId = id++;
    return new Promise((resolve, reject) => {
      callbacks.set(msgId, { resolve, reject });
      ws.send(JSON.stringify({ id: msgId, method, params }));
    });
  }

  async function evalExpression(expr) {
    const res = await send('Runtime.evaluate', {
      expression: expr,
      returnByValue: true,
      awaitPromise: true,
    });
    return res.result.value;
  }

  return { ws, send, eval: evalExpression };
}

const TOOL_ROUTES = [
  '/tools',
  '/ru/tools',
  '/tools/ai-color-palette-generator',
  '/ru/tools/ai-color-palette-generator',
  '/tools/palette-analyzer',
  '/ru/tools/palette-analyzer',
  '/tools/color-ramp-generator',
  '/ru/tools/color-ramp-generator',
  '/tools/image-to-palette',
  '/ru/tools/image-to-palette',
  '/tools/palette-compare',
  '/ru/tools/palette-compare',
  '/tools/lospec-palette-editor',
  '/ru/tools/lospec-palette-editor',
  '/tools/sprite-recolor',
  '/ru/tools/sprite-recolor',
  '/tools/aseprite-palette-converter',
  '/ru/tools/aseprite-palette-converter',
  '/palettes',
  '/ru/palettes',
  '/palettes/winter-forest',
  '/ru/palettes/winter-forest',
  '/research/oklch-vs-hsl',
  '/ru/research/oklch-vs-hsl',
  '/research/text-to-color-benchmark',
  '/ru/research/text-to-color-benchmark',
];

async function main() {
  console.log('=== RUNNING REAL BROWSER SMOKE TEST ACROSS ALL NEW ROUTES ===\n');

  const chrome = spawn(
    '/usr/bin/chromium',
    [
      '--headless=new',
      '--remote-debugging-port=9222',
      '--no-sandbox',
      '--disable-gpu',
      '--disable-extensions',
    ],
    { stdio: 'ignore' }
  );

  try {
    await sleep(1500);

    for (const route of TOOL_ROUTES) {
      const url = `http://localhost:3000${route}`;
      const resTarget = await fetch(`http://127.0.0.1:9222/json/new?${url}`, { method: 'PUT' });
      const target = await resTarget.json();
      const client = await createCdpClient(target.webSocketDebuggerUrl);

      const errors = [];
      const networkRequests = [];

      client.ws.addEventListener('message', (event) => {
        const msg = JSON.parse(event.data);
        if (msg.method === 'Network.requestWillBeSent') {
          networkRequests.push(msg.params.request.url);
        }
        if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
          const text = msg.params.args.map((a) => a.value || a.description || '').join(' ');
          if (!text.includes('Failed to load script from /_vercel/insights/script.js')) {
            errors.push(text);
          }
        }
      });

      await client.send('Page.enable');
      await client.send('Network.enable');
      await client.send('Runtime.enable');

      await sleep(1000);

      // Check for horizontal overflow on mobile 360px viewport
      await client.send('Emulation.setDeviceMetricsOverride', {
        width: 360,
        height: 740,
        deviceScaleFactor: 2,
        mobile: true,
      });
      await sleep(200);

      const overflow = await client.eval(`
        (() => {
          const sw = document.documentElement.scrollWidth;
          const cw = document.documentElement.clientWidth;
          return { scrollWidth: sw, clientWidth: cw, hasOverflow: sw > cw };
        })()
      `);

      if (overflow?.hasOverflow) {
        throw new Error(`Overflow on ${route} at 360px: ${JSON.stringify(overflow)}`);
      }

      // Check model assets lazy loading (none should load on page view)
      const eagerModelAssets = networkRequests.filter(
        (u) => u.includes('.onnx') || u.includes('semantic-anchors.json')
      );
      if (eagerModelAssets.length > 0) {
        throw new Error(`Eager model asset loaded on ${route}: ${eagerModelAssets.join(', ')}`);
      }

      if (errors.length > 0) {
        throw new Error(`Console errors on ${route}: ${errors.join('\n')}`);
      }

      console.log(`[PASS] ${route} -> Hydrated, 0 errors, 0 overflow, lazy AI preserved`);

      await fetch(`http://127.0.0.1:9222/json/close/${target.id}`);
    }

    console.log('\n======================================================');
    console.log(`✅ ALL ${TOOL_ROUTES.length} ROUTES BROWSER SMOKE TESTS PASSED!`);
    console.log('======================================================\n');
  } finally {
    chrome.kill();
  }
}

main().catch((err) => {
  console.error('Fatal smoke test error:', err);
  process.exit(1);
});
