/* GoatCounter v2.7.0: POST /count reads p, q, r and e from the URL query. */
(function () {
  'use strict';
  var label = /^[a-z0-9-]{1,40}$/;
  function send(name) {
    try {
      if (location.hostname !== 'jaromirsvoboda.github.io' ||
          /^\/poster-review(?:\/|$)/.test(location.pathname) ||
          navigator.globalPrivacyControl === true ||
          [navigator.doNotTrack, navigator.msDoNotTrack, window.doNotTrack].some(function (v) {
            return v === '1' || v === 'yes';
          })) return;
      var event = name !== undefined;
      if (event && (typeof name !== 'string' || !label.test(name))) return;
      var path = location.pathname, canonical = document.querySelector('link[rel="canonical"]');
      if (canonical) {
        var url = new URL(canonical.href, location.href);
        if (url.origin === location.origin) path = url.pathname;
      }
      var data = new URLSearchParams({ p: event ? name : path.replace(/\/index\.html$/, '/') });
      if (event) data.set('e', 'true');
      else {
        var refs = new URLSearchParams(location.search).getAll('ref');
        if (refs.length === 1 && label.test(refs[0])) data.set('q', 'ref=' + refs[0]);
        if (document.referrer) {
          var ref = new URL(document.referrer);
          if (/^https?:$/.test(ref.protocol) && ref.origin !== location.origin) data.set('r', ref.origin);
        }
      }
      fetch('https://devvm.tail77ab30.ts.net:8443/count?' + data, {
        method: 'POST', keepalive: true, credentials: 'omit', referrerPolicy: 'no-referrer'
      }).catch(function () {});
    } catch (_) {}
  }
  window.usageCount = function (name) {
    if (typeof name === 'string' && label.test(name)) send(name);
  };
  send();
})();
