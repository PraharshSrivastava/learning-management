/* Run after compiling document_workflow_editor_spike.dart into tmp. No LMS services. */
const path = require('node:path');
const assert = require('node:assert/strict');
const playwright = require(require.resolve('playwright', {
  paths: [process.env.NODE_PATH || 'C:/Users/LPUSER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'],
}));

(async () => {
  const browser = await playwright.chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    timeout: 20000,
  });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<main aria-label="Editor spike"></main>');
    await page.addScriptTag({path: path.resolve(__dirname, '../../tmp/document-workflow-editor-spike.js')});
    await page.waitForFunction(() => document.documentElement.hasAttribute('data-spike-result'), {timeout: 15000});
    const result = await page.locator('html').getAttribute('data-spike-result');
    assert.equal(result, 'passed');
    assert.deepEqual(errors, []);
    console.log('Browser editor spike passed: selection, emoji, scoped edit, outside formatting, image position, neighbor content, stale proposal.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
