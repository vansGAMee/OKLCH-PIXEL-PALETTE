import { spawn } from 'child_process';
import { oklch } from 'culori';

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
  console.log('Starting Chromium to test Homepage -> Generator AI Prompt flow...');
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

    // Open homepage
    const resTarget = await fetch('http://127.0.0.1:9222/json/new?http://localhost:3000/', {
      method: 'PUT',
    });
    const target = await resTarget.json();
    const client = await createCdpClient(target.webSocketDebuggerUrl);

    await client.send('Page.enable');
    await client.send('Runtime.enable');

    console.log('Waiting for homepage load...');
    await sleep(2000);

    console.log('\n--- Scenario 1: English Homepage prompt entry and submit ---');
    const inputFound = await client.eval(`
      (() => {
        const input = document.querySelector('#ai-palette input[name="prompt"]');
        return !!input;
      })()
    `);
    console.log('Homepage prompt input present in DOM:', inputFound);
    if (!inputFound) throw new Error('Homepage prompt input not found!');

    // Type "deep sea horror" into prompt and submit
    await client.eval(`
      (() => {
        const input = document.querySelector('#ai-palette input[name="prompt"]');
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, 'deep sea horror');
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        const form = input.closest('form');
        const btn = form.querySelector('button[type="submit"]');
        btn.click();
      })()
    `);

    // Wait for redirect to /create
    await sleep(3000);

    const currentUrl = await client.eval(`window.location.href`);
    console.log('Navigated URL:', currentUrl);
    if (!currentUrl.includes('/create?prompt=')) {
      throw new Error(`Expected redirect to /create?prompt=..., got: ${currentUrl}`);
    }

    // Wait for palette generation on /create
    await sleep(3000);

    const generatedBase = await client.eval(`
      (() => {
        const hexInputs = Array.from(document.querySelectorAll('input[type="text"]'))
          .filter(i => i.value && /^#[0-9a-fA-F]{6}$/.test(i.value))
          .map(i => i.value);
        const promptVal = document.getElementById('ai-palette-prompt')?.value;
        return {
          baseHex: hexInputs[0] || null,
          promptInStudio: promptVal || null,
        };
      })()
    `);

    console.log('Generator Result from Homepage prompt:', generatedBase);
    if (!generatedBase.baseHex || generatedBase.promptInStudio !== 'deep sea horror') {
      throw new Error(`Prompt flow failed: ${JSON.stringify(generatedBase)}`);
    }

    const o = oklch(generatedBase.baseHex);
    console.log(`OKLCH generated: L=${o?.l?.toFixed(2)}, C=${o?.c?.toFixed(3)}, H=${o?.h?.toFixed(0)}`);

    console.log('\n--- Scenario 2: Russian Homepage chip click ---');
    await client.eval(`window.location.href = 'http://localhost:3000/ru'`);
    await sleep(2500);

    // Click chip for "бледно-розовый рассвет"
    const chipClicked = await client.eval(`
      (() => {
        const chip = Array.from(document.querySelectorAll('#ai-palette button')).find(b => b.textContent.includes('бледно-розовый рассвет'));
        if (chip) {
          chip.click();
          return true;
        }
        return false;
      })()
    `);

    console.log('Russian suggestion chip clicked:', chipClicked);
    if (!chipClicked) throw new Error('Russian suggestion chip not found');

    await sleep(3000);
    const ruUrl = await client.eval(`window.location.href`);
    console.log('Navigated Russian URL:', decodeURIComponent(ruUrl));
    if (!ruUrl.includes('/ru/create?prompt=')) {
      throw new Error(`Expected redirect to /ru/create?prompt=..., got: ${ruUrl}`);
    }

    // Wait for Russian AI generation
    await sleep(3000);
    const ruResult = await client.eval(`
      (() => {
        const hexInputs = Array.from(document.querySelectorAll('input[type="text"]'))
          .filter(i => i.value && /^#[0-9a-fA-F]{6}$/.test(i.value))
          .map(i => i.value);
        const promptVal = document.getElementById('ai-palette-prompt')?.value;
        return {
          baseHex: hexInputs[0] || null,
          promptInStudio: promptVal || null,
        };
      })()
    `);

    console.log('Russian Generator Result:', ruResult);
    if (!ruResult.baseHex || ruResult.promptInStudio !== 'бледно-розовый рассвет') {
      throw new Error(`Russian prompt flow failed: ${JSON.stringify(ruResult)}`);
    }

    console.log('\n=================================================');
    console.log('✅ ALL HOMEPAGE -> GENERATOR AI FLOW TESTS PASSED!');
    console.log('=================================================');
  } finally {
    chrome.kill();
  }
}

main().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
