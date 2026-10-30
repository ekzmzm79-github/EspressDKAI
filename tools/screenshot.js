// 화면 확인용 스크린샷. Playwright(Node)가 있는 환경에서:
//   python scripts/build.py --data-dir tests/fixtures/sample/data --out /tmp/site --today 2026-10-30
//   node tools/screenshot.js /tmp/site /tmp/shots 2026-10-30
// 휴대폰(390px) 라이트·다크, PC(1280px) 라이트를 찍고, JS 오류와 가로 스크롤을 보고한다.
const { chromium } = require('playwright');
const [site, out, today] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch();
  const errors = [];
  for (const [name, width, scheme] of [['mobile-light', 390, 'light'], ['mobile-dark', 390, 'dark'], ['desktop-light', 1280, 'light']]) {
    const page = await browser.newPage({ viewport: { width, height: 800 }, colorScheme: scheme });
    page.on('pageerror', (e) => errors.push(`${name}: ${e.message}`));
    await page.goto(`file://${site}/index.html?today=${today}`);
    await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
    const summary = await page.$$eval('.card', (cs) => cs.map((c) => `${c.dataset.section} open=${c.querySelector('details').open} ${c.querySelector('.badge')?.textContent ?? '-'} | ${c.querySelector('h3').textContent}`));
    if (name === 'mobile-light') console.log(summary.join('\n'));
    const sw = await page.evaluate(() => document.documentElement.scrollWidth);
    if (sw > width) errors.push(`${name}: 가로 스크롤 ${sw}px`);
    await page.close();
  }
  await browser.close();
  console.log(errors.length ? errors.join('\n') : 'JS 오류·가로 스크롤 없음');
})();
