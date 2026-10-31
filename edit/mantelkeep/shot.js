const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 2.4 });
  await p.goto('https://www.mantelkeep.com/', { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: 'mk_hero.png' });
  await p.screenshot({ path: 'mk_full.png', fullPage: true });
  console.log(await p.title());
  await b.close();
})();
