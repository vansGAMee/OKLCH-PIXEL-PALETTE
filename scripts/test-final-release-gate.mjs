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
    if (res.exceptionDetails) {
      throw new Error(`Eval exception: ${JSON.stringify(res.exceptionDetails)}`);
    }
    return res.result?.value;
  }

  return { ws, send, eval: evalExpression };
}

async function main() {
  console.log('=== RUNNING FINAL RELEASE GATE COMPREHENSIVE CHECKS ===\n');

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

    const resTarget = await fetch('http://127.0.0.1:9222/json/new?http://localhost:3000/', {
      method: 'PUT',
    });
    const target = await resTarget.json();
    const client = await createCdpClient(target.webSocketDebuggerUrl);

    await client.send('Page.enable');
    await client.send('Runtime.enable');
    await client.send('Network.enable');

    const networkRequests = [];
    const consoleErrors = [];

    client.ws.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      if (msg.method === 'Network.requestWillBeSent') {
        networkRequests.push(msg.params.request.url);
      }
      if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
        const text = msg.params.args.map((a) => a.value || a.description || '').join(' ');
        if (!text.includes('Failed to load script from /_vercel/insights/script.js')) {
          consoleErrors.push(text);
        }
      }
    });

    console.log('[Check 1] Homepage rendering and Network Lazy Loading...');
    await sleep(2000);

    // Verify 0 model/WASM downloads on homepage
    const modelRequestsOnHome = networkRequests.filter(
      (url) => url.includes('.onnx') || url.includes('.wasm') || url.includes('semantic-anchors.json')
    );
    console.log(`  Model/WASM requests on Homepage: ${modelRequestsOnHome.length} (must be 0)`);
    if (modelRequestsOnHome.length > 0) {
      throw new Error(`Homepage eagerly loaded AI model assets: ${modelRequestsOnHome.join(', ')}`);
    }

    console.log('\n[Check 2] Viewport Responsiveness & Layout...');
    const viewports = [
      { name: '320px (iPhone SE)', width: 320, height: 568 },
      { name: '360px (Galaxy S8)', width: 360, height: 740 },
      { name: '390px (iPhone 14)', width: 390, height: 844 },
      { name: '430px (iPhone 14 Pro Max)', width: 430, height: 932 },
      { name: 'Landscape mobile (844x390)', width: 844, height: 390 },
      { name: 'Desktop (1280x720)', width: 1280, height: 720 },
      { name: 'Desktop (1440x900)', width: 1440, height: 900 },
      { name: 'Desktop (1920x1080)', width: 1920, height: 1080 },
    ];

    for (const vp of viewports) {
      await client.send('Emulation.setDeviceMetricsOverride', {
        width: vp.width,
        height: vp.height,
        deviceScaleFactor: 1,
        mobile: vp.width < 1000,
      });
      await sleep(300);

      const overflow = await client.eval(`
        (() => {
          const docEl = document.documentElement;
          return {
            scrollWidth: docEl.scrollWidth,
            clientWidth: docEl.clientWidth,
            hasOverflow: docEl.scrollWidth > docEl.clientWidth
          };
        })()
      `);

      if (overflow.hasOverflow) {
        throw new Error(`Horizontal overflow detected on viewport ${vp.name}: ${JSON.stringify(overflow)}`);
      }
      console.log(`  Viewport ${vp.name}: scrollWidth=${overflow.scrollWidth}, clientWidth=${overflow.clientWidth} -> NO OVERFLOW`);
    }

    console.log('\n[Check 3] Accessibility & Keyboard interaction...');
    const a11y = await client.eval(`
      (() => {
        const input = document.querySelector('#ai-palette input[name="prompt"]');
        const btn = input?.closest('form')?.querySelector('button[type="submit"]');
        return {
          hasAriaLabel: !!input?.getAttribute('aria-label'),
          hasMaxLength: input?.getAttribute('maxLength') === '4096',
          btnText: btn?.textContent?.trim(),
          isButtonAccessible: !!btn && btn.offsetHeight > 0
        };
      })()
    `);
    console.log('  Accessibility audit result:', a11y);
    if (!a11y.hasAriaLabel || !a11y.isButtonAccessible) {
      throw new Error('Accessibility attributes missing on homepage prompt input');
    }

    console.log('\n[Check 4] Checking console errors...');
    console.log(`  Console errors count: ${consoleErrors.length} (must be 0)`);
    if (consoleErrors.length > 0) {
      throw new Error(`Console errors found: ${consoleErrors.join('\n')}`);
    }

    console.log('\n======================================================');
    console.log('✅ ALL FINAL RELEASE GATE COMPREHENSIVE CHECKS PASSED!');
    console.log('======================================================');
  } finally {
    chrome.kill();
  }
}

main().catch((err) => {
  console.error('Fatal gate check error:', err);
  process.exit(1);
});
