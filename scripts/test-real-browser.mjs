/**
 * test-real-browser.mjs
 * Uses real Chromium via Chrome DevTools Protocol (CDP) to test /create in a real browser.
 */
import { spawn } from 'child_process';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function getBrowserWsUrl() {
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch('http://127.0.0.1:9222/json/version');
      if (res.ok) {
        const data = await res.json();
        return data.webSocketDebuggerUrl;
      }
    } catch {
      // retry
    }
    await sleep(200);
  }
  throw new Error('Chromium did not start CDP in time');
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.id = 1;
    this.callbacks = new Map();
    this.events = [];
    this.networkRequests = [];
    this.consoleLogs = [];
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
    });

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.callbacks.has(msg.id)) {
        const { resolve, reject } = this.callbacks.get(msg.id);
        this.callbacks.delete(msg.id);
        if (msg.error) reject(msg.error);
        else resolve(msg.result);
      } else if (msg.method) {
        this.handleEvent(msg.method, msg.params);
      }
    };
  }

  handleEvent(method, params) {
    if (method === 'Network.requestWillBeSent') {
      this.networkRequests.push({ url: params.request.url, method: params.request.method, type: params.type });
    } else if (method === 'Network.responseReceived') {
      const existing = this.networkRequests.find(r => r.url === params.response.url);
      if (existing) {
        existing.status = params.response.status;
        existing.mimeType = params.response.mimeType;
      }
    } else if (method === 'Console.messageAdded') {
      this.consoleLogs.push({ level: params.message.level, text: params.message.text });
      console.log(`[Browser Console ${params.message.level}]:`, params.message.text);
    } else if (method === 'Runtime.consoleAPICalled') {
      const args = (params.args || []).map(a => a.value || a.description || JSON.stringify(a)).join(' ');
      this.consoleLogs.push({ level: params.type, text: args });
      console.log(`[Browser Console API ${params.type}]:`, args);
    } else if (method === 'Runtime.exceptionThrown') {
      console.error(`[Browser Exception]:`, params.exceptionDetails.text, params.exceptionDetails.exception?.description);
      this.consoleLogs.push({ level: 'error', text: params.exceptionDetails.text });
    }
  }

  send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolve, reject) => {
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res.exceptionDetails) {
      throw new Error(`Eval error: ${res.exceptionDetails.text}`);
    }
    return res.result?.value;
  }
}

async function main() {
  console.log('Starting Chromium in headless mode...');
  const chrome = spawn('/usr/bin/chromium', [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
  ], { stdio: 'ignore' });

  try {
    const wsUrl = await getBrowserWsUrl();
    console.log('Connected to Chromium CDP at:', wsUrl);

    // Create a new target page
    const resTarget = await fetch('http://127.0.0.1:9222/json/new?http://localhost:3000/create', { method: 'PUT' });
    const targetData = await resTarget.json();
    console.log('Opened target:', targetData.id, targetData.url);

    const client = new CdpClient(targetData.webSocketDebuggerUrl);
    await client.connect();

    await client.send('Page.enable');
    await client.send('DOM.enable');
    await client.send('Runtime.enable');
    await client.send('Network.enable');
    await client.send('Console.enable');

    console.log('Waiting for /create page load and hydration...');
    await sleep(3000);

    // Verify no hydration error in logs
    const hydrationErrors = client.consoleLogs.filter(l =>
      l.text && (l.text.toLowerCase().includes('hydration') || l.text.toLowerCase().includes('mismatch'))
    );
    console.log('Hydration errors found:', hydrationErrors.length);

    // Verify model is not loaded prior to AI interaction
    const preAiModelRequests = client.networkRequests.filter(r => r.url.includes('/models/'));
    console.log('Pre-AI model requests count (must be 0):', preAiModelRequests.length);

    // Helper to run AI query in browser
    async function testAiQuery(prompt) {
      console.log(`\n=== Testing AI Query: "${prompt}" ===`);
      const t0 = Date.now();

      try {
        await client.eval(`
          (async () => {
            if (window.__generateAiPalette) {
              await window.__generateAiPalette('${prompt}');
            } else {
              throw new Error('window.__generateAiPalette is not defined');
            }
          })()
        `);
      } catch (err) {
        console.error('Inference error:', err);
        console.log('Network requests so far:', client.networkRequests);
        throw err;
      }

      await sleep(300);

      const state = await client.eval(`
        (() => {
          const cardHexes = Array.from(document.querySelectorAll('h3'))
            .map(h => h.textContent.trim())
            .filter(t => /^#[0-9A-F]{6}$/i.test(t));

          const hexInputs = Array.from(document.querySelectorAll('input[type="text"]'))
            .filter(i => i.value && /^#[0-9a-fA-F]{6}$/.test(i.value))
            .map(i => i.value);

          return {
            cardHexes,
            baseHex: hexInputs[0] || null
          };
        })()
      `);

      const elapsed = Date.now() - t0;
      console.log(`AI Query "${prompt}" completed in ${elapsed}ms!`);
      console.log('Result Base / State:', JSON.stringify(state));
      return { prompt, elapsed, state };
    }

    // 1. Test "winter"
    const resWinter = await testAiQuery('winter');

    // 2. Test "purple"
    const resPurple = await testAiQuery('purple');

    // 3. Test "фиолетовый"
    const resFiolet = await testAiQuery('фиолетовый');

    // 4. Test "заброшенная больница ночью"
    const resHospital = await testAiQuery('заброшенная больница ночью');

    // Inspect network requests
    console.log('\n=== Network Inspection ===');
    const modelReqs = client.networkRequests.filter(r => r.url.includes('/models/') || r.url.includes('/ort/'));
    console.log(`Total local AI model/WASM requests: ${modelReqs.length}`);
    for (const r of modelReqs) {
      console.log(`  ${r.method} ${r.url} -> Status: ${r.status || 'pending/done'}`);
    }

    const externalHfReqs = client.networkRequests.filter(r => r.url.includes('huggingface.co'));
    console.log(`HuggingFace external requests count (must be 0): ${externalHfReqs.length}`);

    // Inspect console errors
    const errors = client.consoleLogs.filter(l => l.level === 'error');
    console.log(`Browser console errors count: ${errors.length}`);
    for (const err of errors) {
      console.log(`  Error: ${err.text}`);
    }

    console.log('\n=== BROWSER TEST COMPLETE ===');
  } finally {
    chrome.kill();
  }
}

main().catch(err => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
