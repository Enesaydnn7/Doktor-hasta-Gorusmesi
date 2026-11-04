(() => {
  // COMED freezes the global Window object.  Adding ad-hoc properties to it
  // therefore throws before the tracer can install.  Keep the idempotency
  // marker on the DOM and all trace state inside this closure instead.
  const TRACE_MARKER = "data-klinot-comed-trace-installed";
  const markerHost = document.documentElement || document;
  if (markerHost.getAttribute?.(TRACE_MARKER) === "1") return;
  markerHost.setAttribute?.(TRACE_MARKER, "1");

  const TRACE_SOURCE = "klinot-comed-trace-v1";
  const SUPPRESS_RELOAD_PROMPT_KEY = "klinot-comed-suppress-reload-prompt-once";
  const API_HOST = "goztepetestapi.comed.mlpcare.com";
  const SECRET_KEY = /authorization|cookie|password|passwd|secret|token|session/i;
  const MAX_TEXT = 300000;
  const sessionHeaders = new Map();
  const traceEvents = [];

  // Klinot'un KENDİ başlattığı tek sayfa geçişinde COMED'in "kaydedilmemiş
  // değişiklik" uyarısını bastır. İki yerde kullanılır: taslak temizlemeden
  // sonraki yenileme ve "COMED'e aktar" sırasında hasta kartının açılması.
  // Dinleyici document_start'ta, uygulama dinleyicilerinden önce kurulur ve
  // yalnızca sessionStorage bayrağının bulunduğu bir sonraki çıkışta çalışır.
  const SUPPRESS_TTL_MS = 15000;
  window.addEventListener("beforeunload", (event) => {
    const flag = sessionStorage.getItem(SUPPRESS_RELOAD_PROMPT_KEY);
    if (!flag) return;
    sessionStorage.removeItem(SUPPRESS_RELOAD_PROMPT_KEY);
    // Bayrak zaman damgası taşır ("1" eski sürümlerle uyum için kabul edilir).
    // Geçiş bir şekilde olmadıysa bayrak asılı kalır; eskimiş bir bayrak
    // doktorun GERÇEK çıkışını sessizce yutmamalı.
    const stamp = Number(flag);
    if (Number.isFinite(stamp) && stamp > 1 && Date.now() - stamp > SUPPRESS_TTL_MS) {
      return;
    }
    event.stopImmediatePropagation();
  }, {capture: true});

  function clip(value) {
    const text = String(value ?? "");
    return text.length > MAX_TEXT ? `${text.slice(0, MAX_TEXT)}…[truncated]` : text;
  }

  function redact(value, depth = 0) {
    if (depth >= 12) return "[MAX_DEPTH]";
    if (Array.isArray(value)) return value.slice(0, 1000).map((item) => redact(item, depth + 1));
    if (value && typeof value === "object") {
      const safe = {};
      Object.entries(value).slice(0, 500).forEach(([key, item]) => {
        safe[key] = SECRET_KEY.test(key) ? "[REDACTED]" : redact(item, depth + 1);
      });
      return safe;
    }
    return typeof value === "string" ? clip(value) : value;
  }

  function parseText(value) {
    if (value === null || value === undefined || value === "") return null;
    const text = clip(value);
    try {
      return redact(JSON.parse(text));
    } catch (_) {
      return text;
    }
  }

  function bodyValue(body) {
    if (body === null || body === undefined) return null;
    if (typeof body === "string") return parseText(body);
    if (body instanceof URLSearchParams) return redact(Object.fromEntries(body.entries()));
    if (body instanceof FormData) {
      const values = {};
      for (const [key, value] of body.entries()) {
        values[key] = typeof value === "string" ? value : `[binary:${value.type || "file"}]`;
      }
      return redact(values);
    }
    if (body instanceof Blob) return `[binary:${body.type || "blob"};${body.size}]`;
    if (body instanceof ArrayBuffer || ArrayBuffer.isView(body)) return "[binary]";
    return parseText(body);
  }

  function safeUrl(value) {
    try {
      const url = new URL(value, location.href);
      for (const key of [...url.searchParams.keys()]) {
        if (SECRET_KEY.test(key)) url.searchParams.delete(key);
      }
      url.hash = "";
      return url.href;
    } catch (_) {
      return "";
    }
  }

  function isApiUrl(value) {
    try {
      return new URL(value, location.href).hostname === API_HOST;
    } catch (_) {
      return false;
    }
  }

  function captureSessionHeader(name, value) {
    const key = String(name || "").trim().toLowerCase();
    if (!["x-application-key", "x-authentication-token", "accept-language"].includes(key)) return;
    const text = String(value || "").trim();
    if (text) sessionHeaders.set(key, text);
  }

  function captureSessionHeaders(headers) {
    try {
      new Headers(headers || {}).forEach((value, name) => captureSessionHeader(name, value));
    } catch (_) {
      // A malformed third-party header bag must not affect COMED.
    }
  }


  function emit(event) {
    const url = safeUrl(event.url);
    try {
      if (!url || new URL(url).hostname !== API_HOST) return;
      const safeEvent = {
        method: String(event.method || "GET").toUpperCase(),
        url,
        status: Number.isFinite(Number(event.status)) ? Number(event.status) : null,
        duration_ms: Number.isFinite(Number(event.duration_ms)) ? Number(event.duration_ms) : null,
        request_body: redact(event.request_body),
        response_body: redact(event.response_body),
        captured_at: new Date().toISOString(),
      };
      // COMED zaten bu istek ve cevap verilerini sayfa belleğinde işler. Son
      // şekilleri yalnız test/doğrulama amacıyla aynı sayfa belleğinde tutmak,
      // oturum başlıklarını DOM'a veya Klinot sunucusuna taşımadan doğrulamayı
      // mümkün kılar.
      traceEvents.push(safeEvent);
      if (traceEvents.length > 250) traceEvents.splice(0, traceEvents.length - 250);
      window.postMessage({
        source: TRACE_SOURCE,
        event: safeEvent,
      }, location.origin);
    } catch (_) {
      // Tracing must never alter COMED behavior.
    }
  }

  const xhrMeta = new WeakMap();
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    xhrMeta.set(this, {
      method: String(method || "GET").toUpperCase(),
      url: safeUrl(url),
      started_at: performance.now(),
      request_body: null,
    });
    this.addEventListener("loadend", () => {
      const meta = xhrMeta.get(this);
      if (!meta) return;
      let responseBody = null;
      try {
        responseBody = this.responseType === "json" ? this.response : parseText(this.responseText);
      } catch (_) {
        responseBody = null;
      }
      emit({
        ...meta,
        url: this.responseURL || meta.url,
        status: this.status,
        duration_ms: Math.round(performance.now() - meta.started_at),
        response_body: responseBody,
      });
      xhrMeta.delete(this);
    }, {once: true});
    return originalOpen.call(this, method, url, ...rest);
  };

  XMLHttpRequest.prototype.send = function(body) {
    const meta = xhrMeta.get(this);
    if (meta) meta.request_body = bodyValue(body);
    return originalSend.call(this, body);
  };

  XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
    const meta = xhrMeta.get(this);
    if (meta && isApiUrl(meta.url)) captureSessionHeader(name, value);
    return originalSetRequestHeader.call(this, name, value);
  };

  if (typeof window.fetch === "function") {
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function(input, init = {}) {
      const method = String(init.method || input?.method || "GET").toUpperCase();
      const url = typeof input === "string" || input instanceof URL ? input : input?.url;
      const startedAt = performance.now();
      if (isApiUrl(url)) {
        captureSessionHeaders(input instanceof Request ? input.headers : null);
        captureSessionHeaders(init.headers);
      }
      let requestBody = bodyValue(init.body);
      if (requestBody === null && input instanceof Request && !["GET", "HEAD"].includes(method)) {
        try {
          requestBody = parseText(await input.clone().text());
        } catch (_) {
          requestBody = null;
        }
      }
      const response = await originalFetch(input, init);
      let responseBody = null;
      try {
        responseBody = parseText(await response.clone().text());
      } catch (_) {
        responseBody = null;
      }
      emit({
        method,
        url: response.url || url,
        status: response.status,
        duration_ms: Math.round(performance.now() - startedAt),
        request_body: requestBody,
        response_body: responseBody,
      });
      return response;
    };
  }

})();
