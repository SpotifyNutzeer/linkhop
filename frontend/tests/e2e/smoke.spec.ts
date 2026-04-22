import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Deezer needs no API credentials, so this works in CI without secrets.
// Override via E2E_TEST_URL to test against Spotify/Tidal when credentials
// are available.
const TEST_URL = process.env.E2E_TEST_URL ?? 'https://www.deezer.com/track/3135556';

// Diagnostik: Browser-Console und -Fehler in CI loggen.
test.beforeEach(async ({ page }) => {
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[browser:${msg.type()}] ${msg.text()}`);
    }
  });
  page.on('pageerror', (err) => {
    console.log(`[browser:pageerror] ${err.message}`);
  });
  page.on('requestfailed', (req) => {
    console.log(`[browser:requestfailed] ${req.method()} ${req.url()} → ${req.failure()?.errorText}`);
  });
});

test.describe('linkhop smoke', () => {
  test('home renders and theme toggle persists', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('textbox', { name: /streaming-link/i })).toBeVisible();

    const toggle = page.getByRole('button', { name: /theme/i });
    await toggle.click();
    const themeAfterClick = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );
    await page.reload();
    const themeAfterReload = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );
    expect(themeAfterReload).toBe(themeAfterClick);
  });

  test('happy-path convert shows result', async ({ page }) => {
    // Netzwerk-Requests loggen um Proxy-Verhalten zu verifizieren.
    page.on('response', (res) => {
      if (res.url().includes('/api/')) {
        console.log(`[network] ${res.status()} ${res.url()}`);
      }
    });

    await page.goto(`/?url=${encodeURIComponent(TEST_URL)}`);

    // Kurz warten und dann DOM-Zustand erfassen falls Element nicht da.
    try {
      await expect(page.locator('a.link[target="_blank"]').first()).toBeVisible({
        timeout: 30_000
      });
    } catch (e) {
      // DOM-Snapshot für Diagnostik
      const html = await page.content();
      console.log('[diag:url]', page.url());
      console.log('[diag:html-length]', html.length);
      // Nur relevante Teile loggen
      const main = await page.locator('main').innerHTML().catch(() => 'MAIN_NOT_FOUND');
      console.log('[diag:main]', main.slice(0, 2000));
      throw e;
    }
  });

  test('invalid url shows ErrorPanel with copy-debug', async ({ page }) => {
    page.on('response', (res) => {
      if (res.url().includes('/api/')) {
        console.log(`[network] ${res.status()} ${res.url()}`);
      }
    });

    await page.goto('/?url=https://not-a-music-service.example/xyz');

    try {
      await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 });
    } catch (e) {
      const main = await page.locator('main').innerHTML().catch(() => 'MAIN_NOT_FOUND');
      console.log('[diag:url]', page.url());
      console.log('[diag:main]', main.slice(0, 2000));
      throw e;
    }
    await expect(page.getByRole('button', { name: /debug.*kopieren/i })).toBeVisible();
  });

  test('history persists across reload', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.goto(`/?url=${encodeURIComponent(TEST_URL)}`);
    await expect(page.locator('a.link[target="_blank"]').first()).toBeVisible({
      timeout: 30_000
    });

    await page.goto('/');
    await page.getByRole('textbox', { name: /streaming-link/i }).focus();
    await expect(page.getByRole('listbox', { name: /verlauf/i })).toBeVisible();
  });

  test('share-button creates short-link that loads', async ({ page }) => {
    await page.goto(`/?url=${encodeURIComponent(TEST_URL)}`);
    await expect(page.locator('a.link[target="_blank"]').first()).toBeVisible({
      timeout: 30_000
    });

    await page.getByRole('button', { name: /teilen/i }).click();
    const shortCode = page.locator('code').first();
    await expect(shortCode).toBeVisible({ timeout: 15_000 });
    const shortUrl = (await shortCode.textContent())!;
    const shortPath = new URL(shortUrl).pathname;

    await page.goto(shortPath);
    await expect(page.locator('a.link[target="_blank"]').first()).toBeVisible({
      timeout: 15_000
    });
  });

  test('a11y: no critical/serious violations on home', async ({ page }) => {
    await page.goto('/');
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious'
    );
    expect(blocking, JSON.stringify(blocking, null, 2)).toHaveLength(0);
  });
});
