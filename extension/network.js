(() => {
  'use strict';
  const core = globalThis.GoldCore;
  let enabled = false, generation = 0;
  window.addEventListener('message', e => {
    if (e.source === window && e.origin === location.origin && e.data?.channel === 'gold-control-v1') {
      enabled = e.data.enabled === true; generation++;
    }
  });
  function eligible(url) {
    const source = core.operationSource(url);
    return enabled && source && source === core.sourceFromPath(location.pathname) ? source : null;
  }
  function publish(data, source, epoch) {
    if (!enabled || epoch !== generation || core.sourceFromPath(location.pathname) !== source) return;
    // Strip the response down to post fields before crossing into extension code. No headers/cookies/tokens.
    const posts = core.extractTimeline(data, source, 'pending');
    if (posts.length) window.postMessage({channel:'gold-posts-v1', source, posts:posts.slice(0,200)}, location.origin);
  }
  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || String(args[0]);
    const source = eligible(url), epoch = generation;
    const response = await Reflect.apply(originalFetch, this, args);
    if (source && response.ok) response.clone().json().then(data => publish(data, source, epoch)).catch(() => {});
    return response;
  };
  const originalOpen = XMLHttpRequest.prototype.open, originalSend = XMLHttpRequest.prototype.send;
  const requestUrls = new WeakMap();
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    requestUrls.set(this, String(url)); return Reflect.apply(originalOpen, this, [method, url, ...rest]);
  };
  XMLHttpRequest.prototype.send = function (...args) {
    const source = eligible(requestUrls.get(this)), epoch = generation;
    if (source) this.addEventListener('load', () => {
      if (this.status < 200 || this.status >= 300) return;
      try { publish(this.responseType === 'json' ? this.response : JSON.parse(this.responseText), source, epoch); } catch {}
    }, {once:true});
    return Reflect.apply(originalSend, this, args);
  };
})();
