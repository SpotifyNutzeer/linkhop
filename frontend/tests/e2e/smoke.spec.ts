import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Override in CI when Tidal's public endpoint is flaky or blocked.
const TEST_URL = process.env.E2E_TEST_URL ?? 'https://tidal.com/track/1566';

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
    await page.goto(`/?url=${encodeURIComponent(TEST_URL)}`);
    await expect(page.getByRole('link', { name: /öffnen/i }).first()).toBeVisible({
      timeout: 30_000
    });
  });

  test('invalid url shows ErrorPanel with copy-debug', async ({ page }) => {
    await page.goto('/?url=https://not-a-music-service.example/xyz');
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('button', { name: /debug.*kopieren/i })).toBeVisible();
  });

  test('history persists across reload', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.goto(`/?url=${encodeURIComponent(TEST_URL)}`);
    await expect(page.getByRole('link', { name: /öffnen/i }).first()).toBeVisible({
      timeout: 30_000
    });

    await page.goto('/');
    await page.getByRole('textbox', { name: /streaming-link/i }).focus();
    await expect(page.getByRole('listbox', { name: /verlauf/i })).toBeVisible();
  });

  test('share-button creates short-link that loads', async ({ page }) => {
    await page.goto(`/?url=${encodeURIComponent(TEST_URL)}`);
    await expect(page.getByRole('link', { name: /öffnen/i }).first()).toBeVisible({
      timeout: 30_000
    });

    await page.getByRole('button', { name: /teilen/i }).click();
    const shortCode = page.locator('code').first();
    await expect(shortCode).toBeVisible({ timeout: 15_000 });
    const shortUrl = (await shortCode.textContent())!;
    const shortPath = new URL(shortUrl).pathname;

    await page.goto(shortPath);
    await expect(page.getByRole('link', { name: /öffnen/i }).first()).toBeVisible({
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
