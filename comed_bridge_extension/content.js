(() => {
  // Some COMED cards are opened before a clinical-card id is assigned. Both
  // /patient-clinical-card/ and /patient-clinical-card/<id>/ are valid cards.
  const CARD_RE = /\/hasta-tibbi-karti\/(\d+)\/patient-clinical-card(?:\/(\d+))?\/?/;
  const WORKLIST_RE = /\/medical(?:\/hasta-tibbi-karti)?\/?$/;
  const SELECTED_PATIENT_KEY = "klinot-comed-selected-patient";
  const ACTIVE_TRANSFER_KEY = "klinot-comed-active-transfer";
  const LAST_DRAFT_SNAPSHOT_KEY = "klinot-comed-last-draft-snapshot";
  const SUPPRESS_RELOAD_PROMPT_KEY = "klinot-comed-suppress-reload-prompt-once";
  const TRACE_SOURCE = "klinot-comed-trace-v1";
  const NATIVE_COMMAND_SOURCE = "klinot-comed-native-command-v1";
  const NATIVE_RESULT_SOURCE = "klinot-comed-native-result-v1";
  const NATIVE_TIMEOUT_MS = 45000;
  const SYSTEM_REVIEW_DEFAULTS = {
    "Genel Sistem Sorgusu": "Özellik Yok",
    "Genitoüriner Sistem": "Özellik Yok",
    "Deri": "Özellik Yok",
    "Solunum Sistemi": "Özellik Yok",
    "Sinir Sistemi": "Özellik Yok",
    "Kas - İskelet Sistemi": "Özellik Yok",
    "Dolaşım Sistemi": "Özellik Yok",
    "Gastrointestinal Sistem": "Özellik Yok",
    "Komplikasyon": "Komplikasyon Yok",
  };

  let activeTransferId = Number(sessionStorage.getItem(ACTIVE_TRANSFER_KEY) || 0) || null;
  let busy = false;
  let routeBusy = false;
  let lastPath = "";
  let lastWorklistSyncAt = 0;
  let lastCardSyncAt = 0;
  let lastIdentityFingerprint = "";
  let dateRangeApplied = false;
  let dateRangeTries = 0;
  let captionTimer = null;
  let identitySyncTimer = null;
  let openingVisitId = null;
  let traceEnabled = true;
  let traceFlushTimer = null;
  const traceQueue = [];
  const nativePending = new Map();

  function request(path, options = {}) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({type: "klinot-request", path, options}, (response) => {
        if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
        if (!response?.ok) return reject(new Error(response?.error || "Köprü isteği başarısız"));
        resolve(response.data);
      });
    });
  }

  function scheduleTraceFlush(delay = 900) {
    if (traceFlushTimer) return;
    traceFlushTimer = setTimeout(flushTraceQueue, delay);
  }

  async function flushTraceQueue() {
    traceFlushTimer = null;
    if (!traceEnabled || !traceQueue.length) return;
    const events = traceQueue.splice(0, 25);
    try {
      await request("/api/v1/mobile/comed/request-log", {
        method: "POST", body: JSON.stringify({events}),
      });
    } catch (_) {
      traceQueue.unshift(...events);
      if (traceQueue.length > 250) traceQueue.splice(0, traceQueue.length - 250);
      scheduleTraceFlush(10000);
      return;
    }
    if (traceQueue.length) scheduleTraceFlush(300);
  }

  function validTraceEvent(value) {
    if (!value || typeof value !== "object") return false;
    try {
      const url = new URL(value.url);
      return url.protocol === "https:"
        && url.hostname === "goztepetestapi.comed.mlpcare.com"
        && /^(GET|POST|PUT|PATCH|DELETE)$/i.test(value.method || "GET");
    } catch (_) {
      return false;
    }
  }

  chrome.storage.local.get(["traceEnabled"], (value) => {
    traceEnabled = value.traceEnabled !== false;
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local" || !changes.traceEnabled) return;
    traceEnabled = changes.traceEnabled.newValue !== false;
    if (traceEnabled && traceQueue.length) scheduleTraceFlush(100);
  });

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== location.origin) return;
    if (event.data?.source === TRACE_SOURCE && traceEnabled && validTraceEvent(event.data.event)) {
      traceQueue.push(event.data.event);
      if (traceQueue.length > 250) traceQueue.shift();
      scheduleTraceFlush();
      return;
    }
    if (event.data?.source !== NATIVE_RESULT_SOURCE) return;
    const requestId = String(event.data.request_id || "");
    const pending = nativePending.get(requestId);
    if (!pending) return;
    clearTimeout(pending.timer);
    nativePending.delete(requestId);
    if (event.data.ok) pending.resolve(event.data.results || []);
    else pending.reject(new Error(event.data.error || "COMED POST başarısız"));
  });

  function executeNativePosts(visitId, requests) {
    return new Promise((resolve, reject) => {
      const requestId = crypto.randomUUID?.()
        || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const timer = setTimeout(() => {
        nativePending.delete(requestId);
        reject(new Error("COMED POST yanıt süresi aşıldı"));
      }, NATIVE_TIMEOUT_MS);
      nativePending.set(requestId, {resolve, reject, timer});
      window.postMessage({
        source: NATIVE_COMMAND_SOURCE,
        request_id: requestId,
        visit_id: String(visitId),
        requests,
      }, location.origin);
    });
  }

  const BRIDGE_LOG_KEY = "klinot_comed_bridge_log_v1";
  const BRIDGE_WIDGET_KEY = "klinot_comed_bridge_widget_v2";

  function bridgeLogs() {
    try { return JSON.parse(sessionStorage.getItem(BRIDGE_LOG_KEY) || "[]"); }
    catch (_) { return []; }
  }

  function bridgeWidgetState() {
    try { return JSON.parse(localStorage.getItem(BRIDGE_WIDGET_KEY) || "{}"); }
    catch (_) { return {}; }
  }

  function saveBridgeWidgetState(patch) {
    localStorage.setItem(BRIDGE_WIDGET_KEY, JSON.stringify({...bridgeWidgetState(), ...patch}));
  }

  function bridgeContext() {
    const body = textOf(document.body).slice(0, 2200);
    const match = location.pathname.match(CARD_RE);
    const patientNo = body.match(/Hasta\s*No[:\s]*(\d+)/i)?.[1] || "";
    const protocol = body.match(/\bV-(\d+)\b/)?.[0] || (match ? `V-${match[1]}` : "");
    const patientName = body.match(/^(.{3,80}?)(?=\s+(?:K|E|\d{1,3}\s*y|Hasta\s*No|V-))/i)?.[1]?.trim() || "";
    return [patientName, patientNo && `Hasta ${patientNo}`, protocol].filter(Boolean).join(" · ");
  }

  function bridgeFieldLabel(field) {
    const labels = {
      patient_complaint: "Hasta yakınması", patient_story: "Öykü",
      complaint_start_date: "Başlangıç tarihi", review_of_system_simple: "Sistem sorgusu özeti",
      exam_simple_textarea: "Muayene notu", treatment_note_v2: "İzlem ve tedavi planı",
      profile_and_family_history: "Özgeçmiş ve soygeçmiş", psychological_status: "Psikolojik durum",
      fall_risk: "Düşme riski", pain: "Ağrı değerlendirmesi", diagnoses: "Tanılar (ICD-10)",
      treatment_plan_label: "Tedavi türü", is_surgery_will_planned: "Ameliyat planı",
      is_control_suggested: "Kontrol önerisi", "review_of_system.document": "Sistem sorgulama belgesi",
    };
    if (labels[field]) return labels[field];
    if (field.startsWith("vitals.")) return `Vital bulgu · ${field.slice(7)}`;
    if (field.startsWith("review_of_system.")) return `Sistem sorgusu · ${field.split(".").at(-1)}`;
    return field.replaceAll("_", " ");
  }

  function ensureBridgeBox() {
    let box = document.getElementById("klinot-comed-bridge");
    if (box) return box;
    box = document.createElement("div");
    box.id = "klinot-comed-bridge";
    const widgetState = bridgeWidgetState();
    Object.assign(box.style, {
      position: "fixed", right: "20px", top: `${Math.max(72, Number(widgetState.top) || Math.round(innerHeight * .56))}px`,
      zIndex: "2147483647", color: "#fff", font: "600 12px system-ui",
      pointerEvents: "none",
    });
    box.innerHTML = `<style data-klinot-log-style>
      #klinot-comed-bridge *{box-sizing:border-box}
      @keyframes klinot-orb-in{from{opacity:0;transform:translateY(10px) scale(.86)}to{opacity:1;transform:none}}
      @keyframes klinot-pulse{0%{box-shadow:0 10px 30px #082c3855,0 0 0 0 #0b8c8233}70%{box-shadow:0 10px 30px #082c3855,0 0 0 15px #0b8c8200}100%{box-shadow:0 10px 30px #082c3855,0 0 0 0 #0b8c8200}}
      #klinot-comed-bridge [data-klinot-log-shell]{pointer-events:auto;position:relative;display:flex;align-items:center;justify-content:flex-end}
      #klinot-comed-bridge [data-klinot-log-orb]{position:relative;height:56px;width:56px;padding:0;border:0;border-radius:28px;background:linear-gradient(135deg,#0a9289,#06706c);color:#fff;display:flex;align-items:center;overflow:hidden;cursor:grab;box-shadow:0 10px 30px #082c3855;transition:width .26s cubic-bezier(.22,1,.36,1),border-radius .26s ease,background .2s ease,transform .18s ease;touch-action:none;animation:klinot-orb-in .32s cubic-bezier(.22,1,.36,1)}
      #klinot-comed-bridge [data-klinot-log-orb]:active{cursor:grabbing;transform:scale(.96)}
      #klinot-comed-bridge [data-klinot-log-orb][data-klinot-busy="1"]{animation:klinot-pulse 1.8s ease-out infinite}
      #klinot-comed-bridge [data-klinot-log-orb]:hover,#klinot-comed-bridge [data-klinot-log-orb]:focus-visible{width:196px;border-radius:28px}
      #klinot-comed-bridge [data-klinot-log-orb][aria-expanded="true"]{width:56px}
      #klinot-comed-bridge [data-klinot-log-mark]{width:56px;min-width:56px;height:56px;display:grid;place-items:center;font:800 20px system-ui;letter-spacing:.5px}
      #klinot-comed-bridge [data-klinot-log-label]{display:flex;flex-direction:column;align-items:flex-start;padding-right:18px;white-space:nowrap;opacity:0;transform:translateX(-10px);transition:opacity .2s ease .04s,transform .26s cubic-bezier(.22,1,.36,1) .04s}
      #klinot-comed-bridge [data-klinot-log-label] b{font:800 13px system-ui;line-height:1.2}
      #klinot-comed-bridge [data-klinot-log-label] i{font:600 11px system-ui;font-style:normal;opacity:.82;line-height:1.3}
      #klinot-comed-bridge [data-klinot-log-orb]:hover [data-klinot-log-label],#klinot-comed-bridge [data-klinot-log-orb]:focus-visible [data-klinot-log-label]{opacity:1;transform:none}
      #klinot-comed-bridge [data-klinot-log-orb][aria-expanded="true"] [data-klinot-log-label]{opacity:0;transform:translateX(-10px)}
      #klinot-comed-bridge [data-klinot-log-count]{position:absolute;right:-3px;top:-5px;display:grid;place-items:center;min-width:22px;height:22px;padding:0 6px;border:2px solid #fff;border-radius:99px;background:#3158c8;color:#fff;font:800 10px system-ui;pointer-events:none;box-shadow:0 3px 9px #0b253355}
      /* Islem sirasinda panel acmadan gorunen canli durum seridi. */
      #klinot-comed-bridge [data-klinot-log-caption]{position:absolute;right:68px;top:50%;transform:translate(10px,-50%);max-width:min(330px,calc(100vw - 110px));padding:9px 14px;border-radius:14px;background:#0f2f3aF2;color:#fff;font:650 12.5px/1.35 system-ui;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-shadow:0 10px 26px #0a222c45;opacity:0;visibility:hidden;transition:opacity .2s ease,transform .26s cubic-bezier(.22,1,.36,1),visibility .2s;pointer-events:none}
      #klinot-comed-bridge [data-klinot-log-caption][data-show="1"]{opacity:1;visibility:visible;transform:translate(0,-50%)}
      #klinot-comed-bridge [data-klinot-log-caption] b{display:block;font-weight:800}
      #klinot-comed-bridge [data-klinot-log-caption] i{display:block;margin-top:2px;font-style:normal;font-weight:600;opacity:.78;font-size:11px}
      #klinot-comed-bridge [data-klinot-log-caption][data-state="ok"]{background:#0b5f47F2}
      #klinot-comed-bridge [data-klinot-log-caption][data-state="bad"]{background:#8d2a26F2}
      #klinot-comed-bridge [data-klinot-log-caption][data-final="1"]{white-space:normal;max-width:min(300px,calc(100vw - 110px))}
      @media(max-width:620px){#klinot-comed-bridge [data-klinot-log-caption]{display:none}}
      #klinot-comed-bridge [data-klinot-log-panel]{position:absolute;right:72px;top:50%;width:min(420px,calc(100vw - 112px));max-height:min(520px,calc(100vh - 32px));display:flex;flex-direction:column;overflow:hidden;background:#fff;color:#173143;border:1px solid #d6e5e7;border-radius:20px;box-shadow:0 22px 56px #102b3a33;opacity:0;visibility:hidden;transform:translate(26px,-50%) scale(.94);transform-origin:right center;transition:opacity .24s ease,transform .3s cubic-bezier(.22,1,.36,1),visibility .24s;pointer-events:none}
      #klinot-comed-bridge [data-klinot-log-panel][aria-hidden="false"]{opacity:1;visibility:visible;transform:translate(0,-50%) scale(1);pointer-events:auto}
      #klinot-comed-bridge [data-klinot-log-header]{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:13px 15px;background:#f4f9f9;border-bottom:1px solid #e0edee}
      #klinot-comed-bridge [data-klinot-log-close]{display:grid;place-items:center;width:30px;height:30px;flex:0 0 auto;border:0;border-radius:10px;background:#e4eeee;color:#36535a;cursor:pointer;transition:background .15s ease,transform .15s ease}
      #klinot-comed-bridge [data-klinot-log-close]:hover svg{transform:translateY(1px)}
      #klinot-comed-bridge [data-klinot-log-close] svg{transition:transform .15s ease}
      #klinot-comed-bridge [data-klinot-log-close]:hover{background:#d2e2e2}
      #klinot-comed-bridge [data-klinot-log-summary]{padding:11px 15px;background:linear-gradient(135deg,#0a9289,#06706c);color:#fff}
      #klinot-comed-bridge [data-klinot-log-list]{flex:1 1 auto;min-height:0;overflow:auto;padding:5px 11px;overscroll-behavior:contain}
      @media(max-width:620px){#klinot-comed-bridge [data-klinot-log-panel]{right:66px;width:calc(100vw - 96px)}}
    </style><div data-klinot-log-shell><section data-klinot-log-panel aria-hidden="true"><div data-klinot-log-header><span><strong style="display:block;font-size:13px">İşlem günlüğü</strong><small data-klinot-log-panel-count style="color:#60777d;font-weight:600"></small></span><button data-klinot-log-close type="button" aria-label="İşlem günlüğünü aşağı indir" title="Aşağı indir"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button></div><div data-klinot-log-summary><strong data-klinot-log-title>Klinot hazır</strong><small data-klinot-log-context style="display:block;margin-top:3px;opacity:.82;font-weight:500;overflow-wrap:anywhere"></small></div><div data-klinot-log-list></div></section><div data-klinot-log-caption data-show="0" aria-live="polite"><b data-klinot-caption-text></b><i data-klinot-caption-sub></i></div><button data-klinot-log-orb type="button" aria-expanded="false" aria-label="Klinot işlem günlüğünü aç"><span data-klinot-log-mark aria-hidden="true">K</span><span data-klinot-log-label><b>Klinot</b><i data-klinot-log-tag>İşlem günlüğü</i></span></button><span data-klinot-log-count>0</span></div>`;
    const shell = box.querySelector("[data-klinot-log-shell]");
    const orb = box.querySelector("[data-klinot-log-orb]");
    const panel = box.querySelector("[data-klinot-log-panel]");
    const setOpen = (open) => {
      panel.setAttribute("aria-hidden", String(!open));
      orb.setAttribute("aria-expanded", String(open));
      orb.setAttribute("aria-label", open ? "Klinot işlem günlüğünü kapat" : "Klinot işlem günlüğünü aç");
      // Gunluk acikken canli serit panelin uzerine binmesin.
      const caption = box.querySelector("[data-klinot-log-caption]");
      if (open && caption) caption.dataset.show = "0";
    };
    let drag = null;
    let suppressClick = false;
    const finishDrag = () => {
      if (!drag) return;
      const moved = drag.moved;
      drag = null;
      const rect = box.getBoundingClientRect();
      const top = Math.max(72, Math.min(innerHeight - 72, rect.top));
      box.style.top = `${top}px`;
      saveBridgeWidgetState({top});
      if (moved) {
        suppressClick = true;
        setTimeout(() => { suppressClick = false; }, 0);
      }
    };
    orb.addEventListener("pointerdown", (event) => {
      if (event.button != null && event.button !== 0) return;
      drag = {y: event.clientY, top: box.getBoundingClientRect().top, moved: false};
      orb.setPointerCapture?.(event.pointerId);
    });
    orb.addEventListener("pointermove", (event) => {
      if (!drag) return;
      const dy = event.clientY - drag.y;
      if (Math.abs(dy) > 5) drag.moved = true;
      box.style.top = `${Math.max(72, Math.min(innerHeight - 72, drag.top + dy))}px`;
    });
    orb.addEventListener("pointerup", finishDrag);
    orb.addEventListener("pointercancel", finishDrag);
    orb.addEventListener("click", () => {
      if (!suppressClick) setOpen(orb.getAttribute("aria-expanded") !== "true");
    });
    box.querySelector("[data-klinot-log-close]").addEventListener("click", () => setOpen(false));
    document.body.appendChild(box);
    return box;
  }

  function renderBridgeStatus(text, state) {
    const box = ensureBridgeBox();
    const theme = state === "ok"
      ? {solid: "#087454", grad: "linear-gradient(135deg,#0ea07e,#077053)", tag: "Tamamlandı"}
      : state === "bad"
        ? {solid: "#b5322d", grad: "linear-gradient(135deg,#d2514a,#a62b26)", tag: "Kontrol gerekli"}
        : {solid: "#3158c8", grad: "linear-gradient(135deg,#4a71e0,#2a49ad)", tag: "İşleniyor"};
    const orb = box.querySelector("[data-klinot-log-orb]");
    orb.style.background = theme.grad;
    orb.dataset.klinotBusy = state === "idle" ? "1" : "0";
    box.querySelector("[data-klinot-log-tag]").textContent = theme.tag;
    box.querySelector("[data-klinot-log-count]").style.background = theme.solid;
    box.querySelector("[data-klinot-log-summary]").style.background = theme.grad;
    box.querySelector("[data-klinot-log-title]").textContent = `Klinot · ${text}`;
    renderBridgeCaption(box, text, state);
    box.querySelector("[data-klinot-log-context]").textContent = bridgeContext();
    const logs = bridgeLogs().slice().reverse();
    box.querySelector("[data-klinot-log-count]").textContent = String(logs.length);
    box.querySelector("[data-klinot-log-panel-count]").textContent = `${logs.length} işlem`;
    const list = box.querySelector("[data-klinot-log-list]");
    list.replaceChildren(...logs.map((entry) => {
      const row = document.createElement("div");
      row.style.cssText = "display:grid;grid-template-columns:10px minmax(0,1fr) auto;align-items:start;gap:9px;padding:9px 4px;border-bottom:1px solid #edf2f3;font-weight:500;line-height:1.35";
      const dot = document.createElement("i");
      dot.style.cssText = `width:8px;height:8px;margin-top:4px;border-radius:50%;background:${entry.state === "bad" ? "#c73b34" : entry.state === "ok" ? "#078d83" : "#5976da"}`;
      const copy = document.createElement("div");
      copy.style.cssText = "min-width:0";
      const title = document.createElement("div");
      title.textContent = entry.text;
      title.style.cssText = "color:#173143;overflow-wrap:anywhere";
      const state = document.createElement("small");
      state.textContent = entry.state === "bad" ? "Kontrol gerekli" : entry.state === "ok" ? "Tamamlandı" : "İşleniyor";
      state.style.cssText = `display:block;margin-top:2px;color:${entry.state === "bad" ? "#b5322d" : entry.state === "ok" ? "#087454" : "#5976da"};font-weight:700`;
      copy.append(title, state);
      if (entry.context) {
        const context = document.createElement("small");
        context.textContent = entry.context;
        context.style.cssText = "display:block;margin-top:3px;color:#60777d;font-weight:500;overflow-wrap:anywhere";
        copy.append(context);
      }
      const time = document.createElement("time");
      time.textContent = entry.time;
      time.style.cssText = "color:#789095;font-size:10px;font-weight:600;white-space:nowrap";
      row.append(dot, copy, time);
      return row;
    }));
  }

  /* Panel acmadan, orbun yaninda gorunen canli durum seridi. Doktor aktarim
     sirasinda hangi alanin islendigini anlik gorur; detayli gunluk yine
     balona tiklayinca acilir. Son adimda mesaj kalici kalir. */
  const BRIDGE_FINAL_TEXT = "Aktarım bitti · Genel doktor kontrolü gerekli";

  function renderBridgeCaption(box, text, state) {
    const caption = box.querySelector("[data-klinot-log-caption]");
    if (!caption) return;
    const panelOpen = box.querySelector("[data-klinot-log-panel]")
      ?.getAttribute("aria-hidden") === "false";
    const isFinal = String(text).startsWith(BRIDGE_FINAL_TEXT);
    caption.dataset.state = state;
    caption.dataset.final = isFinal ? "1" : "0";
    caption.querySelector("[data-klinot-caption-text]").textContent =
      isFinal ? "Aktarım bitti" : text;
    caption.querySelector("[data-klinot-caption-sub]").textContent = isFinal
      ? "Lütfen kontrol edip Kaydet ve İmzala"
      : (bridgeContext() || "COMED aktarımı");
    caption.dataset.show = panelOpen ? "0" : "1";

    clearTimeout(captionTimer);
    // Son mesaj doktorun imza adimidir; kendiliginden kaybolmaz.
    if (!isFinal) {
      captionTimer = setTimeout(() => { caption.dataset.show = "0"; }, 6000);
    }
  }

  function bridgeStatus(text, state = "idle") {
    const logs = bridgeLogs();
    const entry = {text: String(text), state, context: bridgeContext(), time: new Date().toLocaleTimeString("tr-TR", {hour: "2-digit", minute: "2-digit", second: "2-digit"})};
    if (logs.at(-1)?.text !== entry.text || logs.at(-1)?.context !== entry.context) logs.push(entry);
    sessionStorage.setItem(BRIDGE_LOG_KEY, JSON.stringify(logs.slice(-120)));
    renderBridgeStatus(text, state);
  }

  function bridgeFieldStatus(field, ok) {
    bridgeStatus(`${bridgeFieldLabel(field)} ${ok ? "dolduruldu" : "bulunamadı"}`, ok ? "ok" : "bad");
  }

  function textOf(root) {
    return (root?.innerText || "").replace(/\s+/g, " ").trim();
  }

  // ``innerText`` yalnızca görünen metni döndürür; gizli paneldeki kimlik
  // alanlarını da okuyabilmek için ham metin içeriğini verir.
  function deepTextOf(root) {
    return (root?.textContent || "").replace(/\s+/g, " ").trim();
  }

  function parsePatientIdentity() {
    const identityRoots = [...document.querySelectorAll('[role="dialog"],.co-popover,.co-drawer,.patient-info')];
    // COMED, hasta kimlik alanlar\u0131n\u0131 yaln\u0131zca "Hasta Bilgileri" a\u00e7\u0131l\u0131r panelinde
    // g\u00f6sterir. ``innerText`` sadece g\u00f6r\u00fcnen metni verdi\u011fi i\u00e7in panel kapal\u0131yken
    // TCKN ve do\u011fum tarihi okunam\u0131yor, hasta giri\u015fi de e\u015fle\u015femiyordu. Bu y\u00fczden
    // g\u00f6r\u00fcn\u00fcr metne ek olarak gizli d\u00fc\u011f\u00fcmleri de kapsayan ``textContent`` taran\u0131r.
    const raw = [
      identityRoots.map(textOf).join(" "),
      textOf(document.body),
      identityRoots.map(deepTextOf).join(" "),
      deepTextOf(document.body),
    ].join(" ").replace(/\u00a0/g, " ");
    const phone = raw.match(/Telefon\s*[:\-]?\s*\(?0?(\d{3})\)?[\s-]*(\d{3})[\s-]*(\d{2})[\s-]*(\d{2})/i);
    const phoneDigits = phone ? phone.slice(1).join("") : "";
    const tckn = raw.match(/\b(?:T\.?\s*C\.?|TC)\s*(?:\/\s*(?:Pasaport|Passport))?\s*(?:No|Numarası|Kimlik\s*No)?\s*[:\-]?\s*(\d{11})\b/i)?.[1] || "";
    const birthDate = raw.match(/Do[ğg]um\s*Tarihi(?:\s*-\s*Ya[şs])?\s*[:\-]?\s*(\d{2}[.\/-]\d{2}[.\/-]\d{4})/i)?.[1]
      ?.replaceAll("/", ".").replaceAll("-", ".") || "";
    return {
      tckn,
      birth_date: birthDate,
      phone_masked: phoneDigits ? `*** ** ${phoneDigits.slice(-2)}` : "",
    };
  }

  function schedulePatientIdentitySync() {
    if (!CARD_RE.test(location.pathname)) return;
    const identity = parsePatientIdentity();
    if (!identity.tckn || !identity.birth_date) return;
    const fingerprint = `${location.pathname}|${identity.tckn}|${identity.birth_date}`;
    if (fingerprint === lastIdentityFingerprint) return;
    lastIdentityFingerprint = fingerprint;
    clearTimeout(identitySyncTimer);
    identitySyncTimer = setTimeout(async () => {
      try {
        await syncCurrentCard();
        lastCardSyncAt = Date.now();
        bridgeStatus("Hasta kimliği randevuyla eşleştirildi", "ok");
      } catch (error) {
        lastIdentityFingerprint = "";
        if (!/bağlı değil/i.test(error.message)) bridgeStatus(`Kimlik eşleştirme hatası: ${error.message}`, "bad");
      }
    }, 350);
  }

  // COMED'in kart basligi ismin hemen ardindan cinsiyet, yas, dogum tarihi ve
  // hasta numarasini bosluksuz ekler: "Sena Nur ... K28yil22.10.1997 Hasta No:1300013".
  // Ilk meta isaretinden itibaren keserek yalnizca ad soyadi birak.
  function cleanPatientName(value) {
    const name = String(value || "")
      .split(
        // Cinsiyet kodu ancak bir harfin ardindan GELMIYORSA meta sayilir; aksi
        // halde "Ayse 45yil" gibi bir metinde ismin son harfi kesilirdi. JS'te
        // \b Turkce harflerde guvenilir olmadigi icin acik lookbehind kullanilir.
        /\s*(?:(?<![A-Za-zÇĞİÖŞÜçğıöşü])[KE]\s*\d{1,3}\s*y[ıi]l|\d{2}[.\/-]\d{2}[.\/-]\d{4}|Hasta\s*No|Merkez\s*Hasta|Protokol|V-\d)/i,
      )[0]
      .replace(/[\s|·,;:-]+$/u, "")
      .trim();
    return name.length >= 3 ? name.slice(0, 80) : "";
  }

  function parseRow(row, card = {}) {
    if (!row) return null;
    const cells = [...row.querySelectorAll(":scope > td, :scope > [role=cell]")];
    const raw = textOf(row);
    const protocol = raw.match(/V-(\d+)/)?.[0] || "";
    const visitId = String(card.visitId || protocol.replace("V-", "")).trim();
    if (!visitId) return null;
    const patientCell = cells[0];
    const patientLines = (patientCell?.innerText || "")
      .split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
    const patientNo = patientLines.findLast?.((value) => /^\d{4,}$/.test(value))
      || raw.match(/\b(\d{5,})\b/)?.[1] || "";
    const patientName = cleanPatientName(patientCell?.querySelector("img[alt]")?.alt)
      || cleanPatientName(patientLines[0]) || "COMED hastası";
    const taskText = textOf(cells[6]) || raw;
    const doctorLines = (cells[9]?.innerText || "")
      .split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
    return {
      visit_id: visitId,
      clinical_card_id: String(card.cardId || ""),
      patient_id: patientNo,
      patient_name: patientName,
      patient_no: patientNo,
      protocol_no: protocol || `V-${visitId}`,
      department: taskText.replace(/\s*muayenesi.*$/i, "").trim(),
      doctor_name: doctorLines.at(-1) || "",
      task: taskText,
      status: /Bekliyor/i.test(raw) ? "Bekliyor" : "",
      clinical_card_url: card.url || "",
    };
  }

  function parseWorklist() {
    const seen = new Set();
    return [...document.querySelectorAll("tbody tr, [role=row]")]
      .map((row) => parseRow(row))
      .filter((item) => item && !seen.has(item.visit_id) && seen.add(item.visit_id));
  }

  function rowForVisit(visitId) {
    return [...document.querySelectorAll("tbody tr, [role=row]")]
      .find((row) => parseRow(row)?.visit_id === String(visitId));
  }

  async function openPendingTransferFromWorklist() {
    if (openingVisitId) return;
    const payload = await request("/api/v1/mobile/comed/bridge/transfers");
    const pending = (payload.items || []).find((item) => rowForVisit(item.visit_id));
    if (!pending) return;
    const row = rowForVisit(pending.visit_id);
    const button = [...(row?.querySelectorAll("button") || [])]
      .find((item) => textOf(item) === "Göreve Git");
    if (!button) return;
    const selected = parseRow(row);
    if (selected) sessionStorage.setItem(SELECTED_PATIENT_KEY, JSON.stringify(selected));
    openingVisitId = String(pending.visit_id);
    bridgeStatus(`${selected?.patient_name || "Hasta"} kartı aktarım için açılıyor`);
    button.click();
    setTimeout(() => {
      if (WORKLIST_RE.test(location.pathname)) openingVisitId = null;
    }, 10000);
  }

  async function syncCurrentCard() {
    const match = location.pathname.match(CARD_RE);
    if (!match) return;
    let selected = null;
    try {
      selected = JSON.parse(sessionStorage.getItem(SELECTED_PATIENT_KEY) || "null");
    } catch (_) {}
    const headerText = textOf(document.body).slice(0, 1600);
    const fallback = {
      visit_id: match[1],
      patient_name: cleanPatientName(headerText.match(/^([^|\n]{3,120})/)?.[1]) || "COMED hastası",
      patient_no: headerText.match(/Hasta\s*No[:\s]*(\d+)/i)?.[1] || "",
      protocol_no: `V-${match[1]}`,
      task: "Açık hasta tıbbi kartı",
    };
    const item = {
      ...fallback,
      ...(selected?.visit_id === match[1] ? selected : {}),
      ...parsePatientIdentity(),
      visit_id: match[1],
      clinical_card_id: match[2] || selected?.clinical_card_id || "",
      clinical_card_url: location.href,
    };
    await request("/api/v1/mobile/comed/worklist/sync", {
      method: "POST", body: JSON.stringify({items: [item], replace: false}),
    });
    sessionStorage.removeItem(SELECTED_PATIENT_KEY);
  }

  // COMED is listesi varsayilan olarak yalnizca BUGUNU gosterir. Kartlar
  // genelde gecmis tarihli oldugu icin liste bos gorunur ve koprunun
  // esitleyecek satiri kalmaz. Sayfa her yuklendiginde bir kez "3 Ay" araligi
  // secilir. Doktor sonradan araligi degistirirse tekrar zorlanmaz; bayrak
  // yalnizca sayfa yenilendiginde sifirlanir.
  const RANGE_RE = /(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})/;

  function rangeValueOf(node) {
    if (!node) return "";
    const raw = String(node.value || "").trim() || textOf(node);
    return (raw.match(RANGE_RE) || [""])[0];
  }

  // Araligin gercekten genisledigini dogrular: iki tarih artik farkli olmali.
  function rangeIsWide(node) {
    const match = rangeValueOf(node).match(RANGE_RE);
    return Boolean(match && match[1] !== match[2]);
  }

  // COMED is listesi varsayilan olarak yalnizca BUGUNU gosterir. Kartlar
  // genelde gecmis tarihli oldugu icin liste bos gorunur ve koprunun
  // esitleyecek satiri kalmaz. Bu yuzden bir kez "3 Ay" araligi secilir.
  // ONEMLI: bayrak yalnizca BASARIDAN SONRA set edilir. Onceki surumde bayrak
  // denemeden once set edildigi icin ilk deneme erken calisip basarisiz
  // oldugunda bir daha hic denenmiyordu.
  async function ensureWorklistDateRange() {
    if (dateRangeApplied || dateRangeTries >= 8) return;
    dateRangeTries += 1;
    try {
      // Tarih kutusu COMED'de ``disabled`` bir input'tur; ona tiklamak hicbir
      // olay tetiklemez. Takvimi yalnizca yanindaki ikon dugmesi acar.
      const picker = await waitFor(
        () => document.querySelector('[data-test="co-date-time-picker"]'), 6000,
      );
      if (!picker) return;
      if (rangeIsWide(picker.querySelector("input"))) {
        dateRangeApplied = true;
        return;
      }

      const opener = picker.querySelector('[data-test="co-button-icon-calendar"]')
        || picker.querySelector("button");
      if (!opener) return;
      activateNode(opener);

      const monthButton = await waitFor(() => [
        ...document.querySelectorAll("button"),
      ].find((element) => element.offsetParent !== null
        && textOf(element) === "3 Ay"), 2500);
      if (!monthButton) return;
      activateNode(monthButton);

      // "3 Ay" secimi araligi aninda uygular ve paneli kapatir; "Tamam" yalnizca
      // acik kalirsa gereklidir.
      await sleep(320);
      const confirm = [...document.querySelectorAll("button")].find(
        (element) => element.offsetParent !== null && textOf(element) === "Tamam",
      );
      if (confirm) activateNode(confirm);
      await waitForDomQuiet(document.body, 260, 3000);

      if (rangeIsWide(picker.querySelector("input"))) {
        dateRangeApplied = true;
        bridgeStatus("İş listesi son 3 aya genişletildi", "ok");
      }
    } catch (_) {
      // COMED arayuzu degisirse koprunun geri kalani calismaya devam etsin.
    }
  }

  async function syncWorklist() {
    await ensureWorklistDateRange();
    const items = parseWorklist();
    try {
      // Boş ayrıştırma neredeyse her zaman "sayfa henüz yüklenmedi" demektir;
      // doktorun gerçekten sıfır hastası olduğu anlamına gelmez. Bu durumda
      // ``replace`` göndermeyiz, aksi halde sunucu mevcut iş listesini ve
      // hastanın kimlik eşleşmesini siler.
      await request("/api/v1/mobile/comed/worklist/sync", {
        method: "POST", body: JSON.stringify({items, replace: items.length > 0}),
      });
      bridgeStatus(
        items.length ? `${items.length} hasta iş listesine eşitlendi` : "İş listesi okunamadı, mevcut liste korundu",
        items.length ? "ok" : "idle",
      );
    } catch (error) {
      bridgeStatus(error.message, "bad");
    }
  }

  // Native POST is preferred when a verified same-visit template exists.  The
  // COMED test environment does not expose such a template for every protocol,
  // so the bridge keeps a form-filling fallback.  This fallback only prepares a
  // draft on the currently open card; it never clicks Kaydet or Kaydet ve İmzala.
  function setValue(element, value) {
    if (!element || value === null || value === undefined || value === "") return false;
    const proto = element instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    setter?.call(element, String(value));
    element.dispatchEvent(new Event("input", {bubbles: true}));
    element.dispatchEvent(new Event("change", {bubbles: true}));
    element.dispatchEvent(new Event("blur", {bubbles: true}));
    return true;
  }

  function setTypingValue(element, value) {
    if (!element || value === null || value === undefined || value === "") return false;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    setter?.call(element, String(value));
    element.focus();
    element.dispatchEvent(new Event("input", {bubbles: true}));
    element.dispatchEvent(new Event("change", {bubbles: true}));
    return true;
  }

  function byPlaceholder(value, root = document) {
    const wanted = value.toLocaleLowerCase("tr-TR");
    return [...root.querySelectorAll("input,textarea")]
      .find((element) => (element.getAttribute("placeholder") || "")
        .trim().toLocaleLowerCase("tr-TR") === wanted) || null;
  }

  function widgetByTitle(title) {
    return document.querySelector(`[data-test="widget-${title}"]`);
  }

  function cardByTitle(title) {
    return widgetByTitle(title) || [...document.querySelectorAll(".hasta-detay-card")]
      .filter((card) => [...card.querySelectorAll(".hasta-detay-card__title")]
        .some((node) => textOf(node) === title))
      .sort((a, b) => textOf(a).length - textOf(b).length)[0] || null;
  }

  async function ensureCardOpen(title, visiblePlaceholder = null) {
    const card = cardByTitle(title);
    if (!card || (visiblePlaceholder && byPlaceholder(visiblePlaceholder, card)?.offsetParent)) {
      return card;
    }
    const editorAlreadyVisible = [...card.querySelectorAll(
      "input,textarea,table,.autocomplete__input",
    )].some((element) => element.offsetParent !== null);
    if (editorAlreadyVisible) return card;
    card.querySelector(".hasta-detay-card__icon")?.click();
    await sleep(100);
    const editorOpened = [...card.querySelectorAll(
      "input,textarea,table,.autocomplete__input",
    )].some((element) => element.offsetParent !== null);
    if (editorOpened) return card;
    const heading = [...card.querySelectorAll(".hasta-detay-card__title,[data-test],span,div")]
      .find((node) => textOf(node) === title);
    heading?.click();
    await sleep(120);
    return card;
  }

  function fieldGroupByLabel(label, root = document) {
    return [...root.querySelectorAll(".co-input")]
      .filter((group) => {
        const labelNode = group.querySelector(":scope > .co-input__label, .co-input__label");
        return textOf(labelNode) === label;
      })
      .sort((a, b) => textOf(a).length - textOf(b).length)[0] || null;
  }

  function inputByLabel(label, root = document) {
    return fieldGroupByLabel(label, root)
      ?.querySelector("input:not([disabled]),textarea:not([disabled])") || null;
  }

  function activateNode(node) {
    if (!node) return false;
    const target = node.matches("button,label,input,[role=radio],[role=checkbox],.toggle-button__item,.autocomplete__item")
      ? node
      : node.closest("button,label,[role=radio],[role=checkbox],.toggle-button__item,.autocomplete__item") || node;
    if (target.matches("label")) {
      const control = target.control
        || (target.htmlFor ? document.getElementById(target.htmlFor) : null);
      if (control && !control.disabled) {
        control.click();
        return true;
      }
    }
    if (target.disabled) return false;
    target.click();
    return true;
  }

  function clickText(text, root = document) {
    const node = [...root.querySelectorAll(
      "button,label,[role=radio],[role=checkbox],.toggle-button__item,.autocomplete__item,span",
    )].find((element) => textOf(element) === text && element.offsetParent !== null);
    return activateNode(node);
  }

  function clickCardOption(cardTitle, text) {
    const card = cardByTitle(cardTitle);
    return card ? clickText(text, card) : false;
  }

  function clickFieldOption(label, text, root = document) {
    const group = fieldGroupByLabel(label, root);
    return group ? clickText(text, group) : false;
  }

  function checkboxByLabel(root, label) {
    const wanted = label.toLocaleLowerCase("tr-TR");
    const candidates = [...root.querySelectorAll('label,[role="checkbox"]')];
    const labelNode = candidates.find((node) => textOf(node).toLocaleLowerCase("tr-TR") === wanted);
    if (!labelNode) return null;
    const input = labelNode.matches('input[type="checkbox"]')
      ? labelNode
      : labelNode.control
        || (labelNode.htmlFor ? document.getElementById(labelNode.htmlFor) : null)
        || labelNode.querySelector('input[type="checkbox"]');
    return {input, labelNode};
  }

  function setCheckboxByLabel(root, label, checked = true) {
    const match = checkboxByLabel(root, label);
    if (!match) return false;
    const {input, labelNode} = match;
    if (input) {
      if (input.disabled) return false;
      if (input.checked !== checked) input.click();
      return input.checked === checked;
    }
    const current = labelNode.getAttribute("aria-checked") === "true";
    if (current !== checked) labelNode.click();
    return (labelNode.getAttribute("aria-checked") === "true") === checked;
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function waitFor(getter, timeoutMs = 4500) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const value = getter();
      if (value) return value;
      await sleep(120);
    }
    return null;
  }

  async function waitForClinicalFormReady(timeoutMs = 45000) {
    bridgeStatus("COMED hasta kartının yüklenmesi bekleniyor");
    return waitFor(() => {
      if (!CARD_RE.test(location.pathname)) return null;
      const complaint = cardByTitle("Yakınması");
      const system = cardByTitle("Sistem Sorgusu");
      const examination = cardByTitle("Fizik Muayene Bulguları");
      return complaint && system && examination ? true : null;
    }, timeoutMs);
  }

  function systemInquiryOpener() {
    return [...document.querySelectorAll("button,a,[role=button]")]
      .find((node) => node.offsetParent !== null
        && normalizedText(textOf(node)).includes("sistem sorgulama")) || null;
  }

  function normalizedText(value) {
    return String(value || "")
      .normalize("NFKC")
      .replace(/\s+/g, " ")
      .trim()
      .toLocaleLowerCase("tr-TR");
  }

  function profileItemAlreadyPresent(history, name) {
    const wanted = normalizedText(name);
    return Boolean(wanted && normalizedText(textOf(history)).includes(wanted));
  }

  function profileEntryAlreadyPresent(history, name, description = "") {
    const haystack = normalizedText(textOf(history));
    const detail = normalizedText(description);
    if (detail && haystack.includes(detail)) return true;
    const wanted = normalizedText(name);
    if (!wanted) return false;
    // Açık editördeki seçenek etiketi bir kez görünür; ikinci görünüm kayıtlı
    // etiketi/çipi gösterir. Böylece aynı sigara kaydı tekrar eklenmez.
    return haystack.split(wanted).length - 1 > 1;
  }

  function duplicateProfileNotice() {
    return [...document.querySelectorAll("div,section")]
      .filter((element) => element.getClientRects().length
        && /bu hastal[ıi]k hastaya ait bu protokol i[çc]in daha [öo]nce tan[ıi]mlanm[ıi][şs]/i
          .test(textOf(element)))
      .sort((a, b) => textOf(a).length - textOf(b).length)[0] || null;
  }

  function waitForDomQuiet(root = document.body, quietMs = 220, timeoutMs = 2200) {
    if (!root) return Promise.resolve();
    return new Promise((resolve) => {
      let quietTimer = null;
      let timeoutTimer = null;
      const finish = () => {
        clearTimeout(quietTimer);
        clearTimeout(timeoutTimer);
        observer.disconnect();
        resolve();
      };
      const arm = () => {
        clearTimeout(quietTimer);
        quietTimer = setTimeout(finish, quietMs);
      };
      const observer = new MutationObserver(arm);
      observer.observe(root, {subtree: true, childList: true, attributes: true, characterData: true});
      timeoutTimer = setTimeout(finish, timeoutMs);
      arm();
    });
  }

  async function closeKnownDuplicateProfileNotice(timeoutMs = 360) {
    const duplicate = await waitFor(duplicateProfileNotice, timeoutMs);
    if (!duplicate) return false;

    let container = duplicate;
    for (let depth = 0; depth < 6 && container; depth += 1) {
      const visibleButtons = [...container.querySelectorAll("button,[role=button]")]
        .filter((button) => button.getClientRects().length && !button.disabled);
      const close = visibleButtons.find((button) => {
        const hint = normalizedText([
          textOf(button), button.getAttribute("aria-label"),
          button.getAttribute("title"), button.className,
        ].filter(Boolean).join(" "));
        return /kapat|close|dismiss|modal.*close|(^|\s)[x×](\s|$)/i.test(hint);
      }) || visibleButtons.at(-1);
      if (close) {
        close.click();
        await sleep(120);
        return true;
      }
      container = container.parentElement;
    }
    document.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Escape", code: "Escape", bubbles: true,
    }));
    await sleep(120);
    return true;
  }

  function itemParts(item) {
    if (typeof item === "string") return {name: item.trim(), description: ""};
    return {
      name: String(item?.name || item?.value || "").trim(),
      description: String(item?.description || "").trim(),
    };
  }

  function smallestFieldRow(input, root) {
    let node = input?.parentElement;
    while (node && node !== root) {
      const hasDescription = Boolean(byPlaceholder("Açıklama", node));
      const buttons = [...node.querySelectorAll("button")];
      const hasNoButton = buttons.some((button) => textOf(button) === "Yok");
      const hasCommit = buttons.some((button) => /warning|success|orange|add|plus/i.test(button.className)
        || /ekle|arti/i.test(button.getAttribute("data-test") || ""));
      if (hasDescription && hasNoButton && hasCommit) return node;
      node = node.parentElement;
    }
    return input?.parentElement || root;
  }

  async function chooseAutocomplete(input, query) {
    if (!input || !query) return false;
    setTypingValue(input, query);
    const normalized = query.toLocaleLowerCase("tr-TR");
    const result = await waitFor(() => [...document.querySelectorAll(".autocomplete__item")]
      .filter((item) => item.offsetParent !== null)
      .find((item) => {
        const text = textOf(item).toLocaleLowerCase("tr-TR");
        return text === normalized || text.startsWith(`${normalized} |`) || text.includes(normalized);
      }), 6500);
    if (!result) return false;
    result.click();
    await sleep(120);
    return true;
  }

  async function fillProfileLookup(history, placeholder, items = []) {
    let added = 0;
    for (const item of items) {
      const {name, description} = itemParts(item);
      if (!name) continue;
      // COMED aynı protokolde kayıtlı hastalığı yeniden eklerken bir sunucu
      // uyarısı açıyor. Var olan bilgi zaten hedefi karşılar; tekrar POST/form
      // işlemi yapmayarak hem uyarıyı hem de aktarımın bloke olmasını önle.
      if (profileItemAlreadyPresent(history, name)) {
        added += 1;
        continue;
      }
      const input = byPlaceholder(placeholder, history);
      if (!input || !await chooseAutocomplete(input, name)) continue;
      const row = smallestFieldRow(input, history);
      setValue(byPlaceholder("Açıklama", row), description);
      const commit = [...row.querySelectorAll("button")]
        .filter((button) => button.offsetParent !== null && !button.disabled && textOf(button) !== "Yok")
        .findLast((button) => /warning|success|orange|add|plus/i.test(button.className)
          || /ekle|arti/i.test(button.getAttribute("data-test") || ""));
      if (!commit) continue;
      commit.click();
      added += 1;
      const duplicateClosed = await closeKnownDuplicateProfileNotice();
      if (duplicateClosed) setTypingValue(input, "");
      await waitForDomQuiet(history, 100, 700);
    }
    return added;
  }

  function durationUnitLabel(unit) {
    return ({hour: "saat", day: "gün", week: "hafta", month: "ay", year: "yıl"})[unit];
  }

  function fillDuration(root, duration, label = null) {
    if (!root || !duration?.value) return false;
    const labelledScope = label ? fieldGroupByLabel(label, root) : null;
    const input = labelledScope?.querySelector("input.form-control,input[type=number],input:not([type])")
      || root.querySelector(".co-date-before input.form-control, .co-date-before input");
    if (!setValue(input, duration.value)) return false;
    const unit = durationUnitLabel(duration.unit);
    if (unit) clickText(unit, root);
    return true;
  }

  async function fillFallRisk(value) {
    const exists = typeof value === "object" ? value?.exists : value;
    // Dusme riski COMED'de zorunlu alandir. Gorusmede konu hic gecmemisse
    // "bilinmiyor" degil "yok" isaretlenir; aksi halde alan bos kalip form
    // kaydedilemiyordu. Doktor son kontrolde aksini gorurse duzeltir.
    if (exists !== true) return clickCardOption("Düşme Riski", "Yok");
    if (typeof value !== "object") return clickCardOption("Düşme Riski", "Yok");
    const normalized = {...value};
    if (!["65_plus", "under_65"].includes(normalized.age_group)) {
      const age = Number(textOf(document.body).match(/\b(\d{1,3})\s*y[ıi]l\b/i)?.[1]);
      if (age > 0) normalized.age_group = age >= 65 ? "65_plus" : "under_65";
    }
    const detailKeys = ["history", "medications", "addiction", "gait_balance_disorder",
      "vision_disorder", "oriented", "general_health_normal"];
    detailKeys.forEach((key) => {
      if (typeof normalized[key] !== "boolean") normalized[key] = false;
    });
    if (!["65_plus", "under_65"].includes(normalized.age_group)) return false;
    if (!clickCardOption("Düşme Riski", "Var")) return false;
    const popover = await waitFor(() => [...document.querySelectorAll(
      ".co-menu__content .co-popover,.co-menu__content,.co-popover.bottom,.co-popover",
    )].find((item) => item.offsetParent !== null && textOf(item).includes("Düşme Hikayesi")));
    if (!popover) return false;
    const choices = [
      ["Yaş", normalized.age_group === "65_plus", "65 yaş üstü", "65 yaş altı"],
      ["Düşme Hikayesi", normalized.history, "Var", "Yok"],
      ["Kullandığı İlaçlar", normalized.medications, "Var", "Yok"],
      ["Alkol / Madde Bağımlılığı", normalized.addiction, "Var", "Yok"],
      ["Yürüyüş ve Denge Bozuklukları", normalized.gait_balance_disorder, "Var", "Yok"],
      ["Görme Bozukluğu", normalized.vision_disorder, "Var", "Yok"],
      ["Ruhsal Durum", normalized.oriented, "Oryante", "Oryante Değil"],
      ["Genel Sağlık Durumu", normalized.general_health_normal, "Normal", "Normal Değil"],
    ];
    for (const [label, selected, yes, no] of choices) {
      if (!clickFieldOption(label, selected ? yes : no, popover)) return false;
      await sleep(35);
    }
    document.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Escape", code: "Escape", bubbles: true,
    }));
    await sleep(80);
    return true;
  }

  async function fillPainScore(card, score) {
    const numeric = Number(score);
    if (!Number.isFinite(numeric) || numeric < 0 || numeric > 10) return false;
    const opener = card.querySelector('[data-test="co-button-icon-external-link"]');
    if (!opener) return false;
    opener.click();
    const typeMenu = await waitFor(() => [...document.querySelectorAll(".co-popover")]
      .find((item) => item.offsetParent !== null && textOf(item).includes("NRS")));
    if (!typeMenu || !clickText("NRS", typeMenu)) return false;
    const range = await waitFor(() => [...document.querySelectorAll('.co-popover input[type="range"]')]
      .find((input) => input.offsetParent !== null));
    if (!range || !setValue(range, Math.round(numeric))) return false;
    document.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Escape", code: "Escape", bubbles: true,
    }));
    await sleep(80);
    const openScorePopover = [...document.querySelectorAll(".co-popover")]
      .find((item) => item.offsetParent !== null && item.contains(range));
    if (openScorePopover) opener.click();
    await sleep(80);
    return Number(card.querySelector("input[disabled]")?.value) === Math.round(numeric);
  }

  async function fillPain(pain) {
    if (pain?.exists === false) return clickCardOption("Ağrı", "Yok");
    if (pain?.exists !== true) return false;
    const card = cardByTitle("Ağrı");
    if (!card || !clickText("Var", card)) return false;
    await sleep(100);
    const scoreFilled = await fillPainScore(card, pain.score);
    setValue(byPlaceholder("Bölge", card), pain.location);
    setValue(byPlaceholder("Açıklama", card), pain.description);
    (pain.qualities || []).forEach((quality) => clickText(quality, card));
    if (pain.rhythm) clickText(pain.rhythm, card);
    // COMED'in Ağrı Başlangıcı bileşeni yalnızca gün cinsini kabul ediyor.
    // Saat bilgisini "2 gün" diye yanlış yazmak yerine ana yakınma süresinde koru.
    if (pain.start_date?.unit === "day") {
      fillDuration(card, pain.start_date, "Ağrı Başlangıcı");
    }
    return scoreFilled;
  }

  async function fillFamilyHistory(profile = {}) {
    if (profile.no_known_family_history === true) {
      return clickCardOption("Soygeçmiş", "Özellik Yok") ? 1 : 0;
    }
    const entries = profile.family_history || [];
    if (!entries.length && typeof profile.parents_related !== "boolean") {
      return clickCardOption("Soygeçmiş", "Görüldü") ? 1 : 0;
    }
    const card = await ensureCardOpen("Soygeçmiş");
    if (!card) return 0;
    await waitFor(() => [...card.querySelectorAll("input,textarea,table")]
      .find((element) => element.offsetParent !== null), 1800);
    let added = 0;
    for (const entry of entries) {
      const relationship = String(entry?.relationship || "").trim();
      const condition = String(entry?.condition || "").trim();
      const row = [...card.querySelectorAll("tr")]
        .find((candidate) => textOf(candidate.querySelector("td,th")) === relationship);
      const cells = [...(row?.querySelectorAll("td") || [])];
      const target = cells.slice(1).find((cell) => textOf(cell) === condition);
      if (!target) continue;
      target.click();
      const popover = await waitFor(() => [...document.querySelectorAll(".co-popover")]
        .find((item) => item.offsetParent !== null));
      if (!popover) continue;
      setValue(byPlaceholder("Açıklama Girin...", popover), entry.description);
      const save = popover.querySelector('[data-test*="kaydet"],button[type="submit"]')
        || [...popover.querySelectorAll("button")].findLast((button) => !button.disabled);
      if (!save) continue;
      save.click();
      added += 1;
      await sleep(100);
    }
    const related = [...card.querySelectorAll('input[type="checkbox"]')]
      .find((input) => /anne ile baba akraba/i.test(textOf(input.closest("label") || input.parentElement)));
    if (related && typeof profile.parents_related === "boolean"
      && related.checked !== profile.parents_related) related.click();
    clickText("Görüldü", card);
    // Soygecmis COMED'de zorunludur. Hicbir satir isaretlenemediyse alan bos
    // kalmamali; "Ozellik Yok" basilarak kayit edilebilir hale getirilir.
    if (!added) return clickCardOption("Soygeçmiş", "Özellik Yok") ? 1 : 0;
    return added;
  }

  function fillPsychologicalStatus(value = {}) {
    const states = value.states || [];
    if (!states.length && !value.description) return false;
    const card = cardByTitle("Psikolojik Durum");
    if (!card) return false;
    states.forEach((state) => clickText(state, card));
    setValue(byPlaceholder("Açıklama", card), value.description);
    return true;
  }

  async function fillProfile(profile = {}) {
    let filled = 0;
    if (profile.no_known_history === true && clickCardOption("Özgeçmiş", "Özellik Yok")) filled += 1;
    const history = await ensureCardOpen("Özgeçmiş", "Meslek");
    if (!history) return filled;
    await sleep(100);
    for (const item of profile.addictions || []) {
      const {name, description} = itemParts(item);
      const value = name.toLocaleLowerCase("tr-TR");
      const option = value.includes("sigara") ? "Sigara"
        : value.includes("alkol") ? "Alkol"
          : value.includes("madde") ? "Madde" : null;
      if (!option) continue;
      if (profileEntryAlreadyPresent(history, option, description)) {
        filled += 1;
        continue;
      }
      const optionLabel = [...history.querySelectorAll("label")]
        .find((label) => textOf(label) === option && label.offsetParent !== null);
      const row = optionLabel?.closest(".d-flex.align-items-center.position-relative");
      if (!row || !activateNode(optionLabel)) continue;
      await sleep(60);
      setValue(byPlaceholder("Açıklama", row), description);
      const commit = row.querySelector('[data-test="co-button-icon-arti"]');
      if (!commit || commit.disabled) continue;
      commit.click();
      filled += 1;
      await waitForDomQuiet(history, 100, 700);
    }
    const lookupMap = [
      ["Kronik Hastalık", profile.diseases], ["İlaç", profile.pharmacy_products],
      ["Alerji", profile.allergies], ["Ameliyat", profile.operations],
      ["Özel Durumlar", profile.special_conditions], ["Aşı", profile.vaccines],
      ["Cihaz (Vücuda Takılan)", profile.devices],
      ["Engellilik Durumu", profile.disabilities],
      ["Kan Transfüzyon", profile.transfusions], ["Terapi", profile.therapies],
    ];
    for (const [placeholder, items] of lookupMap) {
      filled += await fillProfileLookup(history, placeholder, items || []);
    }
    if (profile.marital_status && clickText(profile.marital_status, history)) filled += 1;
    if (profile.occupation && await chooseAutocomplete(byPlaceholder("Meslek", history), profile.occupation)) filled += 1;
    if (profile.education) {
      const education = byPlaceholder("Eğitim", history);
      education?.click();
      await sleep(80);
      if (clickText(profile.education)) filled += 1;
    }
    bridgeStatus("Özgeçmiş son kontrolleri yapılıyor");
    await waitForDomQuiet(history, 240, 1800);
    if (clickText("Görüldü", history)) filled += 1;
    await waitForDomQuiet(history, 180, 1200);
    filled += await fillFamilyHistory(profile);
    await waitForDomQuiet(document.body, 220, 1800);
    return filled;
  }

  function visibleSystemInquiryModal() {
    return [...document.querySelectorAll(".co-modal.co-document-popup")].find((modal) => {
      if (modal.offsetParent === null) return false;
      return [...modal.querySelectorAll(".hasta-detay-card__title")]
        .some((title) => textOf(title) === "Genel Sistem Sorgusu");
    }) || null;
  }

  function systemInquiryCards(modal) {
    return new Map([...modal.querySelectorAll(
      ".hasta-detay-card.document-panel-parameters-container",
    )].map((card) => [textOf(card.querySelector(".hasta-detay-card__title")), card]));
  }

  function checkboxLabel(input, root) {
    return [...root.querySelectorAll("label")]
      .find((label) => label.htmlFor === input.id) || null;
  }

  function readDraftSnapshot() {
    try { return JSON.parse(sessionStorage.getItem(LAST_DRAFT_SNAPSHOT_KEY) || "null"); }
    catch (_) { return null; }
  }

  function writeDraftSnapshot(value) {
    sessionStorage.setItem(LAST_DRAFT_SNAPSHOT_KEY, JSON.stringify(value));
  }

  function compactEntryParts(item) {
    const label = textOf(item.querySelector(".compact-item__header,.compact-item__label"));
    const explicitValue = textOf(item.querySelector(
      ".compact-item__value,.compact-item__content,.compact-item__description",
    ));
    const whole = textOf(item);
    const value = explicitValue || whole.slice(label.length).trim();
    if (!label || !value) return null;
    return {
      label,
      value,
      key: `${normalizedText(label)}|${normalizedText(value)}`,
      element: item,
    };
  }

  function compactEntries(cardTitle) {
    const card = cardByTitle(cardTitle);
    if (!card) return [];
    return [...card.querySelectorAll(".compact-item")]
      .map(compactEntryParts).filter(Boolean);
  }

  function diagnosisEntries() {
    const card = cardByTitle("Tanılar (ICD - 10)");
    if (!card) return [];
    return [...card.querySelectorAll("table tbody tr")].map((row) => {
      const code = textOf(row.querySelector("td"))
        .toUpperCase().match(/^[A-Z][0-9][0-9A-Z.\-]*/)?.[0] || "";
      return code ? {code, row} : null;
    }).filter(Boolean);
  }

  async function capturePersistedDraftBaseline() {
    const ready = await waitFor(() => cardByTitle("Özgeçmiş")
      && cardByTitle("Soygeçmiş") && cardByTitle("Tanılar (ICD - 10)"), 6000);
    if (!ready) throw new Error("Kalıcı COMED alanları temizleme için hazırlanamadı");
    return {
      captured: true,
      diagnoses: diagnosisEntries().map((entry) => entry.code),
      profile: compactEntries("Özgeçmiş").map((entry) => entry.key),
      family_history: compactEntries("Soygeçmiş").map((entry) => entry.key),
    };
  }

  function visibleRemovalDialog() {
    return [...document.querySelectorAll(
      ".co-modal,[role=dialog],.swal2-container,.modal,.co-message-box",
    )].filter((item) => item.getClientRects().length)
      .sort((a, b) => textOf(a).length - textOf(b).length)[0] || null;
  }

  async function confirmRemovalIfNeeded() {
    const dialog = await waitFor(visibleRemovalDialog, 650);
    if (!dialog) return;
    const confirm = [...dialog.querySelectorAll("button,[role=button]")]
      .find((button) => /^(sil|evet|tamam|onayla)$/i.test(textOf(button)) && !button.disabled);
    if (!confirm) throw new Error("COMED silme onayı bulunamadı");
    confirm.click();
    await waitFor(() => !dialog.isConnected || dialog.offsetParent === null, 5000);
  }

  async function removeDiagnosis(code) {
    const entry = diagnosisEntries().find((item) => item.code === code);
    if (!entry) return true;
    const trash = entry.row.querySelector('[data-test="co-button-icon-trash"]');
    if (!trash || trash.disabled) return false;
    trash.click();
    await confirmRemovalIfNeeded();
    return Boolean(await waitFor(
      () => !diagnosisEntries().some((item) => item.code === code), 7000,
    ));
  }

  function profilePlaceholder(label) {
    return ({
      "kullandığı ilaç": "İlaç",
      "diğer": "Özel Durumlar",
      "vücuda takılan cihaz": "Cihaz (Vücuda Takılan)",
    })[normalizedText(label)] || label;
  }

  async function turnOffProfileNoValue(entry) {
    const card = await ensureCardOpen("Özgeçmiş", "Meslek");
    if (!card) return false;
    const input = byPlaceholder(profilePlaceholder(entry.label), card);
    const row = input ? smallestFieldRow(input, card) : null;
    const noButton = [...(row?.querySelectorAll("button,label") || [])]
      .find((node) => textOf(node) === "Yok" && node.offsetParent !== null);
    if (!noButton || !/primary|active|selected/i.test(noButton.className)) return false;
    activateNode(noButton);
    return Boolean(await waitFor(
      () => !compactEntries("Özgeçmiş").some((item) => item.key === entry.key), 5000,
    ));
  }

  async function removeCompactEntry(cardTitle, key) {
    const entry = compactEntries(cardTitle).find((item) => item.key === key);
    if (!entry) return true;
    entry.element.click();
    const menu = await waitFor(() => [...document.querySelectorAll(
      ".co-menu__content,.co-popover,[role=menu]",
    )].filter((item) => item.getClientRects().length)
      .find((item) => normalizedText(textOf(item)).includes(normalizedText(entry.value))), 1600);
    const trash = menu?.querySelector('[data-test="co-button-icon-trash"]');
    if (trash && !trash.disabled) {
      trash.click();
      await confirmRemovalIfNeeded();
    } else {
      document.dispatchEvent(new KeyboardEvent("keydown", {
        key: "Escape", code: "Escape", bubbles: true,
      }));
      if (cardTitle !== "Özgeçmiş" || normalizedText(entry.value) !== "özellik yok"
        || !await turnOffProfileNoValue(entry)) return false;
    }
    return Boolean(await waitFor(
      () => !compactEntries(cardTitle).some((item) => item.key === key), 7000,
    ));
  }

  async function restorePersistedDraft(snapshot) {
    const baseline = snapshot?.persisted_baseline;
    if (!baseline?.captured) {
      throw new Error("Bu eski taslakta güvenli ICD/özgeçmiş geri alma bilgisi yok");
    }
    const diagnosisBaseline = new Set(baseline.diagnoses || []);
    const profileBaseline = new Set(baseline.profile || []);
    const familyBaseline = new Set(baseline.family_history || []);
    const addedDiagnoses = diagnosisEntries()
      .map((entry) => entry.code).filter((code) => !diagnosisBaseline.has(code));
    const addedProfile = compactEntries("Özgeçmiş")
      .map((entry) => entry.key).filter((key) => !profileBaseline.has(key));
    const addedFamily = compactEntries("Soygeçmiş")
      .map((entry) => entry.key).filter((key) => !familyBaseline.has(key));

    bridgeStatus("Klinot tanıları geri alınıyor");
    for (const code of addedDiagnoses) {
      if (!await removeDiagnosis(code)) throw new Error(`${code} tanısı geri alınamadı`);
    }
    bridgeStatus("Klinot özgeçmiş kayıtları geri alınıyor");
    for (const key of addedProfile) {
      if (!await removeCompactEntry("Özgeçmiş", key)) {
        throw new Error("Özgeçmiş kaydı geri alınamadı");
      }
    }
    bridgeStatus("Klinot soygeçmiş kayıtları geri alınıyor");
    for (const key of addedFamily) {
      if (!await removeCompactEntry("Soygeçmiş", key)) {
        throw new Error("Soygeçmiş kaydı geri alınamadı");
      }
    }
  }

  function captureSystemInquirySnapshot(cards) {
    const snapshot = readDraftSnapshot();
    if (!snapshot || snapshot.system_inquiry) return;
    snapshot.system_inquiry = Object.fromEntries([...cards.entries()].map(([group, card]) => [
      group,
      [...card.querySelectorAll('input[type="checkbox"]:checked')]
        .map((input) => textOf(checkboxLabel(input, card))).filter(Boolean),
    ]));
    writeDraftSnapshot(snapshot);
  }

  async function restoreSystemInquiry(snapshot) {
    if (!snapshot?.system_inquiry) return;
    let modal = visibleSystemInquiryModal();
    if (!modal) {
      const opener = await waitFor(systemInquiryOpener, 10000);
      if (!opener) throw new Error("Sistem Sorgulama düğmesi bulunamadı");
      opener.click();
    }
    modal = await waitFor(() => visibleSystemInquiryModal(), 10000);
    if (!modal) throw new Error("Sistem Sorgulama penceresi açılamadı");
    const cards = systemInquiryCards(modal);
    for (const [group, card] of cards.entries()) {
      const original = snapshot.system_inquiry[group] || [];
      for (const input of card.querySelectorAll('input[type="checkbox"]:checked')) input.click();
      const selections = original.length ? original : [SYSTEM_REVIEW_DEFAULTS[group]].filter(Boolean);
      selections.forEach((label) => setCheckboxByLabel(card, label, true));
    }
    const save = modal.querySelector('.document-fill__footer button[data-test="co-button-Kaydet"]');
    if (!save || save.disabled) throw new Error("Sistem Sorgulama Kaydet düğmesi bulunamadı");
    save.click();
    const closed = await waitFor(() => !modal.isConnected || modal.offsetParent === null, 12000);
    if (!closed) throw new Error("Sistem Sorgulama eski haline getirilemedi");
  }

  async function clearLastKlinotDraft() {
    if (busy) throw new Error("Aktarım sürerken taslak temizlenemez");
    const snapshot = readDraftSnapshot();
    const visitId = location.pathname.match(CARD_RE)?.[1];
    if (!snapshot || String(snapshot.visit_id) !== String(visitId)) {
      throw new Error("Bu kartta temizlenebilecek bir Klinot taslağı yok");
    }
    if (snapshot.native_post_applied) {
      throw new Error("Bu aktarım COMED POST ile kaydedildi; güvenli otomatik geri alma yapılamaz");
    }
    bridgeStatus("Klinot taslağı geri alınıyor");
    await restorePersistedDraft(snapshot);
    await restoreSystemInquiry(snapshot);
    sessionStorage.removeItem(LAST_DRAFT_SNAPSHOT_KEY);
    sessionStorage.removeItem(ACTIVE_TRANSFER_KEY);
    activeTransferId = null;
    bridgeStatus("Klinot taslağı tamamen temizlendi · kart yenileniyor", "ok");
    sessionStorage.setItem(SUPPRESS_RELOAD_PROMPT_KEY, "1");
    setTimeout(() => location.reload(), 450);
  }

  async function fillSystemInquiry(review = {}) {
    const expectedGroups = Object.keys(SYSTEM_REVIEW_DEFAULTS);
    const existingCard = cardByTitle("Sistem Sorgusu");
    const existingText = normalizedText(textOf(existingCard));
    const alreadyPresent = Boolean(existingCard) && expectedGroups.every((group) => {
      const requested = (Array.isArray(review?.[group]) ? review[group] : [review?.[group]])
        .filter(Boolean).map((value) => String(value));
      const selected = requested.length ? requested : [SYSTEM_REVIEW_DEFAULTS[group]];
      return existingText.includes(normalizedText(group))
        && selected.every((option) => existingText.includes(normalizedText(option)));
    });
    if (alreadyPresent) {
      return {
        filled: 0,
        saved: true,
        reused: true,
        fields: expectedGroups.flatMap((group) => {
          const requested = (Array.isArray(review?.[group]) ? review[group] : [review?.[group]])
            .filter(Boolean).map((value) => String(value));
          return (requested.length ? requested : [SYSTEM_REVIEW_DEFAULTS[group]])
            .map((option) => `review_of_system.${group}.${option}`);
        }),
        error: null,
      };
    }
    let modal = visibleSystemInquiryModal();
    if (!modal) {
      const opener = await waitFor(systemInquiryOpener, 30000);
      if (!opener) return {filled: 0, saved: false, fields: [], error: "Sistem Sorgulama düğmesi bulunamadı"};
      opener.click();
    }

    modal = await waitFor(() => {
      const candidate = visibleSystemInquiryModal();
      if (!candidate) return null;
      const cards = systemInquiryCards(candidate);
      const ready = expectedGroups.every((group) => {
        const card = cards.get(group);
        return card && card.querySelector('input[type="checkbox"]');
      });
      return ready ? candidate : null;
    }, 10000);
    if (!modal) {
      return {filled: 0, saved: false, fields: [], error: "Sistem Sorgulama alanları yüklenemedi"};
    }

    const fields = [];
    let filled = 0;
    const cards = systemInquiryCards(modal);
    captureSystemInquirySnapshot(cards);
    for (const group of expectedGroups) {
      const card = cards.get(group);
      if (!card) continue;
      const rawOptions = review?.[group];
      const requested = (Array.isArray(rawOptions) ? rawOptions : [rawOptions])
        .filter(Boolean).map((value) => String(value));
      const available = requested.filter((option) => checkboxByLabel(card, option)?.input);
      const selectedOptions = available.length ? available : [SYSTEM_REVIEW_DEFAULTS[group]];
      const selectedSet = new Set(selectedOptions.map((option) => option.toLocaleLowerCase("tr-TR")));

      for (const input of card.querySelectorAll('input[type="checkbox"]:checked')) {
        const label = checkboxLabel(input, card);
        if (label && !selectedSet.has(textOf(label).toLocaleLowerCase("tr-TR"))) input.click();
      }
      for (const option of selectedOptions) {
        if (setCheckboxByLabel(card, option, true)) {
          filled += 1;
          fields.push(`review_of_system.${group}.${option}`);
        }
      }
      if (!card.querySelector('input[type="checkbox"]:checked')) {
        const fallback = SYSTEM_REVIEW_DEFAULTS[group];
        if (setCheckboxByLabel(card, fallback, true)) {
          filled += 1;
          fields.push(`review_of_system.${group}.${fallback}`);
        }
      }
    }

    const missingGroups = expectedGroups.filter((group) => {
      const card = cards.get(group);
      return !card?.querySelector('input[type="checkbox"]:checked');
    });
    if (missingGroups.length) {
      return {
        filled, saved: false, fields, missingGroups,
        error: `Zorunlu Sistem Sorgulama grupları seçilemedi: ${missingGroups.join(", ")}`,
      };
    }

    const save = modal.querySelector(
      '.document-fill__footer button[data-test="co-button-Kaydet"]',
    );
    if (!save || save.offsetParent === null || save.disabled) {
      return {filled, saved: false, fields, error: "Sistem Sorgulama Kaydet düğmesi bulunamadı"};
    }
    save.click();
    const closed = await waitFor(() => !modal.isConnected || modal.offsetParent === null, 12000);
    return {
      filled,
      saved: Boolean(closed),
      fields,
      error: closed ? null : "Sistem Sorgulama kaydı tamamlanmadı; pencere açık kaldı",
    };
  }

  async function fillDiagnoses(diagnoses = []) {
    const card = cardByTitle("Tanılar (ICD - 10)");
    if (!card) return 0;
    let added = 0;
    for (const [index, diagnosis] of diagnoses.slice(0, 3).entries()) {
      const code = String(diagnosis?.code || "").trim().toUpperCase();
      if (!code || textOf(card.querySelector("table")).includes(code)) continue;
      const input = card.querySelector(".autocomplete__input input");
      if (!input) continue;
      setTypingValue(input, code);
      const result = await waitFor(() => [...document.querySelectorAll(".autocomplete__item")]
        .find((item) => item.offsetParent !== null && textOf(item).startsWith(`${code} |`)), 6500);
      if (!result) continue;
      result.click();
      await sleep(100);
      const diagnosisType = {
        differential: "Ayırıcı Tanı", definitive: "Kesin Tanı", preliminary: "Ön Tanı",
      }[diagnosis.diagnosis_type] || "Ön Tanı";
      clickText(diagnosisType, card);
      const side = {none: "Ayrım Yok", left: "Sol", right: "Sağ"}[diagnosis.side] || "Ayrım Yok";
      const sideInput = fieldGroupByLabel("Taraf Tipi", card)?.querySelector("input");
      sideInput?.click();
      await sleep(60);
      clickText(side);
      const mainDiagnosis = card.querySelector('input[type="checkbox"]');
      const shouldBePrimary = diagnosis.primary === true || (index === 0
        && !diagnoses.some((item) => item?.primary === true));
      if (mainDiagnosis && mainDiagnosis.checked !== shouldBePrimary) mainDiagnosis.click();
      const firstDate = byPlaceholder("İlk Tanı Tarihi", card);
      if (firstDate && !firstDate.disabled) setValue(firstDate, diagnosis.first_diagnosis_date);
      setValue(byPlaceholder("Açıklama", card), diagnosis.description);
      const addButton = [...card.querySelectorAll("button")]
        .find((button) => textOf(button) === "Ekle" && !button.disabled);
      if (!addButton) continue;
      addButton.click();
      added += 1;
      await sleep(180);
    }
    return added;
  }

  async function fillFormDraft(transfer, {skipDiagnoses = false} = {}) {
    const requestSpec = transfer.bundle.requests?.find((item) => item.section === "examination") || {};
    const fields = requestSpec.fields || {};
    const fallbackFields = new Set(transfer.bundle.fallback_fields || []);
    const fieldResults = [];
    let filled = 0;
    const record = (field, ok, detail = null) => {
      fieldResults.push({
        field,
        channel: "extension",
        status: ok ? "filled" : "not_found",
        source: fallbackFields.has(field) ? "operational_default" : "analysis",
        detail,
      });
      if (ok) filled += 1;
      bridgeFieldStatus(field, ok);
      return ok;
    };
    const write = (field, element, value) => {
      record(field, setValue(element, value));
    };

    const systemResult = await fillSystemInquiry(fields.review_of_system || {});
    systemResult.fields.forEach((field) => {
      fieldResults.push({
        field, channel: "extension", status: "filled",
        source: fallbackFields.has(field.split(".").slice(0, 2).join("."))
          ? "operational_default" : "analysis",
      });
      bridgeFieldStatus(field, true);
    });
    filled += systemResult.filled;
    fieldResults.push({
      field: "review_of_system.document",
      channel: "extension",
      status: systemResult.saved ? "saved" : "not_saved",
      source: "form",
      detail: systemResult.error || null,
    });
    if (!systemResult.saved) {
      return {
        filled,
        fieldResults,
        systemSaved: false,
        systemError: systemResult.error || "Sistem Sorgulama kaydedilemedi",
      };
    }

    const complaintCard = cardByTitle("Yakınması") || document;
    write("patient_complaint", byPlaceholder("Şikayeti", complaintCard), fields.patient_complaint);
    write("patient_story", byPlaceholder("Öykü", complaintCard), fields.patient_story);
    record("complaint_start_date", fillDuration(complaintCard, fields.complaint_start_date));
    write("review_of_system_simple", byPlaceholder("Sistem Sorgusu", cardByTitle("Sistem Sorgusu") || document), fields.review_of_system_simple);

    const examCard = cardByTitle("Fizik Muayene Bulguları") || document;
    write("exam_simple_textarea", byPlaceholder("Muayene Notu", examCard), fields.exam_simple_textarea);
    const vitals = fields.vitals || {};
    [["weight", "Kilo (kg)", vitals.weight], ["height", "Boy (cm)", vitals.height],
      ["temperature_v2", "Ateş", vitals.temperature_v2], ["pulse", "Nabız", vitals.pulse],
      ["pressure_systolic", "KB-S", vitals.pressure_systolic],
      ["pressure_diastolic", "KB-D", vitals.pressure_diastolic], ["spo2", "SPO2", vitals.spo2]]
      .forEach(([field, label, value]) => {
        if (value !== null && value !== undefined && value !== "") {
          write(`vitals.${field}`, inputByLabel(label, examCard), value);
        }
      });

    const planCard = cardByTitle("İzlem ve Plan") || document;
    const treatmentText = [fields.treatment_note_v2,
      fields.control_note ? `Kontrol notu: ${fields.control_note}` : null]
      .filter(Boolean).join("\n");
    write("treatment_note_v2", byPlaceholder("Tedavi Notu", planCard), treatmentText);

    bridgeStatus("Özgeçmiş ve soygeçmiş hazırlanıyor");
    const profileCount = await fillProfile(fields.profile || {});
    record("profile_and_family_history", profileCount > 0, `${profileCount} seçim`);
    const psychological = fields.psychological_status || {};
    if ((psychological.states || []).length || psychological.description) {
      record("psychological_status", fillPsychologicalStatus(psychological));
    }
    record("fall_risk", await fillFallRisk(fields.fall_risk));
    record("pain", await fillPain(fields.pain));
    if (!skipDiagnoses) {
      const diagnosisCount = await fillDiagnoses(fields.diagnoses || []);
      record("diagnoses", diagnosisCount > 0, `${diagnosisCount} tanı`);
    }
    record("treatment_plan_label", Boolean(fields.treatment_plan_label)
      && clickCardOption("İzlem ve Plan", fields.treatment_plan_label));
    if (fields.is_surgery_will_planned === true) {
      record("is_surgery_will_planned", clickFieldOption("Ameliyat Planlanacak mı?", "Evet", planCard));
    }
    if (fields.is_surgery_will_planned === false) {
      record("is_surgery_will_planned", clickFieldOption("Ameliyat Planlanacak mı?", "Hayır", planCard));
    }
    const controlSwitch = planCard.querySelector(
      '[data-test="co-switch-Kontrol Önerilme Durumu"] input[type="checkbox"], input[type="checkbox"]',
    );
    if (typeof fields.is_control_suggested === "boolean" && controlSwitch
      && controlSwitch.checked !== fields.is_control_suggested) {
      controlSwitch.click();
      record("is_control_suggested", true);
    }
    return {filled, fieldResults, systemSaved: systemResult.saved};
  }

  async function updateStatus(id, status, error = null, debug = null) {
    return request(`/api/v1/mobile/comed/bridge/transfers/${id}/status`, {
      method: "POST", body: JSON.stringify({status, error, debug}),
    });
  }

  function isMainClinicalSaveButton(button) {
    if (!button || !/^Kaydet(?: ve İmzala)?$/.test(textOf(button))) return false;
    return !button.closest(
      ".co-modal,.co-document-popup,[role=dialog],.document-fill__footer",
    );
  }

  async function postTransfer(transfer) {
    if (busy || !transfer?.bundle) return;
    busy = true;
    // Alt belgelerdeki (ör. Sistem Sorgulama) Kaydet düğmeleri ana muayene
    // kaydı değildir. Ana kayıt takibini ancak bütün alanlar hazır olduktan
    // sonra etkinleştir; böylece uygulama ve admin paneli erken tamamlanmaz.
    sessionStorage.removeItem(ACTIVE_TRANSFER_KEY);
    activeTransferId = null;
    bridgeStatus("COMED taslağı hazırlanıyor");
    const startedAt = new Date().toISOString();
    try {
      await updateStatus(transfer.id, "filling", null, {
        started_at: startedAt,
        stage: "starting",
      });
      if (!await waitForClinicalFormReady()) {
        throw new Error("COMED hasta kartı 45 saniye içinde hazır olmadı");
      }
      const persistedBaseline = await capturePersistedDraftBaseline();
      writeDraftSnapshot({
        visit_id: String(transfer.visit_id),
        transfer_id: transfer.id,
        created_at: new Date().toISOString(),
        system_inquiry: null,
        persisted_baseline: persistedBaseline,
        native_post_applied: false,
      });
      const nativeRequests = transfer.bundle.native_requests || [];
      const hasMainPost = nativeRequests.some(
        (item) => item.endpoint === "forms/document/saveDocumentProcesses",
      );
      const hasDiagnosisPost = nativeRequests.some(
        (item) => item.endpoint === "medical/treatment/savevisitdiagnoses",
      );
      let postResults = [];
      let postError = null;
      if (hasMainPost) {
        bridgeStatus("Doğrulanmış COMED POST'ları gönderiliyor");
        try {
          postResults = await executeNativePosts(transfer.visit_id, nativeRequests);
          const snapshot = readDraftSnapshot();
          if (snapshot) {
            snapshot.native_post_applied = postResults.length > 0;
            writeDraftSnapshot(snapshot);
          }
        } catch (error) {
          postError = error;
          bridgeStatus("POST tamamlanamadı · alanlar eklentiyle dolduruluyor");
        }
      } else {
        bridgeStatus("POST şablonu yok · alanlar eklentiyle dolduruluyor");
      }

      const diagnosisPosted = !postError && hasDiagnosisPost && postResults.length > 0;
      const formResult = await fillFormDraft(transfer, {skipDiagnoses: diagnosisPosted});
      if (!formResult.systemSaved) {
        const systemError = new Error(formResult.systemError || "Sistem Sorgulama kaydedilemedi");
        systemError.klinotDebug = {
          stage: "system_inquiry",
          extension: {
            filled_count: formResult.filled,
            system_inquiry_saved: false,
            fields: formResult.fieldResults,
          },
        };
        throw systemError;
      }
      if (!postResults.length && !formResult.filled) {
        throw postError || new Error("COMED form alanları bulunamadı; kartı yenileyip tekrar deneyin");
      }
      bridgeStatus("Son alanlar doğrulanıyor");
      await waitForDomQuiet(document.body, 400, 3500);
      const unresolved = formResult.fieldResults.filter(
        (item) => !["filled", "saved", "reused"].includes(item.status),
      );
      const mode = postResults.length
        ? "POST + form tamamlama"
        : postError ? "POST fallback + eklenti form doldurma" : "eklenti form doldurma";
      const note = `${mode}; ${formResult.filled} alan işlendi${unresolved.length
        ? `, ${unresolved.length} alan doktor kontrolüne bırakıldı`
        : " ve tarayıcı güncellemeleri tamamlandı"}. Doktor Kaydet/İmzala kontrolünü yapmalıdır.`;
      const debug = {
        started_at: startedAt,
        finished_at: new Date().toISOString(),
        mode,
        post: {
          attempted: hasMainPost,
          error: postError?.message || null,
          requests: postResults,
          fields: postResults.flatMap((item) => item.patched_fields || []),
        },
        extension: {
          filled_count: formResult.filled,
          system_inquiry_saved: formResult.systemSaved,
          fields: formResult.fieldResults,
          unresolved_count: unresolved.length,
        },
        fallback_fields: transfer.bundle.fallback_fields || [],
        remaining_required: transfer.bundle.missing_required || [],
        auto_sign: false,
      };
      await updateStatus(transfer.id, "ready_for_review", note, debug);
      sessionStorage.setItem(ACTIVE_TRANSFER_KEY, String(transfer.id));
      activeTransferId = transfer.id;
      bridgeStatus("Aktarım bitti · Genel doktor kontrolü gerekli", "ok");
    } catch (error) {
      await updateStatus(transfer.id, "failed", error.message, {
        started_at: startedAt,
        finished_at: new Date().toISOString(),
        stage: error.klinotDebug?.stage || "failed",
        message: error.message,
        auto_sign: false,
        ...(error.klinotDebug || {}),
      }).catch(() => {});
      sessionStorage.removeItem(ACTIVE_TRANSFER_KEY);
      activeTransferId = null;
      bridgeStatus(`Aktarım hatası: ${error.message}`, "bad");
    } finally {
      busy = false;
    }
  }

  async function pollTransfer() {
    const match = location.pathname.match(CARD_RE);
    if (!match || busy) return;
    try {
      const payload = await request(`/api/v1/mobile/comed/bridge/transfers?visit_id=${encodeURIComponent(match[1])}`);
      if (payload.items?.length) await postTransfer(payload.items[0]);
    } catch (error) {
      if (!/bağlı değil/i.test(error.message)) bridgeStatus(error.message, "bad");
    }
  }

  async function monitorRoute() {
    if (routeBusy) return;
    routeBusy = true;
    try {
      const path = location.pathname;
      const routeChanged = path !== lastPath;
      if (routeChanged) {
        lastPath = path;
        openingVisitId = null;
        lastIdentityFingerprint = "";
      }
      if (WORKLIST_RE.test(path)) {
        // Tarih araligi her turda (5 sn) denenir; basarili olunca kendini
        // kapatir. Esitleme 60 saniyede bir yapildigi icin burada beklemek
        // ilk denemenin basarisiz olmasi halinde cok gec kalirdi.
        const widened = !dateRangeApplied;
        await ensureWorklistDateRange();
        if (routeChanged || (widened && dateRangeApplied)
          || Date.now() - lastWorklistSyncAt >= 60000) {
          await syncWorklist();
          lastWorklistSyncAt = Date.now();
        }
        await openPendingTransferFromWorklist();
      } else if (CARD_RE.test(path)) {
        if (routeChanged || Date.now() - lastCardSyncAt >= 15000) {
          await syncCurrentCard();
          lastCardSyncAt = Date.now();
        }
        await pollTransfer();
      }
    } catch (error) {
      if (!/bağlı değil/i.test(error.message)) bridgeStatus(error.message, "bad");
    } finally {
      routeBusy = false;
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (button && textOf(button) === "Göreve Git") {
      const selected = parseRow(button.closest("tr,[role=row]"));
      if (selected) sessionStorage.setItem(SELECTED_PATIENT_KEY, JSON.stringify(selected));
    }
    if (!activeTransferId || !isMainClinicalSaveButton(button)) return;
    const id = activeTransferId;
    setTimeout(() => {
      const success = /Kayıt başarılı/i.test(document.body.innerText);
      if (success) {
        updateStatus(id, "completed").catch(() => {});
        bridgeStatus("COMED kaydı tamamlandı", "ok");
        sessionStorage.removeItem(ACTIVE_TRANSFER_KEY);
        sessionStorage.removeItem(LAST_DRAFT_SNAPSHOT_KEY);
        activeTransferId = null;
      }
    }, 1800);
  }, true);

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "klinot-clear-last-transfer") return false;
    clearLastKlinotDraft()
      .then(() => sendResponse({ok: true}))
      .catch((error) => sendResponse({ok: false, error: error.message}));
    return true;
  });

  const patientIdentityObserver = new MutationObserver(schedulePatientIdentitySync);
  patientIdentityObserver.observe(document.documentElement, {
    childList: true, subtree: true, characterData: true,
  });

  setTimeout(monitorRoute, 1500);
  setInterval(monitorRoute, 5000);
})();
