/**
 * test-real-browser.mjs
 * Uses real Chromium via Chrome DevTools Protocol (CDP) to test /create in a real browser.
 */
import { spawn } from 'child_process';
import { existsSync, mkdirSync, writeFileSync } from 'fs';
import path from 'path';
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
  const chromeCandidates = [
    process.env.CHROME_PATH,
    '/usr/bin/chromium',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  ].filter(Boolean);
  const chromePath = chromeCandidates.find((candidate) => existsSync(candidate));
  if (!chromePath) throw new Error('No Chromium executable found; set CHROME_PATH');
  const chrome = spawn(chromePath, [
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

    // 1. Verify no hydration error in logs
    const hydrationErrors = client.consoleLogs.filter(l =>
      l.text && (l.text.toLowerCase().includes('hydration') || l.text.toLowerCase().includes('mismatch'))
    );
    console.log('Hydration errors count (must be 0):', hydrationErrors.length);
    if (hydrationErrors.length > 0) {
      throw new Error('Hydration errors detected!');
    }

    // 2. Verify model is not loaded prior to AI interaction
    const preAiModelRequests = client.networkRequests.filter(r => r.url.includes('/models/'));
    console.log('Pre-AI model requests count (must be 0):', preAiModelRequests.length);
    if (preAiModelRequests.length > 0) {
      throw new Error('Models were requested before user AI trigger!');
    }

    const manifestResponse = await fetch('http://localhost:3000/models/palettebrain-v2.manifest.json');
    if (!manifestResponse.ok) throw new Error(`Could not load PaletteBrain manifest: ${manifestResponse.status}`);
    const declaredManifest = await manifestResponse.json();
    const declaredModelVersion = declaredManifest.modelVersion;
    const declaredDecoderPath = declaredManifest.decoder?.path || declaredManifest.decoder?.url;
    if (!declaredModelVersion || !declaredDecoderPath) {
      throw new Error('PaletteBrain manifest is missing modelVersion or decoder path');
    }

    const openedAiMode = await client.eval(`
      (() => {
        const button = Array.from(document.querySelectorAll('button')).find((item) =>
          item.textContent.trim() === 'AI' || item.textContent.includes('AI')
        );
        if (!button) return false;
        button.click();
        return true;
      })()
    `);
    if (!openedAiMode) throw new Error('Could not activate AI mode');
    await sleep(250);

    // 3. Helper to run AI query in browser
    async function testAiQuery(prompt) {
      console.log(`\n=== Testing In-Browser AI: "${prompt}" ===`);
      const t0 = Date.now();

      try {
        await client.eval(`
          (async () => {
            if (window.__generateAiPalette) {
              const generated = await window.__generateAiPalette(${JSON.stringify(prompt)});
              if (!generated) throw new Error('AI generation hook returned false');
              return generated;
            } else {
              throw new Error('window.__generateAiPalette is not defined');
            }
          })()
        `);
      } catch (err) {
        console.error('Inference error in browser:', err);
        throw err;
      }

      await sleep(400);

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
            baseHex: hexInputs[0] || cardHexes[1] || null,
            neural: window.__paletteBrainLastResult || null
          };
        })()
      `);

      const elapsed = Date.now() - t0;
      const baseHex = state.baseHex;
      const o = baseHex ? oklch(baseHex) : null;
      if (!state.neural || state.neural.fallback !== false) {
        console.error('Neural diagnostic state:', JSON.stringify(state.neural));
        throw new Error(`FAIL: ${prompt} did not return a real neural result`);
      }
      if (state.neural.modelVersion !== declaredModelVersion) {
        throw new Error(`FAIL: wrong model loaded: ${state.neural.modelVersion}`);
      }
      if (!Array.isArray(state.neural.colors) || state.neural.colors.length < 2 || state.neural.colors.length > 9) {
        throw new Error(`FAIL: invalid neural palette count for ${prompt}`);
      }
      console.log(`AI Query "${prompt}" completed in ${elapsed}ms!`);
      console.log(`Result Base: ${baseHex} (L=${o?.l?.toFixed(2)}, C=${o?.c?.toFixed(3)}, H=${o?.h?.toFixed(0) || 'neutral'})`);
      console.log(`Card hexes (${state.cardHexes.length}):`, state.cardHexes.join(', '));
      return { prompt, elapsed, state, baseHex, oklch: o, colors: state.neural.colors };
    }

    const requiredPrompts = [
      'rain', 'дождь', 'grass', 'трава', 'leaf', 'лист', 'hospital', 'больница',
      'fog', 'туман', 'snow', 'снег', 'forest', 'glass', 'rust', 'moonlight',
      'watercolor', 'film noir', 'gothic cathedral', 'constructivist poster',
      'winter forest at night', 'зимний лес ночью',
      'abandoned hospital in winter at night', 'заброшенная больница зимой ночью',
      'warm childhood kitchen', 'уютная кухня из детства',
      'painful nostalgia', 'болезненная ностальгия', 'quiet dread', 'тихая тревога',
      'red', 'красный', 'red and blue', 'not red',
      'a watercolor city after heavy rain, pale morning light reflecting from wet stone streets',
    ];
    const semanticResults = [];
    for (const prompt of requiredPrompts) semanticResults.push(await testAiQuery(prompt));

    const redResult = semanticResults.find((row) => row.prompt === 'red');
    const redHueWins = redResult.colors.filter((color) => color.h !== null && (color.h <= 50 || color.h >= 345)).length;
    if (redHueWins < Math.ceil(redResult.colors.length * 0.6)) {
      throw new Error('FAIL: explicit red control is not predominantly red');
    }
    const grassResult = semanticResults.find((row) => row.prompt === 'grass');
    const grassHueWins = grassResult.colors.filter((color) => color.h !== null && color.h >= 100 && color.h <= 165).length;
    const smokeReportPath = path.resolve('ml/palettebrain/reports/real-browser-semantic-smoke.json');
    mkdirSync(path.dirname(smokeReportPath), { recursive: true });
    writeFileSync(smokeReportPath, `${JSON.stringify({
      schemaVersion: 1,
      testClassification: 'REAL_BROWSER',
      modelVersion: semanticResults[0]?.state.neural.modelVersion,
      fallbackUsed: semanticResults.some((row) => row.state.neural.fallback !== false),
      promptCount: semanticResults.length,
      explicitRedPass: redHueWins >= Math.ceil(redResult.colors.length * 0.6),
      grassSemanticPass: grassHueWins >= Math.ceil(grassResult.colors.length * 0.4),
      pass: redHueWins >= Math.ceil(redResult.colors.length * 0.6)
        && grassHueWins >= Math.ceil(grassResult.colors.length * 0.4),
      results: semanticResults,
    }, null, 2)}\n`, 'utf8');
    if (grassHueWins < Math.ceil(grassResult.colors.length * 0.4)) {
      throw new Error('FAIL: grass semantic family is grossly wrong');
    }

    // 4. Verify count selector in UI
    console.log('\n=== Testing Color Count Selector in Browser ===');
    const count6Result = await client.eval(`
      (() => {
        const countBtns = Array.from(document.querySelectorAll('button')).filter(b => b.textContent.trim() === '6');
        if (countBtns.length > 0) {
          countBtns[0].click();
          return true;
        }
        return false;
      })()
    `);
    console.log('Clicked color count 6:', count6Result);
    await testAiQuery('cyberpunk neon');

    // 5. Inspect network requests
    console.log('\n=== Network Request Verification ===');
    const modelReqs = client.networkRequests.filter(r =>
      r.url.includes('/models/') || r.url.includes('/_next/static/media/ort-')
    );
    console.log(`Total local AI model/WASM requests: ${modelReqs.length}`);
    for (const r of modelReqs) {
      console.log(`  ${r.method} ${r.url} -> Status: ${r.status || '200'}`);
    }
    if (!modelReqs.some((request) => request.url.endsWith(declaredDecoderPath))) {
      throw new Error('Exact Candidate 11 ONNX artifact was not requested');
    }

    const externalHfReqs = client.networkRequests.filter(r =>
      r.url.includes('huggingface.co') ||
      r.url.includes('openai.com') ||
      r.url.includes('anthropic.com') ||
      r.url.includes('googleapis.com')
    );
    console.log(`External AI / HuggingFace requests count (must be 0): ${externalHfReqs.length}`);
    if (externalHfReqs.length > 0) {
      throw new Error(`Remote API calls detected: ${JSON.stringify(externalHfReqs)}`);
    }

    // 6. Inspect console errors
    const errors = client.consoleLogs.filter(l => l.level === 'error');
    console.log(`Browser console errors count: ${errors.length}`);
    for (const err of errors) {
      console.log(`  Error: ${err.text}`);
    }
    if (errors.length > 0) {
      throw new Error(`Browser console errors detected: ${JSON.stringify(errors)}`);
    }

    console.log('\n========================================');
    console.log('✅ ALL REAL BROWSER CDP TESTS PASSED!');
    console.log('========================================\n');
  } finally {
    chrome.kill();
  }
}

main().catch(err => {
  console.error('Fatal browser test error:', err);
  process.exit(1);
});
