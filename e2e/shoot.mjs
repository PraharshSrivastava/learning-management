// Screenshot helper for parity checks: node e2e/shoot.mjs <url> <out.png> [clickText...]
import { chromium } from '@playwright/test'

const [url, out, ...clicks] = process.argv.slice(2)
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.on('console', (msg) => msg.type() === 'error' && console.error('console:', msg.text()))
page.on('pageerror', (err) => console.error('pageerror:', err.message))
await page.goto(url, { waitUntil: 'networkidle' })
for (const text of clicks) {
  await page.getByText(text, { exact: true }).first().click()
  await page.waitForLoadState('networkidle')
}
await page.waitForTimeout(500)
await page.screenshot({ path: out })
await browser.close()
