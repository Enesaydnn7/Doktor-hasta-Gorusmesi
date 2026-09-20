(() => {
  if (window.__klinotComedTraceInstalled) return;
  window.__klinotComedTraceInstalled = true;

  const TRACE_SOURCE = "klinot-comed-trace-v1";
  const API_HOST = "goztepe.comedtestapi.mlpcare.com";
  const SECRET_KEY = /authorization|cookie|password|passwd|secret|token|session/i;
  const MAX_TEXT = 300000;

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

  function emit(event) {
    const url = safeUrl(event.url);
    try {
      if (!url || new URL(url).hostname !== API_HOST) return;
      window.postMessage({
        source: TRACE_SOURCE,
        event: {
          method: String(event.method || "GET").toUpperCase(),
          url,
          status: Number.isFinite(Number(event.status)) ? Number(event.status) : null,
          duration_ms: Number.isFinite(Number(event.duration_ms)) ? Number(event.duration_ms) : null,
          request_body: redact(event.request_body),
          response_body: redact(event.response_body),
          captured_at: new Date().toISOString(),
        },
      }, location.origin);
    } catch (_) {
      // Tracing must never alter COMED behavior.
    }
  }

  const xhrMeta = new WeakMap();
  const originalOpen = XMLHttpRequest.prototype.open;
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

  if (typeof window.fetch === "function") {
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function(input, init = {}) {
      const method = String(init.method || input?.method || "GET").toUpperCase();
      const url = typeof input === "string" || input instanceof URL ? input : input?.url;
      const startedAt = performance.now();
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
