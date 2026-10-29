import { test, expect } from '@playwright/test';
import axe from 'axe-core';

const home = '/pyxel/user-examples/';
const iconStandIn = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=',
  'base64',
);
const fontStandIn =
  "@font-face { font-family: 'Noto Sans JP'; src: url(https://fonts.gstatic.com/s/stand-in.woff2) format('woff2'); }";

// Fonts and badges load from the network and the Pyxel site provides the icon; stand-ins keep
// the tests independent of those services, and the text falls back to local fonts.
async function stubExternal(context) {
  // The stand-in stylesheet points at fonts.gstatic.com like the real one, so font-src is covered.
  await context.route(/^https:\/\/fonts\.googleapis\.com\//, (route) =>
    route.fulfill({ contentType: 'text/css', body: fontStandIn }),
  );
  await context.route(/^https:\/\/fonts\.gstatic\.com\//, (route) =>
    route.fulfill({ contentType: 'font/woff2', body: '' }),
  );
  await context.route('**/pyxel/assets/images/pyxel_icon_64x64.png', (route) =>
    route.fulfill({ contentType: 'image/png', body: iconStandIn }),
  );
  await context.route(/^https:\/\/(img\.shields\.io|ko-fi\.com)\//, (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="149" height="20"><rect width="149" height="20" fill="white"/></svg>',
    }),
  );
}

test.beforeEach(async ({ context }) => {
  await stubExternal(context);
});

// Collects script errors and HTTP error responses.
function watch(page) {
  const problems = [];
  page.on('pageerror', (error) => problems.push(error.message));
  page.on('response', (response) => {
    if (response.status() >= 400) problems.push(`${response.status()} ${response.url()}`);
  });
  return problems;
}

async function expectAccessible(page) {
  await page.evaluate(axe.source);
  const result = await page.evaluate(() =>
    window.axe.run(document, {
      runOnly: {
        type: 'tag',
        values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa', 'best-practice'],
      },
      // The top and bottom page navigations share their label by design.
      rules: { 'landmark-unique': { enabled: false } },
    }),
  );
  expect(
    result.violations.map(({ id, nodes }) => ({ id, elements: nodes.map((node) => node.target) })),
  ).toEqual([]);
}

function isOpen(page) {
  return page.locator('.lightbox').evaluate((dialog) => dialog.open);
}

function rootOverflow(page) {
  return page.evaluate(() => getComputedStyle(document.documentElement).overflow);
}

async function expectPreviewToFit(page, index) {
  const { width, height } = page.viewportSize();
  const preview = page.locator('.preview img').nth(index);
  const ratio =
    Number(await preview.getAttribute('width')) / Number(await preview.getAttribute('height'));
  // styles.css: 85% of the viewport less the frame of 3vmin on each side
  const frame = 0.06 * Math.min(width, height);
  const expected = Math.min(0.85 * width - frame, (0.85 * height - frame) * ratio);
  const image = await page.locator('.lightbox img').boundingBox();
  expect(Math.abs(image.width - expected)).toBeLessThan(1);
  expect(Math.abs(image.height - expected / ratio)).toBeLessThan(1);
  // The frame holds the whole image, and the viewport the whole frame.
  const dialog = await page.locator('.lightbox').boundingBox();
  for (const [inner, outer] of [
    [image, dialog],
    [dialog, { x: 0, y: 0, width, height }],
  ]) {
    expect(inner.x).toBeGreaterThanOrEqual(outer.x);
    expect(inner.y).toBeGreaterThanOrEqual(outer.y);
    expect(inner.x + inner.width).toBeLessThanOrEqual(outer.x + outer.width);
    expect(inner.y + inner.height).toBeLessThanOrEqual(outer.y + outer.height);
  }
}

for (const width of [320, 375, 768, 1280])
  test(`${width}px: cards, previews, and accessibility`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 });
    const problems = watch(page);
    await page.goto(home);
    const layout = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > innerWidth,
      cards: [...document.querySelectorAll('.card')].map((card) => {
        const preview = card.querySelector('.preview img').getBoundingClientRect();
        const heading = card.querySelector('h2').getBoundingClientRect();
        return {
          top: card.getBoundingClientRect().top,
          previewFirst: preview.bottom <= heading.top,
          square: Math.abs(preview.width - preview.height) < 1,
        };
      }),
    }));
    expect(layout.overflow).toBe(false);
    expect(layout.cards).toHaveLength(18);
    expect(layout.cards.every((card) => card.previewFirst && card.square)).toBe(true);
    const columns = layout.cards.filter((card) => card.top === layout.cards[0].top).length;
    expect(columns).toBe(width < 768 ? 1 : width < 960 ? 2 : 3);
    await expectAccessible(page);
    await page.locator('.preview').first().click();
    expect(await isOpen(page)).toBe(true);
    await expectAccessible(page);
    expect(problems).toEqual([]);
  });

test('numbered pages link to each other, label their ranges, and display every preview', async ({
  page,
}) => {
  await page.goto(home);
  const pages = await page
    .locator('nav:not(.bottom-nav) > :not(.nav-arrow)')
    .evaluateAll((items) => items.map((item) => ({ label: item.textContent, href: item.href })));
  for (const [index, { label, href }] of pages.entries()) {
    const path = index === 0 ? home : `${home}page/${index + 1}/`;
    if (href) expect(new URL(href).pathname).toBe(path);
    expect((await page.goto(path)).status()).toBe(200);
    expect(await page.locator('meta[property="og:url"]').getAttribute('content')).toBe(
      `https://kitao.dev${path}`,
    );
    await expect(page.locator('[aria-current="page"]').first()).toHaveText(label);
    const ids = await page
      .locator('.card h2')
      .evaluateAll((headings) =>
        headings.map((heading) => Number(heading.textContent.match(/^#(\d+) /)[1])),
      );
    expect(ids.length).toBeGreaterThan(0);
    expect(ids.length).toBeLessThanOrEqual(18);
    expect(label).toBe(`${ids[0]}-${ids.at(-1)}`);
    await expect(page.locator('a[rel="prev"]')).toHaveCount(index === 0 ? 0 : 2);
    await expect(page.locator('a[rel="next"]')).toHaveCount(index === pages.length - 1 ? 0 : 2);

    const failedPreviews = await page.locator('.preview img').evaluateAll(async (images) => {
      // Include offscreen lazy images, not just those in the initial viewport.
      const results = await Promise.all(
        images.map(async (image) => {
          image.loading = 'eager';
          try {
            await image.decode();
            return null;
          } catch {
            return new URL(image.src).pathname;
          }
        }),
      );
      return results.filter((path) => path !== null);
    });
    expect(failedPreviews, path).toEqual([]);
  }
});

test('a preview opens enlarged and closes with Escape, the image, or the backdrop', async ({
  page,
  hasTouch,
}) => {
  await page.goto(home);
  for (const [index, close] of [
    [0, 'Escape'],
    [1, 'image'],
    [2, 'backdrop'],
  ]) {
    const preview = page.locator('.preview').nth(index);
    await (hasTouch ? preview.tap() : preview.click());
    expect(await isOpen(page)).toBe(true);
    await expect(page.locator('.lightbox')).toHaveAttribute(
      'aria-label',
      await preview.locator('img').getAttribute('alt'),
    );
    await expect(page.locator('.lightbox img')).toHaveAttribute(
      'src',
      await preview.evaluate((link) => link.href),
    );
    await expectPreviewToFit(page, index);
    expect(await rootOverflow(page)).toBe('hidden');
    if (close === 'Escape') await page.keyboard.press('Escape');
    else if (close === 'image') await page.locator('.lightbox img').click();
    else if (hasTouch) await page.touchscreen.tap(2, 2);
    else await page.mouse.click(2, 2);
    expect(await isOpen(page)).toBe(false);
    expect(await rootOverflow(page)).toBe('visible');
  }
});

test('the page does not scroll behind an open preview', async ({ page, isMobile }) => {
  test.skip(isMobile, 'Phones have no mouse wheel');
  await page.goto(home);
  await page.locator('.preview').first().click();
  await expect.poll(() => rootOverflow(page)).toBe('hidden');
  // WebKit scrolls on another thread, which takes the new overflow at the next frames.
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(100);
  expect(await page.evaluate(() => scrollY)).toBe(0);
});

test('keyboard users open and close a preview, and focus returns', async ({ page, isMobile }) => {
  test.skip(isMobile, 'Phones have no keyboard');
  await page.goto(home);
  const link = page.locator('.preview').first();
  await link.focus();
  await page.keyboard.press('Enter');
  expect(await isOpen(page)).toBe(true);
  await expect(page.locator('.lightbox button')).toBeFocused();
  await expect(page.locator('.lightbox button')).toHaveAccessibleName('Close preview');
  await page.keyboard.press('Enter');
  expect(await isOpen(page)).toBe(false);
  await expect(link).toBeFocused();
});

test('keyboard focus is visible', async ({ page }) => {
  await page.goto(home);
  const outlines = () =>
    page.evaluate(() =>
      ['.meta a', 'nav a', '.preview'].map((selector) => {
        const element = document.querySelector(selector);
        element.focus();
        if (!element.matches(':focus-visible')) return 'none';
        const style = getComputedStyle(element, selector === 'nav a' ? '::after' : null);
        return style.outlineStyle === 'solid' ? style.outlineWidth : 'none';
      }),
    );
  // A key press makes the following script focus visible, as keyboard focus is.
  await page.keyboard.press('Shift');
  expect(await outlines()).toEqual(['1px', '1px', '1px']);
});

test('other clicks on a preview are left to the browser', async ({ page }) => {
  await page.goto(home);
  const click = (init) =>
    page.evaluate((init) => {
      let prevented = null;
      document.addEventListener(
        'click',
        (event) => {
          prevented = event.defaultPrevented;
          // Stays on the page instead of opening the GIF.
          event.preventDefault();
        },
        { once: true },
      );
      const event = new MouseEvent('click', { bubbles: true, cancelable: true, ...init });
      document.querySelector('.preview').dispatchEvent(event);
      return [prevented, document.querySelector('.lightbox').open];
    }, init);
  for (const init of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }])
    expect(await click(init), JSON.stringify(init)).toEqual([false, false]);
  expect(await click({})).toEqual([true, true]);
});

test('an open preview follows the viewport', async ({ page }) => {
  await page.goto(home);
  await page.locator('.preview').nth(1).click();
  // Small enough that the default maximum size of a dialog would clip it
  await page.setViewportSize({ width: 200, height: 240 });
  await expectPreviewToFit(page, 1);
});

test('a preview opens before the stylesheet and the image arrive', async ({
  page,
  browserName,
}) => {
  test.skip(browserName !== 'webkit', 'Only WebKit runs deferred scripts before a slow stylesheet');
  const late = async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  };
  await page.route('**/styles.css', late);
  await page.route('**/*.gif', late);
  await page.goto(home, { waitUntil: 'domcontentloaded' });
  const background = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(await background()).toBe('rgba(0, 0, 0, 0)');
  const preview = page.locator('.preview img').first();
  expect(await preview.evaluate((image) => image.complete)).toBe(false);
  // Click at once; click() would wait until the page settles.
  await preview.dispatchEvent('click');
  expect(await isOpen(page)).toBe(true);
  expect(await preview.evaluate((image) => image.complete)).toBe(false);
  await page.waitForLoadState('load');
  expect(await background()).not.toBe('rgba(0, 0, 0, 0)');
  await expectPreviewToFit(page, 0);
});

test('security headers apply and the gallery runs without CSP violations', async ({ page }) => {
  await page.addInitScript(() => {
    window.violations = [];
    document.addEventListener('securitypolicyviolation', (event) =>
      window.violations.push(`${event.violatedDirective} ${event.blockedURI}`),
    );
  });
  for (const path of [home]) {
    const headers = (await page.goto(path)).headers();
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['referrer-policy']).toBe('strict-origin-when-cross-origin');
    const policy = Object.fromEntries(
      headers['content-security-policy'].split(';').map((directive) => {
        const [name, ...values] = directive.trim().split(/\s+/);
        return [name, values];
      }),
    );
    expect(policy['default-src']).toEqual(["'none'"]);
    // Local runs neither inject the analytics script nor frame the page, so check these by value.
    expect(policy['script-src']).toContain('https://static.cloudflareinsights.com');
    expect(policy['connect-src']).toContain('https://cloudflareinsights.com');
    for (const name of ['base-uri', 'form-action', 'frame-ancestors'])
      expect(policy[name], name).toEqual(["'none'"]);
    expect(await page.evaluate(() => window.violations)).toEqual([]);
  }
  await page.evaluate(() => document.fonts.ready);
  await expect
    .poll(() =>
      page
        .locator('.preview img')
        .first()
        .evaluate((image) => image.naturalWidth),
    )
    .toBeGreaterThan(0);
  await page.locator('.preview').first().click();
  expect(await isOpen(page)).toBe(true);
  expect(await page.evaluate(() => window.violations)).toEqual([]);
  // A redirect to the trailing slash carries the headers too.
  const redirect = await page.request.get('/pyxel/user-examples', { maxRedirects: 0 });
  expect(redirect.status()).toBe(307);
  expect(redirect.headers()['content-security-policy']).toContain("default-src 'none'");
  // The browser's own viewer for an image opened on its own needs inline styles.
  const image = (await page.request.get(`${home}images/1.gif`)).headers();
  expect(image['x-content-type-options']).toBe('nosniff');
  expect(image['content-security-policy']).toBeUndefined();
});
