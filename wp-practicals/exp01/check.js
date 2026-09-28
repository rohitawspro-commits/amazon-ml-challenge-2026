// Checks every page for the semantic rules of the practical, using Playwright's Chromium.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');
const fs = require('fs');
const pages = ['index.html', 'getting-started.html', 'endpoints.html', 'faq.html'];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  let failures = 0;
  for (const file of pages) {
    await page.goto('file://' + path.join(__dirname, file));
    const r = await page.evaluate(() => {
      const q = s => document.querySelectorAll(s).length;
      const levels = [...document.querySelectorAll('h1,h2,h3,h4')].map(h => Number(h.tagName[1]));
      const internal = [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))
        .filter(h => !/^(https?:|mailto:)/.test(h));
      return {
        lang: document.documentElement.lang, title: document.title,
        description: !!document.querySelector('meta[name=description]'),
        h1: q('h1'), skipped: levels.some((l, i) => i && l - levels[i - 1] > 1),
        landmarks: ['header', 'nav', 'main', 'footer'].filter(t => q(t) > 0).length,
        current: document.querySelector('.side [aria-current="page"]')?.textContent,
        unlabeledSections: [...document.querySelectorAll('section')].filter(s => !s.getAttribute('aria-labelledby')).length,
        thWithoutScope: q('th:not([scope])'), internal
      };
    });
    // every internal link must point to an existing file and, if it has #id, to an existing id there
    r.links = r.internal.length;
    r.broken = r.internal.filter(h => {
      const [target, id] = h.split('#');
      const html = fs.existsSync(path.join(__dirname, target || file)) && fs.readFileSync(path.join(__dirname, target || file), 'utf8');
      return !html || (id && !html.includes(`id="${id}"`));
    });
    const ok = r.lang === 'en' && r.description && r.h1 === 1 && !r.skipped && r.landmarks === 4 && r.current
      && r.unlabeledSections === 0 && r.thWithoutScope === 0 && r.broken.length === 0;
    failures += !ok;
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${file.padEnd(21)} title="${r.title}"  h1=${r.h1}  landmarks=${r.landmarks}/4  ` +
      `current="${r.current}"  headings-skipped=${r.skipped}  links=${r.links} broken=${r.broken.length}`);
  }
  console.log(failures ? `${failures} page(s) failed` : 'All 4 pages passed the semantic checks');
  await browser.close();
})();
