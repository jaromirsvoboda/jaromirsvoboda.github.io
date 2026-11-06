const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('site/usage-counts.js', 'utf8');
let checks = 0;
function browser(options = {}) {
  const requests = [];
  const location = new URL(options.url || 'https://jaromirsvoboda.github.io/library/test/index.html?email=private#answer');
  const navigator = options.navigator || {};
  const window = { doNotTrack: options.dnt };
  const fetch = (url, config) => {
    requests.push({ url: new URL(url), config });
    if (options.throw) throw Error('offline');
    return options.reject ? Promise.reject(Error('offline')) : Promise.resolve();
  };
  vm.runInNewContext(source, { location, navigator, window,
    document: { referrer: options.referrer || '', querySelector: () => options.canonical ? { href: options.canonical } : null },
    fetch: options.noFetch ? undefined : fetch, URL, URLSearchParams });
  return { requests, window, navigator };
}
function check(name, run) { run(); checks++; }

check('default page, canonical path, no private query or fragment', () => {
  const { requests } = browser();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url.searchParams.get('p'), '/library/test/');
  assert.equal(requests[0].url.searchParams.size, 1);
  assert.equal(requests[0].url.hash, '');
  assert.equal(requests[0].url.pathname, '/count');
  assert.equal(requests[0].config.method, 'POST');
  assert.equal(requests[0].config.keepalive, true);
  assert.equal(requests[0].config.credentials, 'omit');
  assert.equal(requests[0].config.referrerPolicy, 'no-referrer');
  assert.equal(requests[0].config.body, undefined);
});
check('canonical link on this origin', () => {
  assert.equal(browser({ canonical: '/library/moved/?drop=yes#drop' }).requests[0].url.searchParams.get('p'), '/library/moved/');
  assert.equal(browser({ canonical: 'https://example.org/private/' }).requests[0].url.searchParams.get('p'), '/library/test/');
});
check('one valid referral label, other parameters stripped', () => {
  const p = browser({ url: 'https://jaromirsvoboda.github.io/?ref=post-123&email=private' }).requests[0].url.searchParams;
  assert.equal(p.get('q'), 'ref=post-123');
  assert.equal(p.get('p'), '/');
  assert.equal(p.size, 2);
});
check('invalid and repeated referral labels discarded', () => {
  for (const q of ['ref=', 'ref=UPPER', 'ref=a&ref=b', 'ref=person%40example.org', 'ref=' + 'a'.repeat(41), 'ref=a_b']) {
    assert.equal(browser({ url: 'https://jaromirsvoboda.github.io/?' + q }).requests[0].url.searchParams.get('q'), null);
  }
});
check('external referrer reduced to origin', () => {
  const p = browser({ referrer: 'https://example.org/private?secret=value#private' }).requests[0].url.searchParams;
  assert.equal(p.get('r'), 'https://example.org');
});
check('internal referrer omitted', () => {
  assert.equal(browser({ referrer: 'https://jaromirsvoboda.github.io/quiz/?private' }).requests[0].url.searchParams.get('r'), null);
});
check('four quiz events contain only name and event flag', () => {
  const b = browser();
  for (const name of ['quiz-start-en', 'quiz-finish-en', 'quiz-start-cs', 'quiz-finish-cs']) b.window.usageCount(name);
  assert.equal(b.requests.length, 5);
  for (const r of b.requests.slice(1)) {
    assert.match(r.url.searchParams.get('p'), /^quiz-(start|finish)-(en|cs)$/);
    assert.equal(r.url.searchParams.get('e'), 'true');
    assert.equal(r.url.searchParams.size, 2);
  }
});
check('invalid events never cause a page or event request', () => {
  const b = browser();
  for (const value of [undefined, null, {}, '', 'UPPER', 'answer 1', 'a'.repeat(41), 'a/b']) b.window.usageCount(value);
  assert.equal(b.requests.length, 1);
});
check('DNT and GPC suppress page and event requests', () => {
  for (const options of [{ navigator: { doNotTrack: '1' } }, { navigator: { msDoNotTrack: '1' } }, { dnt: '1' }, { navigator: { doNotTrack: 'yes' } }, { navigator: { globalPrivacyControl: true } }]) {
    const b = browser(options); b.window.usageCount('quiz-start-en');
    assert.equal(b.requests.length, 0);
  }
});
check('privacy signal rechecked for later events', () => {
  const b = browser(); b.navigator.globalPrivacyControl = true; b.window.usageCount('quiz-start-en');
  assert.equal(b.requests.length, 1);
});
check('poster review and local previews excluded', () => {
  for (const url of ['https://jaromirsvoboda.github.io/poster-review', 'https://jaromirsvoboda.github.io/poster-review/index.html', 'http://localhost:8000/']) {
    const b = browser({ url }); b.window.usageCount('quiz-start-en'); assert.equal(b.requests.length, 0);
  }
});
check('offline and unavailable fetch never throw or retry', () => {
  for (const options of [{ throw: true }, { noFetch: true }, { reject: true }]) {
    const b = browser(options); assert.doesNotThrow(() => b.window.usageCount('quiz-finish-cs'));
    assert.equal(b.requests.length, options.noFetch ? 0 : 2);
  }
});
setImmediate(() => console.log(`usage-counts: ${checks} contract checks passed`));
