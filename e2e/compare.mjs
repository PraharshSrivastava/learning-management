// Old-vs-new screenshots for the migration PR.
// Usage: node e2e/compare.mjs <flutter|react> <out-dir> [shot-name...]
// Needs the lms-e2e backend and seed. Flutter: trainer :6969, employee :6970. React: :5173, :5174.
import { chromium } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const [flavor, outDir, ...only] = process.argv.slice(2)
if (flavor !== 'flutter' && flavor !== 'react') throw new Error('flavor must be flutter or react')
const host = process.env.LMS_E2E_HOST ?? '127.0.0.1'
const ports =
  flavor === 'flutter' ? { trainer: 6969, employee: 6970 } : { trainer: 5173, employee: 5174 }

// Flutter draws to a canvas, so text clicks need its semantics tree.
async function enableSemantics(page) {
  if (flavor !== 'flutter') return
  const button = page.locator('flt-semantics-placeholder')
  if (await button.count()) await button.evaluate((el) => el.click())
  await page.waitForTimeout(800)
}

async function settle(page, ms = 1200) {
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.waitForTimeout(ms)
}

async function click(page, text, exact = true) {
  // Flutter merges a card's texts into one button label, so also match buttons by label.
  const escaped = text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const button = page.getByRole('button', { name: new RegExp(exact ? `^${escaped}` : escaped) })
  await page.getByText(text, { exact }).or(button).first().click()
  await settle(page)
}

async function trainer(page, user) {
  await page.goto(`http://${host}:${ports.trainer}/`, { waitUntil: 'networkidle' })
  await settle(page)
  await enableSemantics(page)
  await click(page, user, false)
}

async function employee(page, user) {
  await page.goto(`http://${host}:${ports.employee}/`, { waitUntil: 'networkidle' })
  await settle(page)
  await enableSemantics(page)
  // React labels each button with the name. Flutter groups the card with its button.
  const button =
    flavor === 'react'
      ? page.getByRole('button', { name: `Open session for ${user}` })
      : page
          .getByRole('group', { name: new RegExp(user) })
          .getByRole('button', { name: 'Open session' })
  await button.first().click()
  await settle(page, 2000)
}

const shots = {
  'trainer-01-login': async (page) => {
    await page.goto(`http://${host}:${ports.trainer}/`, { waitUntil: 'networkidle' })
  },
  'trainer-02-documents': async (page) => trainer(page, 'Kiran Rao'),
  'trainer-03-blueprint': async (page) => {
    await trainer(page, 'Kiran Rao')
    await click(page, 'Blueprint')
  },
  'trainer-04-blueprint-course': async (page) => {
    await trainer(page, 'Kiran Rao')
    await click(page, 'Blueprint')
    await click(page, 'Compliance Essentials')
  },
  'trainer-05-courses': async (page) => {
    await trainer(page, 'Kiran Rao')
    await click(page, 'Courses')
  },
  'trainer-06-course-detail': async (page) => {
    await trainer(page, 'Kiran Rao')
    await click(page, 'Courses')
    await click(page, 'Compliance Essentials')
  },
  'trainer-07-assign': async (page) => {
    await trainer(page, 'Kiran Rao')
    await click(page, 'Assign')
  },
  'trainer-08-performance': async (page) => {
    await trainer(page, 'Kiran Rao')
    await click(page, 'Performance')
    await settle(page, 2500)
  },
  'employee-01-login': async (page) => {
    await page.goto(`http://${host}:${ports.employee}/`, { waitUntil: 'networkidle' })
  },
  'employee-02-dashboard': async (page) => employee(page, 'Priya Nair'),
  'employee-03-my-courses': async (page) => {
    await employee(page, 'Priya Nair')
    await click(page, 'My Courses')
  },
  'employee-04-course': async (page) => {
    await employee(page, 'Priya Nair')
    await click(page, 'My Courses')
    // Flutter: the Continue button in the course card. React: the card title.
    if (flavor === 'flutter') {
      await page
        .getByRole('group', { name: /Communication Skills/ })
        .getByRole('button')
        .click()
      await settle(page, 2000)
    } else await click(page, 'Communication Skills')
  },
  'employee-05-notifications': async (page) => {
    await employee(page, 'Priya Nair')
    await click(page, 'Notifications')
  },
  'employee-06-performance-hod': async (page) => {
    await employee(page, 'Meera Iyer')
    await click(page, 'Performance')
    await settle(page, 2500)
  },
}

mkdirSync(outDir, { recursive: true })
const browser = await chromium.launch()
let failed = 0
for (const [name, run] of Object.entries(shots)) {
  if (only.length && !only.includes(name)) continue
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  page.on('pageerror', (err) => console.error(`${name} pageerror:`, err.message))
  try {
    await run(page)
    await settle(page, 800)
    await page.screenshot({ path: join(outDir, `${name}.png`) })
    console.log('ok', name)
  } catch (error) {
    failed++
    console.error('FAIL', name, error.message.split('\n')[0])
    await page.screenshot({ path: join(outDir, `${name}.FAILED.png`) }).catch(() => {})
  }
  await context.close()
}
await browser.close()
process.exit(failed ? 1 : 0)
