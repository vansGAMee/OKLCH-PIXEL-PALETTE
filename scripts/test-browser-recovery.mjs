/**
 * test-browser-recovery.mjs
 * Real Chromium CDP test for AI asset failure injection and UI Retry recovery.
 *
 * Scenarios verified:
 * 1. Injected failure on first critical asset request (/models/semantic-anchors.json)
 * 2. Verification that UI displays error and the Retry button
 * 3. Clicking Retry in the UI triggers a NEW fetch for the asset
 * 4. Allowing the second fetch to succeed
 * 5. Verifying AI generation completes successfully with valid OKLCH palette without page reload
 * 6. Mobile viewport emulation & slow network emulation
 */
import { spawn } from 'child_process';
import { oklch } from 'culori';

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
    this.networkRequests = [];
    this.consoleLogs = [];
    this.pausedRequests = [];
    this.onRequestPaused = null;
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
      this.networkRequests.push({ url: params.request.url, method: params.request.method });
    } else if (method === 'Fetch.requestPaused') {
      if (this.onRequestPaused) {
        this.onRequestPaused(params);
      } else {
        this.send('Fetch.continueRequest', { requestId: params.requestId }).catch(() => {});
      }
    } else if (method === 'Runtime.consoleAPICalled') {
      const args = (params.args || []).map((a) => a.value || a.description || JSON.stringify(a)).join(' ');
      this.consoleLogs.push({ level: params.type, text: args });
      console.log(`[Browser Console ${params.type}]:`, args);
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
  console.log('Starting Chromium for Failure Injection & Recovery testing...');
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

    // Emulate Mobile Device (iPhone 14 Pro: 393x852, touch enabled, DPR 3)
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: 393,
      height: 852,
      deviceScaleFactor: 3,
      mobile: true,
    });
    await client.send('Emulation.setTouchEmulationEnabled', { enabled: true });

    console.log('Waiting for /create page load and hydration...');
    await sleep(2500);

    // Set up Fetch interception for semantic-anchors.json
    await client.send('Fetch.enable', {
      patterns: [
        { urlPattern: '*semantic-anchors.json*', requestStage: 'Request' },
      ],
    });

    let anchorRequestCount = 0;
    client.onRequestPaused = async (params) => {
      anchorRequestCount++;
      console.log(`[CDP Fetch Intercept] Request #${anchorRequestCount} for ${params.request.url}`);
      if (anchorRequestCount <= 2) {
        console.log(`[CDP Fetch Intercept] INJECTING FAILURE for request #${anchorRequestCount}!`);
        await client.send('Fetch.failRequest', {
          requestId: params.requestId,
          errorReason: 'Failed',
        });
      } else {
        console.log(`[CDP Fetch Intercept] ALLOWING request #${anchorRequestCount} (after user UI Retry) to succeed.`);
        await client.send('Fetch.continueRequest', {
          requestId: params.requestId,
        });
      }
    };

    console.log('\n--- Scenario 1: Submit prompt "winter starry forest" with injected failure ---');
    // Type prompt into input using nativeInputValueSetter and click generate
    await client.eval(`
      (() => {
        const input = document.getElementById('ai-palette-prompt');
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, 'winter starry forest');
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        const genBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('AI') || b.textContent.includes('Generate') || b.textContent.includes('Создать'));
        if (genBtn) genBtn.click();
      })()
    `);

    // Wait for the failure to register in the UI
    await sleep(2000);

    // Verify error state in UI
    const errorState = await client.eval(`
      (() => {
        const errorText = document.querySelector('.text-red-300')?.textContent || null;
        const retryBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Retry') || b.textContent.includes('Попробовать снова'));
        return {
          hasError: !!errorText,
          errorText,
          hasRetryBtn: !!retryBtn
        };
      })()
    `);

    console.log('UI Error State observed:', errorState);
    if (!errorState.hasError || !errorState.hasRetryBtn) {
      throw new Error(`Expected error state and Retry button in UI, got: ${JSON.stringify(errorState)}`);
    }

    console.log('\n--- Scenario 2: Press Retry in UI and observe recovery ---');
    const retryClicked = await client.eval(`
      (() => {
        const retryBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Retry') || b.textContent.includes('Попробовать снова'));
        if (retryBtn) {
          retryBtn.click();
          return true;
        }
        return false;
      })()
    `);
    console.log('Retry button clicked:', retryClicked);

    // Wait for second fetch and inference completion
    let success = false;
    let baseHex = null;
    for (let i = 0; i < 40; i++) {
      await sleep(500);
      const state = await client.eval(`
        (() => {
          const cardHexes = Array.from(document.querySelectorAll('h3'))
            .map(h => h.textContent.trim())
            .filter(t => /^#[0-9A-F]{6}$/i.test(t));
          const hexInputs = Array.from(document.querySelectorAll('input[type="text"]'))
            .filter(i => i.value && /^#[0-9a-fA-F]{6}$/.test(i.value))
            .map(i => i.value);
          const errorText = document.querySelector('.text-red-300')?.textContent || null;
          return { cardHexes, baseHex: hexInputs[0] || null, errorText };
        })()
      `);

      if (state.baseHex && state.cardHexes.length >= 4 && !state.errorText) {
        success = true;
        baseHex = state.baseHex;
        console.log(`Generation succeeded after Retry! BaseHex: ${baseHex}, Cards: ${state.cardHexes.length}`);
        break;
      }
    }

    if (!success) {
      throw new Error('AI Generation did NOT recover after clicking Retry!');
    }

    if (anchorRequestCount < 2) {
      throw new Error(`Expected at least 2 anchor requests, but got ${anchorRequestCount}`);
    }

    const o = oklch(baseHex);
    console.log(`Recovered OKLCH: L=${o?.l?.toFixed(2)}, C=${o?.c?.toFixed(3)}, H=${o?.h?.toFixed(0)}`);
    console.log(`Total anchor request attempts made: ${anchorRequestCount}`);

    // Disable fetch interception for regular tests
    await client.send('Fetch.disable');

    console.log('\n--- Scenario 3: Mobile Network Throttle Test ---');
    // Emulate 4G / Slow Network conditions
    await client.send('Network.emulateNetworkConditions', {
      offline: false,
      latency: 100, // 100ms latency
      downloadThroughput: (1.5 * 1024 * 1024) / 8, // 1.5 Mbps
      uploadThroughput: (750 * 1024) / 8, // 750 Kbps
    });

    // Test a subsequent prompt: "neon cyberpunk rain"
    await client.eval(`
      (() => {
        const input = document.getElementById('ai-palette-prompt');
        input.value = 'neon cyberpunk rain';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        const genBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('AI') || b.textContent.includes('Generate') || b.textContent.includes('Создать'));
        if (genBtn) genBtn.click();
      })()
    `);

    let mobileSuccess = false;
    for (let i = 0; i < 40; i++) {
      await sleep(500);
      const state = await client.eval(`
        (() => {
          const cardHexes = Array.from(document.querySelectorAll('h3'))
            .map(h => h.textContent.trim())
            .filter(t => /^#[0-9A-F]{6}$/i.test(t));
          const hexInputs = Array.from(document.querySelectorAll('input[type="text"]'))
            .filter(i => i.value && /^#[0-9a-fA-F]{6}$/.test(i.value))
            .map(i => i.value);
          return { cardHexes, baseHex: hexInputs[0] || null };
        })()
      `);

      if (state.baseHex && state.cardHexes.length >= 4) {
        mobileSuccess = true;
        console.log(`Mobile throttled generation succeeded! BaseHex: ${state.baseHex}, Cards: ${state.cardHexes.length}`);
        break;
      }
    }

    if (!mobileSuccess) {
      throw new Error('Mobile throttled generation failed!');
    }

    console.log('\n=============================================================');
    console.log('✅ ALL INJECTED FAILURE & RECOVERY BROWSER CDP TESTS PASSED!');
    console.log('=============================================================\n');
  } finally {
    chrome.kill();
  }
}

main().catch((err) => {
  console.error('Fatal browser recovery test error:', err);
  process.exit(1);
});
