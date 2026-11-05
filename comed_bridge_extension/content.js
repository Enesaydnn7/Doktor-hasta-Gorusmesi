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
  let identityPanelTried = false;
  let identitySyncTimer = null;
  let openingVisitId = null;
  let traceEnabled = true;
  let traceFlushTimer = null;
  const traceQueue = [];

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
  });

  const BRIDGE_LOG_KEY = "klinot_comed_bridge_log_v1";
  const BRIDGE_WIDGET_KEY = "klinot_comed_bridge_widget_v2";

  /* ---- doldurma hizi ----
     Deger buyudukce doldurma hizlanir; 1 = varsayilan. Eklenti penceresindeki
     kaydiraçtan degistirilir, chrome.storage ile buraya anlik yansir.

     DIKKAT (onceki surumdeki hata): yalnizca sleep() olceklendiginde ayar
     hissedilmiyordu. Olculdugunde sleep'lerin toplami ~2.7 sn, buna karsilik
     "DOM sakinlesene kadar bekle" (waitForDomQuiet) beklemeleri 1.5-12.7 sn
     tutuyordu. Yani surenin ancak ~%15'i olcekleniyor, 2.5x bile fark
     yaratmiyordu. Simdi her iki bekleme turu de olcekleniyor.

     Olceklenmeyen tek sey waitFor()'un ZAMAN ASIMI suresi: o bir guvenlik
     siniri, kisaltmak alanin hazir olmadan islenmesine yol acar. */
  const FILL_SPEEDS = [
    {value: 0.5, label: "0.5×", title: "Çok yavaş · adımları rahat takip et"},
    {value: 0.75, label: "0.75×", title: "Yavaş"},
    {value: 1, label: "1×", title: "Normal (varsayılan)"},
    {value: 1.5, label: "1.5×", title: "Hızlı"},
    {value: 2.5, label: "2.5×", title: "Çok hızlı"},
  ];
  const DEFAULT_FILL_SPEED = 1;
  let fillSpeed = DEFAULT_FILL_SPEED;

  function normalizeFillSpeed(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return DEFAULT_FILL_SPEED;
    return FILL_SPEEDS.some((item) => item.value === number) ? number : DEFAULT_FILL_SPEED;
  }

  /* Bekleme suresini o anki hiza gore olcekle. Alt sinir, en hizli ayarda
     bile COMED'in olayi isleyebilmesi icindir. */
  function scaled(ms, floor) {
    return Math.max(floor, Math.round(ms / (fillSpeed || 1)));
  }

  function applyFillSpeed(value) {
    fillSpeed = normalizeFillSpeed(value);
  }

  chrome.storage.local.get(["fillSpeed"], (value) => applyFillSpeed(value.fillSpeed));
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local" || !changes.fillSpeed) return;
    const onceki = fillSpeed;
    applyFillSpeed(changes.fillSpeed.newValue);
    if (fillSpeed === onceki) return;
    // Doktor kaydiraci oynattiginda degisikligin ULASTIGINI gorsun; aksi
    // halde "ayar tutuyor mu?" belirsizligi kaliyor.
    const etiket = FILL_SPEEDS.find((item) => item.value === fillSpeed)?.label || `${fillSpeed}×`;
    if (document.getElementById("klinot-comed-bridge")) {
      bridgeStatus(`Doldurma hızı ${etiket}`, "ok");
    }
  });

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
    // Hasta adi YALNIZCA hasta kartinda okunur. Is listesi sayfasinda sayfa
    // govdesinin basi arac cubugudur ("Is Listesi Havuz Is Listesi Randevular
    // ...") ve bu metin hasta adi sanilip seride basiliyordu.
    const patientName = match
      ? cleanPatientName(
        body.match(/^(.{3,80}?)(?=\s+(?:K|E|\d{1,3}\s*y|Hasta\s*No|V-))/i)?.[1],
      )
      : "";
    return [patientName, patientNo && `Hasta ${patientNo}`, protocol]
      .filter(Boolean).join(" · ");
  }

  function bridgeFieldLabel(field) {
    const labels = {
      patient_complaint: "Hasta yakınması", patient_story: "Öykü",
      complaint_start_date: "Başlangıç tarihi", review_of_system_simple: "Sistem sorgusu özeti",
      exam_simple_textarea: "Muayene notu", treatment_note_v2: "İzlem ve tedavi planı",
      profile_and_family_history: "Özgeçmiş ve soygeçmiş", family_history: "Soygeçmiş",
      requested_services: "Hizmet istemleri (EKG, EKO…)",
      requested_drugs: "İlaç istemleri",
      psychological_status: "Psikolojik durum",
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
      /* TEK balon: hem fare uzerine gelince hem islem sirasinda ayni balon yana
         acilir ve o anki adimi gosterir. Ayri bir durum seridi yok. */
      #klinot-comed-bridge [data-klinot-log-orb]:hover,
      #klinot-comed-bridge [data-klinot-log-orb]:focus-visible,
      #klinot-comed-bridge [data-klinot-log-orb][data-live="1"]{width:max-content;max-width:min(360px,calc(100vw - 60px));border-radius:28px}
      #klinot-comed-bridge [data-klinot-log-orb][aria-expanded="true"]{width:56px;max-width:56px}
      #klinot-comed-bridge [data-klinot-log-mark]{width:56px;min-width:56px;height:56px;display:grid;place-items:center;font:800 20px system-ui;letter-spacing:.5px}
      #klinot-comed-bridge [data-klinot-log-label]{display:flex;flex-direction:column;align-items:flex-start;padding-right:18px;min-width:0;white-space:nowrap;opacity:0;transform:translateX(-10px);transition:opacity .2s ease .04s,transform .26s cubic-bezier(.22,1,.36,1) .04s}
      #klinot-comed-bridge [data-klinot-log-label] b{max-width:290px;overflow:hidden;text-overflow:ellipsis;font:800 13px system-ui;line-height:1.2}
      #klinot-comed-bridge [data-klinot-log-label] i{max-width:290px;overflow:hidden;text-overflow:ellipsis;font:600 11px system-ui;font-style:normal;opacity:.82;line-height:1.3}
      #klinot-comed-bridge [data-klinot-log-orb]:hover [data-klinot-log-label],
      #klinot-comed-bridge [data-klinot-log-orb]:focus-visible [data-klinot-log-label],
      #klinot-comed-bridge [data-klinot-log-orb][data-live="1"] [data-klinot-log-label]{opacity:1;transform:none}
      #klinot-comed-bridge [data-klinot-log-orb][aria-expanded="true"] [data-klinot-log-label]{opacity:0;transform:translateX(-10px)}
      #klinot-comed-bridge [data-klinot-log-count]{position:absolute;right:-3px;top:-5px;display:grid;place-items:center;min-width:22px;height:22px;padding:0 6px;border:2px solid #fff;border-radius:99px;background:#3158c8;color:#fff;font:800 10px system-ui;pointer-events:none;box-shadow:0 3px 9px #0b253355}
      @media(max-width:620px){#klinot-comed-bridge [data-klinot-log-label]{max-width:180px}}
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
    </style><div data-klinot-log-shell><section data-klinot-log-panel aria-hidden="true"><div data-klinot-log-header><span><strong style="display:block;font-size:13px">İşlem günlüğü</strong><small data-klinot-log-panel-count style="color:#60777d;font-weight:600"></small></span><button data-klinot-log-close type="button" aria-label="İşlem günlüğünü aşağı indir" title="Aşağı indir"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button></div><div data-klinot-log-summary><strong data-klinot-log-title>Klinot hazır</strong><small data-klinot-log-context style="display:block;margin-top:3px;opacity:.82;font-weight:500;overflow-wrap:anywhere"></small></div><div data-klinot-log-list></div></section><button data-klinot-log-orb type="button" data-live="0" aria-expanded="false" aria-label="Klinot işlem günlüğünü aç"><span data-klinot-log-mark aria-hidden="true">K</span><span data-klinot-log-label aria-live="polite"><b data-klinot-caption-text>Klinot</b><i data-klinot-caption-sub>İşlem günlüğü</i></span></button><span data-klinot-log-count>0</span></div>`;
    const shell = box.querySelector("[data-klinot-log-shell]");
    const orb = box.querySelector("[data-klinot-log-orb]");
    const panel = box.querySelector("[data-klinot-log-panel]");
    const setOpen = (open) => {
      panel.setAttribute("aria-hidden", String(!open));
      orb.setAttribute("aria-expanded", String(open));
      orb.setAttribute("aria-label", open ? "Klinot işlem günlüğünü kapat" : "Klinot işlem günlüğünü aç");
      // Gunluk acikken canli serit panelin uzerine binmesin.
      // Gunluk acikken balon kucuk kalsin.
      if (open) orb.dataset.live = "0";
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
    const orb = box.querySelector("[data-klinot-log-orb]");
    if (!orb) return;
    const panelOpen = box.querySelector("[data-klinot-log-panel]")
      ?.getAttribute("aria-hidden") === "false";
    const isFinal = String(text).startsWith(BRIDGE_FINAL_TEXT);
    // Uzun baglam metni tek satirda kalmali.
    const context = bridgeContext() || "COMED aktarımı";
    // Son mesajin sonunda "· 19 sn · 1× hız" olabilir; balonda da gorunsun
    // ki doktor hiz ayarinin etkisini rakamla karsilastirabilsin.
    const olcum = isFinal ? String(text).slice(BRIDGE_FINAL_TEXT.length) : "";
    orb.querySelector("[data-klinot-caption-text]").textContent =
      isFinal ? `Aktarım bitti${olcum}` : text;
    orb.querySelector("[data-klinot-caption-sub]").textContent = isFinal
      ? "Lütfen kontrol edip Kaydet ve İmzala"
      : (context.length > 54 ? `${context.slice(0, 53)}…` : context);
    orb.dataset.live = panelOpen ? "0" : "1";

    clearTimeout(captionTimer);
    // Son mesaj doktorun imza adimidir; balon acik kalir.
    if (!isFinal) {
      captionTimer = setTimeout(() => { orb.dataset.live = "0"; }, 6000);
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

  function parsePatientIdentity(doc = document) {
    const identityRoots = [...(doc?.querySelectorAll('[role="dialog"],.co-popover,.co-drawer,.patient-info') || [])];
    // COMED, hasta kimlik alanlar\u0131n\u0131 yaln\u0131zca "Hasta Bilgileri" a\u00e7\u0131l\u0131r panelinde
    // g\u00f6sterir. ``innerText`` sadece g\u00f6r\u00fcnen metni verdi\u011fi i\u00e7in panel kapal\u0131yken
    // TCKN ve do\u011fum tarihi okunam\u0131yor, hasta giri\u015fi de e\u015fle\u015femiyordu. Bu y\u00fczden
    // g\u00f6r\u00fcn\u00fcr metne ek olarak gizli d\u00fc\u011f\u00fcmleri de kapsayan ``textContent`` taran\u0131r.
    const raw = [
      identityRoots.map(textOf).join(" "),
      textOf(doc?.body),
      identityRoots.map(deepTextOf).join(" "),
      deepTextOf(doc?.body),
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

  /** Ziyaret kimliginden COMED hasta kartinin adresini uret. */
  function cardUrlForVisit(visitId) {
    const id = String(visitId || "").trim();
    if (!/^\d+$/.test(id)) return "";
    return `${location.origin}/tr-tr/medical/hasta-tibbi-karti/${id}/patient-clinical-card/`;
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
    // COMED is listesi satiri dogum tarihini gosteriyor ("28yıl 22.10.1997").
    // TCKN burada YOK -- o yalnizca hasta kartindaki "Hasta Bilgileri"
    // panelinde. Yine de dogum tarihini simdiden gonderiyoruz; hasta
    // eslesmesi icin gereken ikinci parca kart acilinca tamamlanir.
    const birthDate = (patientCell?.innerText || "")
      .match(/\b(\d{2})[.\/-](\d{2})[.\/-](\d{4})\b/);
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
      // Is listesi satirinda kartin adresi YOK. Eskiden bos biraktigimiz icin
      // doktor "COMED'e aktar" dediginde panel bos adres gonderiyor, kart
      // acilamiyor ve bos bir sekme kaliyordu. Adres yalnizca doktor o karti
      // bir kez actiginda (syncCurrentCard) doluyordu. Oysa COMED kart
      // adresi visit_id'den uretilebiliyor: klinik kart kimligi henuz
      // atanmamis kartlar da /patient-clinical-card/ ile acilabiliyor.
      clinical_card_url: card.url || cardUrlForVisit(visitId),
      ...(birthDate ? {birth_date: `${birthDate[1]}.${birthDate[2]}.${birthDate[3]}`} : {}),
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

  /* COMED, TCKN ve dogum tarihini yalnizca "Hasta Bilgileri" panelinde tutar ve
     bu panel ACILANA KADAR DOM'a hic basilmaz (lazy render). Hasta mobil girisi
     bu iki alanin ozetine dayandigi icin, kimlik yoksa kopru paneli bir kez
     kendisi acar, okur ve hemen kapatir. Canli COMED test ortaminda dogrulandi:
       acici : button[data-test="co-button-icon-patient-profile"]
       kapatici: button[data-test="co-button-icon-close"]  (Escape calismiyor)
     Bayrak kart degisince sifirlanir. */
  async function ensurePatientIdentityPanel() {
    if (identityPanelTried || !CARD_RE.test(location.pathname)) return null;
    const current = parsePatientIdentity();
    if (current.tckn && current.birth_date) return current;
    identityPanelTried = true;
    const opener = document.querySelector('[data-test="co-button-icon-patient-profile"]');
    if (!opener) return null;
    let identity = null;
    try {
      activateNode(opener);
      // Kimlik DOM'da YALNIZCA panel acikken bulunur; okunan deger burada
      // yakalanip DONDURULUR. Panel kapandiktan sonra tekrar okumak bos doner.
      identity = await waitFor(() => {
        const value = parsePatientIdentity();
        return value.tckn && value.birth_date ? value : null;
      }, 5000);
    } finally {
      const close = document.querySelector('[data-test="co-button-icon-close"]');
      if (close) {
        activateNode(close);
        await sleep(260);
      }
    }
    return identity;
  }

  async function syncCurrentCard() {
    const match = location.pathname.match(CARD_RE);
    if (!match) return;
    // Panel kapandiktan sonra kimlik DOM'dan silindigi icin DONEN deger
    // kullanilir; dogrudan tekrar okumak bos sonuc verirdi.
    const panelIdentity = await ensurePatientIdentityPanel();
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
      ...(panelIdentity || parsePatientIdentity()),
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

  // Tum alanlar acik hasta kartinda form doldurarak hazirlanir. Koprunun
  // kendisi asla Kaydet veya Kaydet ve Imzala dugmesine basmaz; son kontrol,
  // kayit ve imza doktordadir.
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

  /* COMED'in bazi dugmeleri salt .click() ile tepki vermiyor; gercek fare
     dizisi bekliyorlar (ornegin hizmet istem ekranindaki "Ekle" ve
     "Uygulayan" alani). Canli ortamda olculdu. */
  function pressNode(node) {
    if (!node) return false;
    const rect = node.getBoundingClientRect();
    const init = {
      bubbles: true, cancelable: true, view: window,
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2,
      button: 0, buttons: 1,
    };
    try {
      // Bazi COMED bilesenleri once hover olaylarini bekliyor; eksik dizi
      // gonderildiginde tiklama sessizce yutuluyordu.
      for (const type of ["pointerover", "mouseover", "pointermove", "mousemove",
        "pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
        const Ctor = type.startsWith("pointer") ? PointerEvent : MouseEvent;
        node.dispatchEvent(new Ctor(type, init));
      }
      return true;
    } catch (_) {
      node.click();
      return true;
    }
  }

  /* COMED'in acilir alanlarinda tiklama dinleyicisi alanin KENDISINDE degil,
     icindeki ok ikonunda. Canli ortamda olculdu: alanin kendisine, cocuklarina
     ve atalarina gonderilen tiklama panel acmiyor, yalnizca ikon aciyor. */
  function pressField(root) {
    if (!root) return false;
    const icon = root.querySelector('svg,i,[class*="icon"],[class*="arrow"]');
    return pressNode(icon || root);
  }

  /* Sayfada ayni data-test'li birden cok dugme olabiliyor: tani kartindaki
     "Ekle" ile hizmet istem penceresindeki "Ekle" ayni isimde. Pencereninki
     "Vazgeç" ile ayni hizada durur; en yakin olani seciyoruz. Eskiden
     querySelector ilk bulduğunu (tani kartindakini) aliyor ve o hep pasif
     oldugu icin istem hic eklenemiyordu. */
  function dialogButton(testName) {
    const cancel = [...document.querySelectorAll('[data-test="co-button-Vazgeç"]')]
      .find((item) => item.offsetParent !== null);
    const candidates = [...document.querySelectorAll(`[data-test="${testName}"]`)]
      .filter((item) => item.offsetParent !== null);
    if (!candidates.length) return null;
    if (!cancel) return candidates[candidates.length - 1];
    const cancelTop = cancel.getBoundingClientRect().top;
    return candidates.sort((a, b) =>
      Math.abs(a.getBoundingClientRect().top - cancelTop)
      - Math.abs(b.getBoundingClientRect().top - cancelTop))[0];
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

  /* COMED etiketleri bazen "Özellik Yok", bazen "Özellik yok" yazilir.
     Tam eslesme arayan clickText bu yuzden kaciriyordu. */
  function clickTextLoose(labels, root = document) {
    const wanted = labels.map((item) => item.toLocaleLowerCase("tr-TR").replace(/\s+/g, " ").trim());
    const nodes = [...root.querySelectorAll(
      "button,label,[role=radio],[role=checkbox],.toggle-button__item,.autocomplete__item,span",
    )].filter((element) => element.offsetParent !== null);
    for (const label of wanted) {
      const node = nodes.find(
        (element) => textOf(element).toLocaleLowerCase("tr-TR").replace(/\s+/g, " ").trim() === label,
      );
      if (activateNode(node)) return true;
    }
    return false;
  }

  /* Zorunlu kartlari (Soygecmis, Dusme Riski) bos birakmamak icin:
     karti ac, secenek gorunene kadar bekle, sonra sirayla dene.
     Bir denemede olmazsa karti yeniden acip tekrar dener. */
  async function markCardOption(cardTitle, labels, tries = 3) {
    for (let attempt = 0; attempt < tries; attempt += 1) {
      const card = await ensureCardOpen(cardTitle);
      if (card) {
        await waitFor(
          () => [...card.querySelectorAll("button,label,[role=radio],.toggle-button__item")]
            .some((element) => element.offsetParent !== null),
          1200,
        );
        if (clickTextLoose(labels, card)) return true;
      }
      // Kart bulunamadiysa sayfa genelinde de ara; bazi alanlar modal icinde acilir.
      if (clickTextLoose(labels)) return true;
      await sleep(260);
    }
    return false;
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

  function rawSleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /* Adimlar arasi bekleme.

     Hiz ORTADA degistirilebilsin diye bekleme tek parca degil dilim dilim
     yapilir: her dilimde fillSpeed yeniden okunur. Tek parca olsaydi, doktor
     doldurma surerken kaydiraci oynattiginda o an suren bekleme eski hizla
     bitecek ve "ayar tutmuyor" hissi verecekti. */
  async function sleep(ms) {
    let kalan = ms;                       // olceklenmemis "is" miktari
    while (kalan > 0) {
      const hiz = fillSpeed || 1;
      // Gercek zamanda ~60 ms'lik dilim; hiz arttikca daha cok is tuketir.
      const dilim = Math.min(kalan, 60 * hiz);
      const basla = performance.now();
      await rawSleep(Math.max(5, Math.round(dilim / hiz)));
      // setTimeout her zaman istenenden GEC uyanir. Planlanani degil gercekte
      // gecen sureyi dusersek bu gecikme birikmez; aksi halde dilimleme
      // toplam sureyi ~%25 uzatiyordu.
      kalan -= (performance.now() - basla) * hiz;
    }
  }

  async function waitFor(getter, timeoutMs = 4500) {
    // Zaman asimi BILEREK olceklenmez: bu bir guvenlik siniri. Yalnizca
    // yoklama sikligi hizlanir, boylece eleman hazir olur olmaz devam edilir.
    const deadline = Date.now() + timeoutMs;
    const poll = scaled(120, 40);
    while (Date.now() < deadline) {
      const value = getter();
      if (value) return value;
      await rawSleep(poll);
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

  /* Doldurma suresinin BUYUK bolumu burada geciyor (olculen: 1.5-12.7 sn,
     sleep'lerin toplami yalnizca ~2.7 sn). Hiz ayarinin hissedilmesi icin
     hem sessizlik esigi hem ust sinir olceklenir.

     Esikler sabit setTimeout yerine 30 ms'lik periyodik kontrolle olculur;
     boylece bekleme SURERKEN hiz degisirse yeni deger hemen gecerli olur.
     Sabit timer'da 3,5 saniyelik bir bekleme eski hizla biteceginden doktor
     kaydiraci oynattiginda hicbir sey degismemis gibi gorunuyordu. */
  function waitForDomQuiet(root = document.body, quietMs = 220, timeoutMs = 2200) {
    if (!root) return Promise.resolve();
    return new Promise((resolve) => {
      const basladi = Date.now();
      let sonDegisiklik = basladi;
      const observer = new MutationObserver(() => { sonDegisiklik = Date.now(); });
      observer.observe(root, {subtree: true, childList: true, attributes: true, characterData: true});
      const timer = setInterval(() => {
        const sessizlik = scaled(quietMs, 40);
        const ustSinir = Math.max(scaled(timeoutMs, 400), sessizlik + 100);
        const simdi = Date.now();
        if (simdi - sonDegisiklik >= sessizlik || simdi - basladi >= ustSinir) {
          clearInterval(timer);
          observer.disconnect();
          resolve();
        }
      }, 30);
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

  /* CANLI OLCUM (5 Kasim): Agri niteligi ve psikolojik durum aç/kapa
     dugmesi. Tekrar aktarimda secili "Bastırıcı"ya yeniden basilinca secim
     kalkiyordu. Zaten seciliyse dokunulmaz. */
  /* CANLI (5 Kasim): tam aktarimda "Bastirici" tiklaniyor ama sonunda secili
     kalmiyordu; tek basina tiklayinca tutuyor. Kisa bekleyip kontrol edilir,
     secili degilse bir kez daha basilir. Aktarimin sonunda da tekrar bakilir. */
  async function ensureTogglesOn(root, texts = []) {
    for (const text of texts || []) {
      await sleep(150);
      const item = [...(root || document).querySelectorAll(".toggle-button__item")]
        .find((element) => textOf(element) === text && element.offsetParent !== null);
      if (item && !item.classList.contains("active")) activateNode(item);
    }
  }

  function clickToggleOn(text, root = document) {
    const item = [...root.querySelectorAll(".toggle-button__item")]
      .find((element) => textOf(element) === text && element.offsetParent !== null);
    if (item?.classList.contains("active")) return true;
    return item ? activateNode(item) : clickText(text, root);
  }

  /* CANLI OLCUM (5 Kasim): Ozgecmis katalogunda karsiligi olmayan kayit
     (test ortaminda isitme cihazi, fizik tedavi, tuzsuz diyet; ilaclar yalniz
     marka adiyla) sessizce kayboluyordu. Bulunamayanlar Öykü'nün sonuna
     yazilir ki doktor gorsun. */
  const PROFILE_MISSING_LABELS = {
    "İlaç": "Kullandığı ilaç", "Ameliyat": "Ameliyat", "Özel Durumlar": "Özel durum",
    "Aşı": "Aşı", "Cihaz (Vücuda Takılan)": "Cihaz", "Engellilik Durumu": "Engellilik",
    "Kan Transfüzyon": "Kan nakli", "Terapi": "Terapi", "Kronik Hastalık": "Kronik hastalık",
    "Alerji": "Alerji",
  };

  async function fillProfileLookup(history, placeholder, items = [], missing = []) {
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
      // Ilk kelimeyle yeniden arama YOK: CANLI "Kan Nakli" -> "Kan" -> "Tam Kan"
      // seciyordu; hasta urun soylemedi, uydurma kayit olur.
      if (!input || !await chooseAutocomplete(input, name)) {
        if (input) setTypingValue(input, "");
        missing.push(`${PROFILE_MISSING_LABELS[placeholder] || placeholder}: ${[name, description].filter(Boolean).join(" ")}`);
        continue;
      }
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
    if (exists !== true) return markCardOption("Düşme Riski", ["Yok"]);
    if (typeof value !== "object") return markCardOption("Düşme Riski", ["Yok"]);
    const normalized = {...value};
    if (!["65_plus", "under_65"].includes(normalized.age_group)) {
      // CANLI: baslikta "E29yıl22.10.1997" bitisik; \b ile yas hic okunmuyor,
      // dusme riski hep "Yok"a dusuyordu.
      const age = Number(textOf(document.body).match(/(?:^|\D)(\d{1,3})\s*y[ıi]l/i)?.[1]);
      if (age > 0) normalized.age_group = age >= 65 ? "65_plus" : "under_65";
    }
    const detailKeys = ["history", "medications", "addiction", "gait_balance_disorder",
      "vision_disorder", "oriented", "general_health_normal"];
    detailKeys.forEach((key) => {
      if (typeof normalized[key] !== "boolean") normalized[key] = false;
    });
    // Detayli akis tutmazsa alan bos kalmasin; "Yok" ile kart tamamlanir.
    if (!["65_plus", "under_65"].includes(normalized.age_group)) {
      return markCardOption("Düşme Riski", ["Yok"]);
    }
    if (!await markCardOption("Düşme Riski", ["Var"], 2)) {
      return markCardOption("Düşme Riski", ["Yok"]);
    }
    const popover = await waitFor(() => [...document.querySelectorAll(
      ".co-menu__content .co-popover,.co-menu__content,.co-popover.bottom,.co-popover",
    )].find((item) => item.offsetParent !== null && textOf(item).includes("Düşme Hikayesi")));
    if (!popover) return markCardOption("Düşme Riski", ["Yok"]);
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
    (pain.qualities || []).forEach((quality) => clickToggleOn(quality, card));
    if (pain.rhythm) clickToggleOn(pain.rhythm, card);
    await ensureTogglesOn(card, pain.qualities);
    // COMED'in Ağrı Başlangıcı bileşeni yalnızca gün cinsini kabul ediyor.
    // Saat bilgisini "2 gün" diye yanlış yazmak yerine ana yakınma süresinde koru.
    if (pain.start_date?.unit === "day") {
      fillDuration(card, pain.start_date, "Ağrı Başlangıcı");
    }
    return scoreFilled;
  }

  /* Soygecmis COMED'de zorunlu. Veri olsun olmasin kart asla bos kalmamali:
     once "Ozellik Yok", olmazsa "Gorulduveya benzeri etiketler denenir. */
  const FAMILY_EMPTY_LABELS = ["Özellik Yok", "Özellik yok", "Görüldü", "Görüldü."];

  async function markFamilyHistoryEmpty() {
    const ok = await markCardOption("Soygeçmiş", FAMILY_EMPTY_LABELS);
    bridgeFieldStatus("family_history", ok);
    return ok ? 1 : 0;
  }

  async function fillFamilyHistory(profile = {}) {
    if (profile.no_known_family_history === true) return markFamilyHistoryEmpty();
    const entries = profile.family_history || [];
    if (!entries.length && typeof profile.parents_related !== "boolean") {
      return markFamilyHistoryEmpty();
    }
    const card = await ensureCardOpen("Soygeçmiş");
    if (!card) return markFamilyHistoryEmpty();
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
    // Satir isaretlenebildiyse "Goruldu" ile kart tamamlanmis sayilir;
    // hicbiri tutmadiysa kart bos kalmasin diye "Ozellik Yok"a dusulur.
    if (!added) return markFamilyHistoryEmpty();
    clickTextLoose(["Görüldü"], card);
    bridgeFieldStatus("family_history", true);
    return added;
  }

  function fillPsychologicalStatus(value = {}) {
    const states = value.states || [];
    if (!states.length && !value.description) return false;
    const card = cardByTitle("Psikolojik Durum");
    if (!card) return false;
    states.forEach((state) => clickToggleOn(state, card));
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
    const missing = [];
    for (const [placeholder, items] of lookupMap) {
      filled += await fillProfileLookup(history, placeholder, items || [], missing);
    }
    if (profile.marital_status && clickToggleOn(profile.marital_status, history)) filled += 1;
    if (profile.occupation) {
      if (await chooseAutocomplete(byPlaceholder("Meslek", history), profile.occupation)) filled += 1;
      else missing.push(`Meslek: ${profile.occupation}`);
    }
    if (profile.education) {
      const education = byPlaceholder("Eğitim", history);
      education?.click();
      await sleep(80);
      // CANLI: secenekler .co-select__item DIV'i; clickText bunlari kapsamiyor.
      const option = await waitFor(() => [...document.querySelectorAll(".co-select__dropdown .co-select__item")]
        .find((item) => item.offsetParent !== null && textOf(item) === profile.education), 2500);
      if (option && activateNode(option)) filled += 1;
      else missing.push(`Eğitim: ${profile.education}`);
    }
    if (missing.length) {
      const story = byPlaceholder("Öykü", cardByTitle("Yakınması") || document);
      const extra = `Özgeçmiş (HBYS listesinde yok): ${missing.join("; ")}.`;
      if (story && !String(story.value || "").includes("Özgeçmiş (HBYS listesinde yok)")) {
        setValue(story, [story.value, extra].filter(Boolean).join("\n"));
      }
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

  /* COMED acilir listelerini secer ve LISTEYI KAPATIR.
     Onceki kod 60 ms bekleyip clickText() ile ariyordu; clickText yalnizca
     button/label/span tarar, oysa secenekler li/div olabiliyor. Secenek
     bulunamayinca liste acik kaliyor ve doktorun karsisina yarim kalmis bir
     alan cikiyordu. Burada secenek genis bir kume icinde aranir, secimden
     sonra listenin gercekten kapandigi dogrulanir; kapanmadiysa Escape ile
     kapatilir. */
  async function selectDropdownOption(group, label) {
    if (!group || !label) return false;
    const input = group.querySelector("input");
    if (!input) return false;
    if (String(input.value || "").trim() === label) return true;

    input.click();
    const optionSelector = "li,[role=option],.co-select__option,.co-option,"
      + ".autocomplete__item,.co-dropdown__item,button,span,div";
    const isOpenOption = (node) => node.offsetParent !== null
      && textOf(node) === label
      && node.children.length <= 1
      && !group.contains(node);

    const option = await waitFor(
      () => [...document.querySelectorAll(optionSelector)].find(isOpenOption), 2500,
    );
    if (option) {
      activateNode(option);
      await sleep(140);
    }

    // Liste hala aciksa doktora yarim kalmis alan birakma: Escape ile kapat.
    const stillOpen = () => [...document.querySelectorAll(optionSelector)]
      .some(isOpenOption);
    if (stillOpen()) {
      input.dispatchEvent(new KeyboardEvent("keydown", {
        key: "Escape", code: "Escape", keyCode: 27, bubbles: true,
      }));
      document.body.click();
      await sleep(120);
    }
    return String(input.value || "").trim() === label;
  }

  /* ---- Hizmet istemleri (EKG, EKO, grafi...) ----
     COMED'de bunlar muayene formunda DEGIL, ayri bir ekranda girilir:
       <kart adresi>?app-action=action-order-procedure
     Canli ortamda dogrulanan akis:
       1. Ekrani ac, "Hizmet İstem" sekmesine gec
       2. Listede hizmeti bul (favorilerde yoksa arama kutusuyla ara)
       3. Satira tikla -> detay penceresi acilir
       4. "Uygulayan" alanina doktoru sec (isteyen doktorun aynisi)
       5. Secim panelini kapat, "Ekle" -> "Kayıt başarılı"
     Doktor sonra ekrani kapatip kontrol eder ve imzalar. */
  const SERVICE_SCREEN_PARAM = "app-action=action-order-procedure";
  const DRUG_SCREEN_PARAM = "app-action=action-order-drug";
  const STUDY_SCREEN_PARAM = "app-action=action-order-study";

  /* ---------- TETKİK İSTEM ----------

     COMED'de UC AYRI istem ekrani var; tetkikler (laboratuvar + radyoloji)
     ucuncusunde. "Tam Kan Sayimi"nin Hizmet Istem'de bulunamamasinin sebebi
     buydu: yanlis ekranda araniyordu.

     CANLI OLCUM (22 Ekim 2026, hasta 22207363):
       Sol agac: Favoriler (paketler) / Laboratuvar / Radyoloji / Patoloji /
                 Kardiyoloji
       Favori paketleri ve icerikleri:
         adnan kaya kardiyoloji paketi 21 · ANJİYO RUTİN 19 · kısa biyo 8 ·
         Enzim 2 · alt ekstremite doppler 4 · akciğer grafisi 2 · karotis 1
         (Bt koroner / ekooo / karotis mrlar BOS)
       Akis: satirdaki onay kutusunu isaretle -> altta "Laboratuvar İstekleri"
             / "Radyoloji İstekleri" paneli acilir -> sag altta "Ekle".
             Birden cok tetkik ayni anda isaretlenip tek "Ekle" ile eklenir.
       Hemogram (796) onay kutusu PASIF geliyor; isaretlenemez, atlanir.
       Soldaki "Ara" kutusu GLOBAL DEGIL, yalniz secili paketin icinde arar. */
  const STUDY_PACKAGES = [
    "adnan kaya kardiyoloji paketi", "Enzim", "ANJİYO RUTİN", "kısa biyo",
    "akciğer grafisi", "Bt koroner", "alt ekstremite doppler", "ekooo",
    "karotis", "karotis mrlar",
  ];
  /* Radyoloji istemlerinde "Acil" yanindaki aciklama kutusu ZORUNLU.

     CANLI OLCUM: zorunluluk ancak "Ekle"ye basinca ortaya cikiyor --
     "Form Alanları Hatası / Zorunlu alanları doldurunuz" ve her satir icin
     "Girilen açıklama hasta tetkik raporunda yer alacaktır alanı zorunludur,
      uzunluğu 3 degerinden büyük olmalı".
     Alan placeholder'indan bulunur (sinif/kirmizi-nokta tespiti tutmuyor).
     Doktor aciliyet belirtmediyse bu varsayilan yazilir. */
  const STUDY_URGENCY_DEFAULT = "Acil bir durum yoktur";
  const STUDY_NOTE_PLACEHOLDER = /Girilen açıklama hasta tetkik raporunda/i;

  /** Istem ekranini kapat ve hasta kartina don.

     Istek: "herhangi bir istemi acip bitirince kapatmiyor, digerlerini
     goremedim." Ekranlar ust uste biniyordu. Her istem turu bitince karta
     donuyoruz; sonraki ekran temiz aciliyor ve doktor arada formu gorebiliyor. */
  async function closeOrderScreen() {
    if (!/[?&]app-action=/.test(location.search)) return;
    history.pushState({}, "", location.pathname);
    window.dispatchEvent(new PopStateEvent("popstate"));
    await waitForDomQuiet(document.body, 300, 3500);
  }

  async function openStudyScreen() {
    if (!location.search.includes(STUDY_SCREEN_PARAM)) {
      history.pushState({}, "", `${location.pathname}?${STUDY_SCREEN_PARAM}`);
      window.dispatchEvent(new PopStateEvent("popstate"));
      await waitFor(() => location.search.includes(STUDY_SCREEN_PARAM), 4000);
    }
    await waitForDomQuiet(document.body, 300, 4000);
    await waitFor(() => studyMenuVisible()
      || document.querySelector('[data-test="co-button-Yeni Tetkik İstem"]'), 15000);
    await ensureStudyAddView();
    return Boolean(await waitFor(() => studyRows().length ? true : null, 15000));
  }

  /** Tetkik listesi satirlari: onay kutusu tasiyan gorunur satirlar. */
  function studyRows() {
    return [...document.querySelectorAll("tbody tr, [role=row]")].filter(
      (row) => row.offsetParent !== null
        && textOf(row).length > 8
        && row.querySelector('input[type="checkbox"]'),
    );
  }

  /** Satirdaki tetkik adi: "Açlık Kan Şekeri (AKŞ) - ++44 Biyokimya ..." */
  function studyRowName(row) {
    const cells = [...row.querySelectorAll("td,[role=cell]")]
      .map((cell) => textOf(cell)).filter(Boolean);
    const named = cells.find((cell) => /[A-Za-zÇĞİÖŞÜçğıöşü]{3}/.test(cell));
    return String(named || textOf(row)).split(" - ")[0].trim();
  }

  /* CANLI OLCUM (26 Ekim): Tetkik ekrani iki gorunumlu. "Ekle"den sonra ya da
     bir istem reddedilince EKLEME gorunumu (sol favori agaci + onay kutulu
     liste) yerine ISTEM LISTESI gorunumune donebiliyor: ustte Ilac/Diyet/
     Bakim/Tetkik/Hizmet sekmeleri, solda "+ Yeni Tetkik İstem" dugmesi.
     Bu gorunumde favori agaci HIC yok; toplu calismada sonraki 8 paket
     "menude gorunmuyor" diye sessizce atlaniyor, Akciger Grafisi bu yuzden
     eklenmiyordu. "Yeni Tetkik İstem" ekleme gorunumunu geri getiriyor. */
  function studyMenuVisible() {
    const leaves = new Set([...document.querySelectorAll("a,li,div,span")]
      .filter((node) => node.offsetParent !== null && node.children.length === 0)
      .map((node) => textOf(node)));
    return STUDY_PACKAGES.some((name) => leaves.has(name));
  }

  async function ensureStudyAddView() {
    if (studyMenuVisible()) return true;
    const button = [...document.querySelectorAll('[data-test="co-button-Yeni Tetkik İstem"]')]
      .find((node) => node.offsetParent !== null);
    if (!button) return false;
    pressNode(button);
    return Boolean(await waitFor(studyMenuVisible, 8000));
  }

  /** Ekrandaki istem listesinin (Aktif Protokol) tarihli satirlari.

     CANLI OLCUM (26 Ekim): "Ekle"den sonra hata cikmamasi KAYDEDILDIGI
     anlamina GELMIYOR. Tam kosuda sayac "3 tetkik eklendi" dedi, COMED'in
     istem listesine tek satir dusmedi. Doktora "eklendi" deyip eklememek en
     kotu sonuc. Basariyi listeye YENI satir dusmesiyle olcuyoruz. */
  function studyOrderRows() {
    return [...document.querySelectorAll("tbody tr, [role=row]")]
      .filter((row) => row.offsetParent !== null
        && /\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}/.test(textOf(row)))
      .map((row) => textOf(row));
  }

  /** once alinan listeye gore yeni dusen satir sayisi (ayni metinli satirlari
     da sayar: ayni dakikada ikinci CRP de "yeni"dir). */
  function newStudyOrderCount(before) {
    const kalan = new Map();
    before.forEach((text) => kalan.set(text, (kalan.get(text) || 0) + 1));
    let yeni = 0;
    for (const text of studyOrderRows()) {
      const adet = kalan.get(text) || 0;
      if (adet > 0) kalan.set(text, adet - 1);
      else yeni += 1;
    }
    return yeni;
  }

  /** Basarisiz paketin tiklerini kaldir: sonraki paketin "Ekle"sine
     karismasinlar. */
  function untickStudyRows(labels) {
    const wanted = new Set(labels.map((label) => simplifyStudy(label)));
    for (const row of studyRows()) {
      const box = row.querySelector('input[type="checkbox"]');
      if (!box || !box.checked || box.disabled) continue;
      if (!wanted.has(simplifyStudy(studyRowName(row)))) continue;
      pressNode(box.closest("label") || box);
    }
  }

  /** Sol menuden favori paketini sec ve listenin O PAKETE gecmesini bekle.

     CANLI OLCUM (26 Ekim): toplu calismada paket degisirken liste hemen
     yenilenmiyor; eslestirme bir onceki paketin satirlarina bakip "yok"
     diyordu. Akciger Grafisi tek basina eklenirken toplu calismada
     "bulunamadi" diye dusuyordu. Liste basligi ("Favoriler : Akciğer
     Grafisi") secilen pakete gecene kadar bekliyoruz. */
  async function selectStudyPackage(name) {
    await ensureStudyAddView();
    const item = [...document.querySelectorAll("a,li,div,span")].find(
      (node) => node.offsetParent !== null && node.children.length === 0
        && textOf(node) === name,
    );
    if (!item) return false;
    const wanted = name.toLocaleLowerCase("tr-TR");
    const headerShows = () => [...document.querySelectorAll("*")].some(
      (node) => node.offsetParent !== null && node.children.length <= 2
        && /^Favoriler\s*:/i.test(textOf(node))
        && textOf(node).toLocaleLowerCase("tr-TR").includes(wanted));
    pressNode(item);
    await waitFor(headerShows, 6000);
    await waitForDomQuiet(document.body, 300, 3500);
    return true;
  }

  /* Tetkik adini satirla esle.

     CANLI OLCUM: model bilimsel tam adi yaziyor, COMED kisaltma kullaniyor:
       "Alanin Aminotransferaz (ALT)"        -> COMED: "ALT (SGPT)"
       "C-Reaktif Protein (CRP)"             -> COMED: "CRP (Kantitatif)"
       "Total Demir Bağlama Kapasitesi (TDBK)" -> COMED: "Demir Bağlama Kapasitesi (UIBC)"
       "HDL Kolesterol"                      -> COMED: "HDL-Kolesterol"
     Bu yuzden hem tam ad, hem parantezsiz cekirdek, hem de PARANTEZ ICINDEKI
     KISALTMA aday olarak denenir. Noktalama (tire/bosluk) sadelestirilir.
     Hizmet istemindeki niteleyici vetosu burada da gecerli. */
  function studyCandidates(name) {
    const lower = name.toLocaleLowerCase("tr-TR").trim();
    const core = lower.replace(/\(.*?\)/g, "").trim();
    const abbreviations = [...lower.matchAll(/\(([^)]+)\)/g)]
      .map((match) => match[1].trim())
      .filter((value) => value && value.length <= 12);
    return [...new Set([lower, core, ...abbreviations].filter(Boolean))];
  }

  /** "HDL-Kolesterol" ile "HDL Kolesterol" ayni sayilsin. */
  function simplifyStudy(value) {
    return value.toLocaleLowerCase("tr-TR").replace(/[\s\-_.]+/g, " ").trim();
  }

  function matchStudyRow(name) {
    const wanted = name.toLocaleLowerCase("tr-TR").trim();
    const candidates = studyCandidates(name);
    const rows = studyRows();
    const score = (row) => {
      const label = studyRowName(row).toLocaleLowerCase("tr-TR");
      const labelCore = label.replace(/\(.*?\)/g, "").trim();
      const labelAbbr = [...label.matchAll(/\(([^)]+)\)/g)].map((m) => m[1].trim());
      for (const qualifier of SERVICE_QUALIFIERS) {
        if (label.includes(qualifier)
          && !candidates.some((c) => c.includes(qualifier))) return -1000;
      }
      let best = 0;
      for (const candidate of candidates) {
        const c = simplifyStudy(candidate);
        if (!c) continue;
        if (simplifyStudy(label) === c) best = Math.max(best, 200);
        else if (simplifyStudy(labelCore) === c) best = Math.max(best, 180);
        else if (labelAbbr.some((a) => simplifyStudy(a) === c)) best = Math.max(best, 160);
        else if (simplifyStudy(labelCore).startsWith(`${c} `)) best = Math.max(best, 120);
        else if (simplifyStudy(label).includes(c) && c.length > 4) best = Math.max(best, 60);
      }
      return best;
    };
    const best = rows.map((row) => ({row, value: score(row)}))
      .sort((a, b) => b.value - a.value)[0];
    return best && best.value >= 120 ? best.row : null;
  }

  /** Alt paneldeki zorunlu aciklama kutularini varsayilanla doldur.

     Placeholder ile bulunuyor: canli olcumde sinif/kirmizi-nokta tespiti
     hic tutmadi, placeholder ile 7/7 doldu. */
  function fillStudyRequiredNotes() {
    let filled = 0;
    for (const field of document.querySelectorAll("textarea, input")) {
      if (field.offsetParent === null || field.value) continue;
      if (!STUDY_NOTE_PLACEHOLDER.test(field.getAttribute("placeholder") || "")) continue;
      if (setValue(field, STUDY_URGENCY_DEFAULT)) filled += 1;
    }
    return filled;
  }

  /** Klinik secim isteyen tetkiklerin TIKINI LISTEDEN kaldir.

     CANLI OLCUM: "Vitamin D3 (25-OH-Kolekalsiferol)" satiri "Endikasyon
     seçiniz" istiyor. Endikasyon klinik gerekcedir, otomatik secmek tibbi
     karar vermek olur.

     Alt paneldeki satiri X ile kapatmayi denedik, COMED'de tutmadi. Onun
     yerine ustteki LISTEDEN tiki kaldiriyoruz -- isaretleme mekanizmasi
     zaten calisiyor. Boylece tek sorunlu tetkik yuzunden paketteki diger
     20 tetkik kaybolmuyor.
     @returns {string[]} tiki kaldirilan tetkik adlari */
  function untickBlockedStudies() {
    const blocked = new Set();
    const errors = [...document.querySelectorAll("*")].filter(
      (node) => node.offsetParent !== null && node.children.length === 0
        && /Endikasyon seçiniz|alanı zorunludur/i.test(textOf(node)));
    for (const error of errors) {
      let holder = error;
      for (let step = 0; step < 9 && holder; step += 1) {
        holder = holder.parentElement;
        if (!holder) break;
        const text = textOf(holder);
        if (text.length < 20 || text.length > 320) continue;
        // "Vitamin D3 (25-OH-Kolekalsiferol) - Kan Endikasyon seçiniz"
        const name = text.split(/\s-\s|Endikasyon|Açıklama/)[0].trim();
        if (name.length > 3) blocked.add(name);
        break;
      }
    }
    const removed = [];
    for (const name of blocked) {
      const simple = simplifyStudy(name);
      for (const row of studyRows()) {
        const box = row.querySelector('input[type="checkbox"]');
        if (!box || !box.checked) continue;
        if (!simplifyStudy(studyRowName(row)).startsWith(simple.slice(0, 18))) continue;
        pressNode(box.closest("label") || box);
        removed.push(name);
        break;
      }
    }
    return [...new Set(removed)];
  }

  /** "Ekle"den sonra COMED hala zorunlu alan istiyor mu? */
  function studyValidationErrors() {
    return [...document.querySelectorAll("*")]
      .filter((node) => node.offsetParent !== null && node.children.length === 0
        && /alanı zorunludur|Zorunlu alanları doldurunuz/i.test(textOf(node)))
      .map((node) => textOf(node));
  }

  /** Doküman isteyen istem satiri var mi? (ornek: Gliko Hemoglobin HbA1C) */
  function studyDocumentWarnings() {
    return [...document.querySelectorAll("*")]
      .filter((node) => node.offsetParent !== null
        && node.children.length === 0
        && /Dokümanları Doldurunuz/i.test(textOf(node)))
      .length;
  }

  /** @returns {{added:number, picked:string[], skipped:string[], remaining:object[]}}
     remaining: tetkik ekraninda bulunamayanlar. Bunlar hata degildir --
     EKG gibi islemler Hizmet Istem ekraninda duruyor, oraya devredilir. */
  async function fillStudyRequests(studies = []) {
    const result = {added: 0, picked: [], skipped: [], remaining: []};
    if (!studies.length) return result;
    if (!await openStudyScreen()) {
      // Ekran acilmadiysa hepsini hizmet ekranina devret, kaybetme.
      result.remaining = studies.slice();
      return result;
    }
    const kalan = new Map();
    for (const study of studies) {
      const name = String(study?.name || "").trim();
      if (name) kalan.set(name, study);
    }
    // Paketleri tek tek gez; her pakette bulunanlari isaretle. COMED birden
    // cok tetkigi tek "Ekle" ile kabul ediyor, bu yuzden paket basina topluyoruz.
    /* CANLI OLCUM (26 Ekim): bir paketin "Ekle"sinden SONRA ekran "kayit
       sonrasi" durumda kaliyor. Sonraki pakette onay kutusu gorunuste
       tikleniyor ama COMED onu kaydetmiyor: alt istek paneli hic acilmiyor
       (Vazgec yok), "Ekle" pasif. Taze acilmis ekranda ilk paket her zaman
       calisiyor. Bu yuzden istem gonderilen her paketten sonra ekrani kapatip
       TAZE aciyoruz -- doktorun elle yapacagi da bu. */
    let ekranKirli = false;
    for (const paket of STUDY_PACKAGES) {
      if (!kalan.size) break;
      if (ekranKirli) {
        await closeOrderScreen();
        if (!await openStudyScreen()) {
          bridgeStatus("Tetkik ekranı yeniden açılamadı", "bad");
          break;
        }
        ekranKirli = false;
      }
      if (!await selectStudyPackage(paket)) {
        // Sessizce gecmeyelim: canli testte paketler bu yuzden atlaniyordu.
        bridgeStatus(`Tetkik paketi menüde görünmüyor · ${paket}`, "bad");
        continue;
      }
      const isaretli = [];
      for (const [name] of [...kalan]) {
        const row = matchStudyRow(name);
        if (!row) continue;
        const box = row.querySelector('input[type="checkbox"]');
        if (!box) continue;
        if (box.disabled) {
          // Hemogram gibi pasif tetkikler isaretlenemiyor.
          result.skipped.push(`${name}: COMED'de pasif, işaretlenemiyor`);
          kalan.delete(name);
          continue;
        }
        if (!box.checked) {
          pressNode(box.closest("label") || box);
          await sleep(140);
        }
        isaretli.push({name, label: studyRowName(row)});
        kalan.delete(name);
      }
      if (!isaretli.length) continue;
      ekranKirli = true;
      bridgeStatus(`Tetkik istemi hazırlanıyor · ${paket}`);
      await waitForDomQuiet(document.body, 320, 4000);
      /* Doküman isteyen tetkik varsa istemi hic gondermiyoruz: yarim
         birakilmis bir istem doktoru yaniltir. Hangisi oldugu rapora yazilir. */
      if (studyDocumentWarnings()) {
        isaretli.forEach((item) => result.skipped.push(
          `${item.name}: doküman doldurulması gerekiyor, doktor tamamlamalı`));
        const vazgec = dialogButton("co-button-Vazgeç");
        if (vazgec) pressNode(vazgec);
        await waitForDomQuiet(document.body, 300, 3000);
        continue;
      }
      fillStudyRequiredNotes();
      const ekle = await waitFor(() => {
        const button = dialogButton("co-button-Ekle");
        return button && !button.disabled ? button : null;
      }, 10000);
      if (!ekle) {
        /* Olcum: ayni tetkik zaten AKTIF istem olarak varsa (ornek Troponin I)
           COMED "Ekle"yi acmiyor. Tikleri kaldirip devam ediyoruz. */
        untickStudyRows(isaretli.map((item) => item.label));
        isaretli.forEach((item) => result.skipped.push(
          `${item.name}: "Ekle" etkinleşmedi (zaten aktif istem olabilir), doktor kontrol etmeli`));
        continue;
      }
      const listeOnce = studyOrderRows();
      pressNode(ekle);
      await waitForDomQuiet(document.body, 350, 5000);
      /* COMED zorunlulugu ancak "Ekle"den sonra bildiriyor. Alanlar o anda
         gorunur hale geliyor: doldurup BIR KEZ daha deniyoruz. */
      if (studyValidationErrors().length) {
        const eklenen = fillStudyRequiredNotes();
        if (eklenen) {
          await waitForDomQuiet(document.body, 300, 3000);
          const tekrar = dialogButton("co-button-Ekle");
          if (tekrar && !tekrar.disabled) {
            pressNode(tekrar);
            await waitForDomQuiet(document.body, 350, 5000);
          }
        }
      }
      let kalanHata = studyValidationErrors();
      if (kalanHata.length) {
        /* Endikasyon gibi KLINIK secim isteyen satirlar kaldi (olcum:
           Vitamin D3 "Endikasyon seçiniz" istiyor). Bunu otomatik secmek
           tibbi karar vermek olur. Ama tek satir yuzunden paketteki diger
           20 tetkigi kaybetmeyelim: SORUNLU SATIRI panelden cikarip
           kalanlari ekliyoruz, cikarilan doktora bildiriliyor. */
        const sorunlu = untickBlockedStudies();
        sorunlu.forEach((ad) => {
          result.skipped.push(`${ad}: klinik seçim gerekiyor (Endikasyon vb.), doktor tamamlamalı`);
          const index = isaretli.findIndex((item) => item.label.includes(ad) || ad.includes(item.name));
          if (index >= 0) isaretli.splice(index, 1);
        });
        if (sorunlu.length && isaretli.length) {
          await waitForDomQuiet(document.body, 300, 3000);
          const ucuncu = dialogButton("co-button-Ekle");
          if (ucuncu && !ucuncu.disabled) {
            pressNode(ucuncu);
            await waitForDomQuiet(document.body, 350, 5000);
          }
        }
        kalanHata = studyValidationErrors();
      }
      if (kalanHata.length || !isaretli.length) {
        untickStudyRows(isaretli.map((item) => item.label));
        isaretli.forEach((item) => result.skipped.push(
          `${item.name}: ${(kalanHata[0] || "zorunlu alan").slice(0, 60)} — doktor tamamlamalı`));
        continue;
      }
      const dusen = await waitFor(() => {
        const adet = newStudyOrderCount(listeOnce);
        return adet > 0 ? adet : null;
      }, 9000) || 0;
      if (!dusen) {
        untickStudyRows(isaretli.map((item) => item.label));
        isaretli.forEach((item) => result.skipped.push(
          `${item.name}: "Ekle"ye basıldı ama COMED istem listesine düşmedi — doktor kontrol etmeli`));
        bridgeStatus(`${paket}: Ekle sonrası istem listeye düşmedi`, "bad");
        continue;
      }
      if (dusen < isaretli.length) {
        bridgeStatus(`${paket}: ${isaretli.length} tetkikten ${dusen} tanesi listeye düştü`, "bad");
      }
      result.added += Math.min(dusen, isaretli.length);
      isaretli.slice(0, dusen).forEach((item) => result.picked.push(item.label.slice(0, 80)));
      isaretli.slice(dusen).forEach((item) => result.skipped.push(
        `${item.name}: listeye düşmedi — doktor kontrol etmeli`));
      bridgeFieldStatus("requested_services", true);
    }
    // Kalanlar tetkik degil, islem olabilir (EKG gibi) -> Hizmet Istem denesin.
    result.remaining = [...kalan.values()];
    return result;
  }

  function serviceRows() {
    return [...document.querySelectorAll("tbody tr, [role=row]")]
      .filter((row) => row.offsetParent !== null && textOf(row).length > 10);
  }

  /* CANLI OLCUM (22 Ekim 2026): katalogda ayni tetkikin nitelikli turevleri
     var ve duz hali bulunmayabiliyor.
       "ekokardiyografi"   -> 3D / Fetal / Stres ekokardiyografi
                              (duz "Ekokardiyografi" YOK)
       "elektrokardiogram" -> Elektrokardiogram (EKG) + 12 derivasyonlu,
                              evde cekim, trase monitorizasyonu, Fetal ...
       "tam kan sayimi" / "hemogram" -> HIC SONUC YOK
     Eski kural (ilk "includes" eslesmesi) doktor "EKO" dediginde
     "3D ekokardiyografi" siparis ediyordu -- ilac tarafindaki PAROL COLD
     hatasinin aynisi. Artik tam hucre eslesmesi kazanir, istenmeyen nitelik
     tasiyan satir VETO edilir, emin olunamazsa istem doktora birakilir. */
  const SERVICE_QUALIFIERS = [
    "3d", "fetal", "stres", "evde", "trase", "pediatrik", "holter", "efor",
    "yorumlama", "monitorizasyon", "kadın hastalıkları", "ambulatuar",
  ];
  const SERVICE_SCORE_THRESHOLD = 100;

  function serviceCells(row) {
    return [...row.querySelectorAll("td,[role=cell]")]
      .map((cell) => textOf(cell)).filter(Boolean);
  }

  function scoreServiceRow(row, wanted, core) {
    const cells = serviceCells(row);
    if (!cells.length) return -1000;
    /* Katalog satirlarinin ilk hucresi kod ("16384", "208", "MRD-1"). Zaten
       eklenmis istem satirlari "Hizmet" ile basliyor; onlari tekrar ekleme. */
    if (!/^[A-Za-z0-9-]{2,12}$/.test(cells[0])) return -1000;
    const lower = cells.join(" ").toLocaleLowerCase("tr-TR");
    for (const qualifier of SERVICE_QUALIFIERS) {
      if (lower.includes(qualifier)
        && !wanted.includes(qualifier) && !core.includes(qualifier)) return -1000;
    }
    const named = cells.some((cell) => {
      const value = cell.toLocaleLowerCase("tr-TR");
      return value === wanted || value === core
        || value.startsWith(`${core} `) || value.startsWith(`${core}(`);
    });
    if (named) return 100;
    return lower.includes(core) ? 40 : 0;
  }

  /** Hizmet adini satirla esle. Emin olunamazsa null doner. */
  function matchServiceRow(name) {
    const wanted = name.toLocaleLowerCase("tr-TR").trim();
    // "Elektrokardiogram (EKG)" aranirken cekirdek "elektrokardiogram".
    const core = wanted.replace(/\(.*?\)/g, "").trim() || wanted;
    /* Yalniz KATALOG satirlari (ilk hucre kod). CANLI OLCUM (26 Ekim): tam ad
       eslesmesi alttaki istem listesindeki eski "Hizmet Elektrokardiogram
       (EKG)" satirini yakaliyordu; katalog yerine eski isteme basiliyordu. */
    const rows = serviceRows()
      .filter((row) => /^[A-Za-z0-9-]{2,12}$/.test(serviceCells(row)[0] || ""));
    const exact = rows.find((row) => serviceCells(row).some((cell) => {
      const value = cell.toLocaleLowerCase("tr-TR");
      return value === wanted || value === core;
    }));
    if (exact) return exact;
    const best = rows
      .map((row) => ({row, score: scoreServiceRow(row, wanted, core)}))
      .sort((a, b) => b.score - a.score)[0];
    return best && best.score >= SERVICE_SCORE_THRESHOLD ? best.row : null;
  }

  /** Istem ekranini ac ve "Hizmet İstem" sekmesine gec. */
  async function openServiceScreen() {
    if (!location.search.includes(SERVICE_SCREEN_PARAM)) {
      const url = `${location.pathname}?${SERVICE_SCREEN_PARAM}`;
      history.pushState({}, "", url);
      window.dispatchEvent(new PopStateEvent("popstate"));
      await waitFor(() => location.search.includes(SERVICE_SCREEN_PARAM), 4000);
    }
    const tab = await waitFor(
      () => document.querySelector('[data-test="co-button-Hizmet İstem"]'), 12000);
    if (!tab) return false;
    pressNode(tab);
    await waitForDomQuiet(document.body, 260, 3000);
    return true;
  }

  /** Detay penceresinde uygulayan doktoru sec.

     Her hizmet turunun penceresi ayni degil: "Hizmet" tipinde (EKG gibi)
     Uygulayan alani zorunlu, "Radyoloji" tipinde (grafi gibi) bu alan hic
     yok -- onun yerine cekim yontemi/vucut bolgesi gibi alanlar cikiyor.
     Alan yoksa bu adim atlanir; eksikse "Ekle" zaten pasif kalir ve istem
     doktora birakilir. */
  async function pickPerformingDoctor(doctorName) {
    const opener = document.querySelector('[data-test="personnel-department-Uygulayan"]');
    if (!opener) return true;                       // bu pencerede alan yok
    if (textOf(opener) && !/^Uygulayan$/i.test(textOf(opener))) return true;  // zaten dolu
    pressField(opener);                             // dinleyici ok ikonunda
    const rows = await waitFor(() => {
      const found = [...document.querySelectorAll(".department-select-button")]
        .filter((row) => row.offsetParent !== null);
      return found.length ? found : null;
    }, 6000);
    if (!rows) return false;
    // Isteyen doktorun adiyla esles; bulunamazsa ilk siradakini birakma.
    const parts = String(doctorName || "").split(/[-|]/).map((p) => p.trim()).filter(Boolean);
    const target = rows.find((row) => {
      const text = textOf(row).toLocaleLowerCase("tr-TR");
      return parts.every((part) => text.includes(part.toLocaleLowerCase("tr-TR")));
    });
    if (!target) {
      document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
      return false;
    }
    pressNode(target);
    await sleep(600);
    // Secim paneli disariya tiklayinca kapanir.
    pressNode(document.body);
    await sleep(400);
    return true;
  }

  /** @returns {{added:number, picked:string[], skipped:string[], remaining:object[]}}
     remaining: hizmet katalogunda bulunamayanlar. Hata degildir --
     laboratuvar tetkikleri Tetkik Istem ekraninda duruyor, oraya devredilir. */
  async function fillServiceRequests(services = []) {
    const result = {added: 0, picked: [], skipped: [], remaining: []};
    if (!services.length) return result;
    if (!await openServiceScreen()) {
      // Ekran acilmadiysa hepsini tetkik ekranina devret, kaybetme.
      result.remaining = services.slice();
      return result;
    }
    // Isteyen doktor zaten dolu gelir; uygulayan icin ayni adi kullanacagiz.
    const requester = textOf(
      document.querySelector('[data-test^="personnel-department"]')) || "";
    // Sinir yok: eskiden ilk 8 hizmet deneniyor, 9. ve sonrasi (ALT, AST,
    // AKŞ) SESSIZCE kayboluyordu -- atlanan listesine bile yazilmiyordu.
    // Ust sinir sunucuda (25).
    for (const service of services) {
      const name = String(service?.name || "").trim();
      if (!name) continue;
      bridgeStatus(`Hizmet istemi hazırlanıyor · ${name}`);
      try {
        // Her hizmetten once arama kutusunu temizle; onceki aramanin suzgeci
        // kalirsa sonraki hizmet "listede yok" sanilip atlaniyordu.
        const search = [...document.querySelectorAll("input")]
          .find((input) => input.offsetParent !== null
            && /ara/i.test(input.placeholder || ""));
        if (search && search.value) {
          setTypingValue(search, " ");
          search.value = "";
          search.dispatchEvent(new Event("input", {bubbles: true}));
          await waitForDomQuiet(document.body, 260, 2500);
        }
        /* Her hizmet ONCE aranir, sonra tiklanir. CANLI OLCUM (26 Ekim): bir
           istem eklendikten sonra favori listesindeki satira aramasiz basinca
           pencere acilip 0,5 sn icinde kapaniyordu ("Ekle" pasif -> EKG'den
           sonra EKO hep dusuyordu). Arama listeyi yeniden cizince tiklama
           tutuyor. */
        const query = name.replace(/\(.*?\)/g, "").trim();
        let row = null;
        if (search) {
          setTypingValue(search, query);
          await waitForDomQuiet(document.body, 300, 3500);
          row = matchServiceRow(name);
        }
        if (!row) row = matchServiceRow(name);
        if (!row) {
          /* Liste varsayilan olarak "Favoriler" sekmesinde aciliyor; orada
             olmayan hizmet (ornegin Ekokardiyografi) bulunamiyordu. Tum
             katalog icin "Genel" sekmesine gecip bir daha araniyor. */
          const general = [...document.querySelectorAll("button,div,span")]
            .find((item) => item.offsetParent !== null && textOf(item) === "Genel");
          if (general) {
            pressNode(general);
            await waitForDomQuiet(document.body, 300, 3500);
            if (search) {
              setTypingValue(search, query);
              await waitForDomQuiet(document.body, 300, 3500);
            }
            row = matchServiceRow(name);
          }
        }
        if (!row) {
          /* Hizmet katalogunda yok. Laboratuvar tetkigi olabilir (Tam Kan
             Sayimi gibi) -> Tetkik Istem ekranina devret. Orada da yoksa
             orasi "bulunamadi" diye bildirir. */
          result.remaining.push(service);
          continue;
        }
        const rowText = textOf(row).slice(0, 90);
        /* CANLI OLCUM (26 Ekim): ekran ilk acildiginda liste YENIDEN
           ciziliyor. Eslestiricinin buldugu satir DOM'dan kopuyor, kopuk
           satira basmak hicbir sey acmiyor. Listenin ilk istemi (EKG) tam o
           ana denk geldigi icin "istem penceresi açılmadı" diye dusuyordu;
           tek basina denendiginde pencere 0,5 sn'de aciliyordu. Acilmazsa
           satiri YENIDEN bulup bir kez daha basiyoruz. */
        const dialogOpen = () => [...document.querySelectorAll('[data-test="co-button-Vazgeç"]')]
          .some((item) => item.offsetParent !== null);
        let opened = false;
        for (let deneme = 0; deneme < 2 && !opened; deneme += 1) {
          const target = deneme === 0 && row.isConnected ? row : matchServiceRow(name);
          if (!target) break;
          pressNode(target);
          // Pencerenin acilmasini "Vazgeç" ile anla: "Ekle" adi sayfada birden
          // cok yerde geciyor.
          opened = Boolean(await waitFor(dialogOpen, deneme === 0 ? 4000 : 6000));
        }
        if (opened) {
          /* CANLI OLCUM (26 Ekim): ikinci hizmette onceki pencerenin "Vazgeç"i
             hala ekranda, "acildi" kontrolu aninda geciyor. Uygulayan yeni
             pencere yuklenmeden seciliyor, yuklenince SIFIRLANIYOR ve "Ekle"
             pasif kaliyordu (EKG'den sonra EKO hep dusuyordu). Yeni pencerenin
             bos "Uygulayan" alaniyla gelmesini bekle. */
          await waitFor(() => {
            const opener = document.querySelector('[data-test="personnel-department-Uygulayan"]');
            return !opener || /^Uygulayan$/i.test(textOf(opener));
          }, 4000);
          await waitForDomQuiet(document.body, 260, 2000);
        }
        if (!opened) {
          // Tetkik ekraninda ayni istem olabilir; orada bir kez daha denensin.
          result.remaining.push({...service, hizmetNotu: "istem penceresi açılmadı"});
          continue;
        }
        const doctorOk = await pickPerformingDoctor(requester);
        /* Gerekce BILEREK yazilmiyor. CANLI OLCUM (26 Ekim): istem penceresinde
           "Açıklama" kutusu yok; byPlaceholder("Açıklama") arkadaki kartin
           ILK Açıklama alanini -- "Psikolojik Durum" aciklamasini -- buluyor ve
           her istemin gerekcesi oraya yaziliyordu. Gerekce zorunlu degil. */
        /* CANLI OLCUM (26 Ekim): Transözofageal ekokardiografi penceresinde
           "Ekle" uygulayan secilip aciklama yazildiktan sonra GEC etkinlesiyor.
           Hemen bakinca pasif goruldu, istem "ek zorunlu alan istiyor" diye
           doktora birakildi; tek basina denendiginde ekleniyordu. Pasifse
           etkinlesmesini bekle; gercekten zorunlu alan varsa pasif kalir. */
        const addButton = doctorOk
          ? (await waitFor(() => {
            const button = dialogButton("co-button-Ekle");
            return button && !button.disabled ? button : null;
          }, 8000)) || dialogButton("co-button-Ekle")
          : null;
        if (!addButton || addButton.disabled) {
          /* Uygulayan secilemedi ya da bu hizmet turu ek zorunlu alan
             istiyor (radyolojide cekim yontemi, vucut bolgesi gibi).
             Istemi yarim birakmiyoruz: pencereyi kapatip doktora birakiyoruz. */
          pressNode(dialogButton("co-button-Vazgeç"));
          await waitForDomQuiet(document.body, 260, 2500);
          /* CANLI OLCUM (26 Ekim): Akciger Grafisi ve Troponin Hizmet Istem
             katalogunda DA var ama orada radyoloji/laboratuvar ek alani
             istiyor. Tetkik Istem ekraninda ayni kalem varsayilan aciklamayla
             ekleniyor. Burada vazgecmek yerine Tetkik ekranina devrediyoruz;
             orada da olmazsa bu not raporlanir. */
          result.remaining.push({...service, hizmetNotu: doctorOk
            ? "Hizmet İstem'de ek zorunlu alan istiyor"
            : "uygulayan doktor seçilemedi"});
          continue;
        }
        pressNode(addButton);
        await waitForDomQuiet(document.body, 320, 4000);
        result.added += 1;
        result.picked.push(rowText);
        bridgeFieldStatus("requested_services", true);
      } catch (error) {
        result.skipped.push(`${name}: ${error.message || "beklenmeyen hata"}`);
      }
    }
    return result;
  }

  /* ---------- İLAÇ İSTEM ----------

     COMED'de ilaç istemi hizmet isteminden daha basit: zorunlu alan yok.
     Canli ortamda olculen akis:
       1. ?app-action=action-order-drug -> "İlaç İstem" sekmesi
       2. "Ana İlaç" arama kutusuna ilac adi yazilir
       3. Acilan oneri listesinden satir secilir (COMED formu kendi doldurur:
          veris yolu, miktar, doz, uygulama, siklik hep varsayilan gelir)
       4. Doktor siklik soylediyse "Günlük N Kez" dugmesine basilir
       5. "Ekle" -> istem listeye duser
     Doz/siklik soylenmediyse hicbir alana dokunmuyoruz; COMED'in varsayilani
     kalir ve doktor imzalamadan once kontrol eder. */

  /** İlac arama kutusu.

     CANLI OLCUM (22 Ekim 2026): placeholder "Temel ilaçlar kategorisinde ara".
     Ayni ekranda alt arac cubugunda "Ara" ve "İsteyen ara..." kutulari da var;
     onlar elenmeli. Onceki surumde kutular "ara" gecen placeholder'a bakilarak
     eleniyordu -- dogru kutunun placeholder'i da "...kategorisinde ara" ile
     bittigi icin hedef kutu bizzat eleniyor ve istem sessizce atlaniyordu.
     Ayrica ".co-input__label" icinde "Ana İlaç" etiketi YOK; etiketle
     bulmaya calismak da ise yaramaz. */
  const DRUG_TOOLBAR_PLACEHOLDERS = ["ara", "isteyen ara...", "isteyen ara"];

  function drugSearchInput() {
    const visible = [...document.querySelectorAll("input")]
      .filter((input) => input.offsetParent !== null && !input.disabled);
    const placeholderOf = (input) =>
      (input.getAttribute("placeholder") || "").trim().toLocaleLowerCase("tr-TR");
    // Olculen kesin yol: placeholder'da "ilaç" geciyor.
    const byDrugWord = visible.find((input) => /ila[çc]/.test(placeholderOf(input)));
    if (byDrugWord) return byDrugWord;
    // Yedek: alt arac cubugunun kutularini eleyip kalan autocomplete girisi.
    return visible.find((input) => {
      if (!input.closest(".autocomplete__input")) return false;
      return !DRUG_TOOLBAR_PLACEHOLDERS.includes(placeholderOf(input));
    }) || null;
  }

  /* Ayni etken maddenin onlarca formu listeleniyor. "parol" aramasinin canli
     sonucu (olculdu):
       PAROL COLD Kapsül 325 mg ... Fenilpropanolamin HCl
       PAROL HOT Granül ...
       PAROL IV Flakon 10 mg/ml ...
       PAROL Tablet 500 mg 20 tabletlik ambalaj Parasetamol
     "Ilk baslayan eslesme" kurali COLD'u seciyordu: grip ilaci, icinde
     sempatomimetik var, yasli/hipertansif hastada yanlis secim. Bu yuzden
     puanlama kullaniyoruz ve emin olamazsak ILACI HIC EKLEMIYORUZ. */
  const DRUG_QUALIFIERS = ["cold", "hot", "plus", "forte", "fort", "pediatrik"];
  const DRUG_PARENTERAL = ["flakon", "ampul", "i.v", " iv ", "infüzyon", "infuzyon"];
  const DRUG_ORAL = ["tablet", "kapsül", "kapsul", "film"];
  /* Esik canli katalogda olculerek secildi: marka adi bas kelime olarak
     eslesip (100) ya dozu tutuyorsa (+60) ya da agizdan form ise (+20)
     kabul edilir. Daha dusuk her sey doktora birakilir. */
  const DRUG_SCORE_THRESHOLD = 120;
  const DRUG_LOCAL_FORMS = ["sprey", "damla", "krem", "pomad", "jel", "şurup", "inhaler", "fitil"];

  function scoreDrugOption(text, wantedRaw, dose) {
    /* CANLI OLCUM (3 Kasim): COMED "ALLERGODIL" yaziyor; tr-TR kucultme
       "allergodıl" (noktasiz ı) veriyor, "allergodil" ile hic eslesmiyordu.
       Iki taraf da ı -> i ile katlanir. */
    const fold = (value) => String(value || "").toLocaleLowerCase("tr-TR").replace(/ı/g, "i");
    const lower = fold(text);
    const wanted = fold(wantedRaw);
    /* VETO: doktorun soylemedigi marka eki tasiyan urun BASKA bir ilactir.
       "Parol" denince PAROL COLD secilmesi (sempatomimetik iceriyor, yasli
       hipertansifte kontrendike) bu vetoyla engelleniyor. Puanla telafi
       edilemez, dogrudan elenir. */
    for (const qualifier of DRUG_QUALIFIERS) {
      if (lower.includes(qualifier) && !wanted.includes(qualifier)) return -1000;
    }
    let score = 0;
    // Marka adi bas kelime(ler) olarak birebir geciyorsa en guclu sinyal.
    // Kelime siniri sart: "parol" ararken "PAROLOX" tam eslesme sayilmamali.
    // "allergodil burun spreyi, çözelti" -> ad virgulle de bitebilir.
    if (lower === wanted || lower.startsWith(`${wanted} `)
      || lower.startsWith(`${wanted},`)) score += 100;
    else if (lower.includes(wanted)) score += 20;
    // Ayaktan muayenede agizdan form varsayilandir; enjeksiyonluk sekli
    // doktor acikca soylemeden secme.
    const parenteralWanted = DRUG_PARENTERAL.some((form) => wanted.includes(form.trim()))
      || /damar|intraven/.test(wanted);
    if (!parenteralWanted && DRUG_PARENTERAL.some((form) => lower.includes(form))) {
      score -= 40;
    }
    // Doz soylendiyse eslesmesi sart: 500 mg istenip 325 mg secilmemeli.
    if (dose) score += lower.includes(dose) ? 60 : -80;
    // Form soylenmediyse agizdan tablet/kapsul tercih edilir.
    const formWanted = [...DRUG_ORAL, ...DRUG_PARENTERAL]
      .some((form) => wanted.includes(form.trim()))
      || /şurup|surup|süspansiyon/.test(wanted);
    if (!formWanted && DRUG_ORAL.some((form) => lower.includes(form))) score += 20;
    // Doktorun soyledigi form (burun spreyi, damla, krem...) urunde varsa
    // agizdan tablet tercihinin karsiligi: +20. Allergodil boyle esigi geciyor.
    if (DRUG_LOCAL_FORMS.some((form) => wanted.includes(form) && lower.includes(form))) score += 20;
    return score;
  }

  /** Oneri listesinden ilaci sec. Emin olunamazsa null doner ve istem
     doktora birakilir -- yanlis ilac eklemektense hic eklemeyiz. */
  async function pickDrugOption(name, dose = "") {
    const wanted = name.toLocaleLowerCase("tr-TR").trim();
    // Doz metninden sayiyi ve birimi cikar: "500 mg" -> "500 mg"
    const doseKey = String(dose || "").toLocaleLowerCase("tr-TR")
      .replace(/\s+/g, " ").trim();
    const options = await waitFor(() => {
      const found = [...document.querySelectorAll(".autocomplete__item")]
        .filter((item) => item.offsetParent !== null && textOf(item).trim());
      return found.length ? found : null;
    }, 6500);
    if (!options) return null;
    const scored = options
      .map((item) => ({item, text: textOf(item), score: scoreDrugOption(textOf(item), wanted, doseKey)}))
      .sort((a, b) => b.score - a.score);
    const best = scored[0];
    if (!best || best.score < DRUG_SCORE_THRESHOLD) return null;
    return {node: best.item, text: best.text, score: best.score};
  }

  /** Siklik: "Günlük" satirindaki "N Kez" dugmesi. Yoksa dokunulmaz.
     CANLI OLCUM: dugumler <div class="toggle-button__item xl"> seklinde. */
  function pressDailyFrequency(times) {
    if (!Number.isInteger(times) || times < 1 || times > 12) return false;
    const label = `${times} Kez`;
    const button = [...document.querySelectorAll(".toggle-button__item")]
      .find((item) => item.offsetParent !== null && textOf(item) === label)
      || [...document.querySelectorAll("button,div,span")]
        .find((item) => item.offsetParent !== null && textOf(item) === label);
    if (!button) return false;
    return pressNode(button);
  }

  /** İlac istem ekranini ac.

     CANLI OLCUM: adres ?app-action=action-order-drug olunca ekran dogrudan
     aciliyor; hizmet istemindeki gibi ayrica sekmeye basmak GEREKMIYOR --
     "co-button-Ilac Istem" adinda bir dugme sayfada hic yok (ASCII yazildi,
     testler bu adin secici olarak kullanilmadigini dogruluyor). Onceki surum
     onu 12 saniye bosuna bekliyordu. Hazir oldugunu arama kutusundan anlariz. */
  async function openDrugScreen() {
    if (!location.search.includes(DRUG_SCREEN_PARAM)) {
      const url = `${location.pathname}?${DRUG_SCREEN_PARAM}`;
      history.pushState({}, "", url);
      window.dispatchEvent(new PopStateEvent("popstate"));
      await waitFor(() => location.search.includes(DRUG_SCREEN_PARAM), 4000);
    }
    await waitForDomQuiet(document.body, 260, 3000);
    return Boolean(await waitFor(() => drugSearchInput(), 12000));
  }

  /** Arama kutusunu temizle: onceki ilacin suzgeci kalirsa yeni oneri listesi
     acilmiyor. Hizmet isteminde de ayni temizlik yapiliyor. */
  async function clearDrugSearch(search) {
    if (!search || !search.value) return;
    setTypingValue(search, " ");
    search.value = "";
    search.dispatchEvent(new Event("input", {bubbles: true}));
    await waitForDomQuiet(document.body, 240, 2000);
  }

  /** Katalog sekmesi: varsayilan "Temel İlaç". Aranan ilac orada yoksa
     "Tümü" sekmesine gecilip bir daha aranir (hizmet istemindeki
     Favoriler -> Genel yedeginin ilac karsiligi). */
  function pressAllDrugsTab() {
    const tab = [...document.querySelectorAll("button,.toggle-button__item,div,span")]
      .find((item) => item.offsetParent !== null && textOf(item) === "Tümü");
    return tab ? pressNode(tab) : false;
  }

  /** @returns {{added:number, picked:string[], skipped:string[]}}
     Neyin eklendigi ve neyin atlandigi doktora ve debug kaydina bildirilir;
     istem sessizce kaybolmamali. */
  async function fillDrugRequests(drugs = []) {
    const result = {added: 0, picked: [], skipped: []};
    if (!drugs.length) return result;
    if (!await openDrugScreen()) {
      result.skipped = drugs.map((drug) => `${drug?.name || "?"}: ilaç ekranı açılmadı`);
      return result;
    }
    for (const drug of drugs.slice(0, 10)) {
      const name = String(drug?.name || "").trim();
      if (!name) continue;
      const dose = String(drug?.dose || "").trim();
      bridgeStatus(`İlaç istemi hazırlanıyor · ${name}`);
      try {
        const search = drugSearchInput();
        if (!search) {
          result.skipped.push(`${name}: arama kutusu bulunamadı`);
          continue;
        }
        await clearDrugSearch(search);
        // Parantezli ek bilgi arama sonucunu daraltiyor: "Parol (tablet)" →
        // "Parol". Hizmet isteminde de ayni temizlik yapiliyor.
        const query = name.replace(/\(.*?\)/g, "").trim();
        /* Aramaya yalniz MARKA yazilir, puanlama tam adla yapilir. CANLI
           OLCUM (3 Kasim): "Allergodil burun spreyi" aramasi COMED'de sonuc
           vermiyor, "allergod" veriyor. */
        const searchText = query.split(/\s+/)[0] || query;
        setTypingValue(search, searchText);
        // Puanlama da aranan metinle ayni olmali: "Parol (tablet)" aranirken
        // "parol" ile puanlanmazsa marka eslesmesi hic tutmaz.
        let option = await pickDrugOption(query, dose);
        if (!option) {
          // "Temel İlaç" kategorisinde yoksa tum katalogda bir daha ara.
          if (pressAllDrugsTab()) {
            await waitForDomQuiet(document.body, 300, 3000);
            const again = drugSearchInput();
            if (again) {
              await clearDrugSearch(again);
              setTypingValue(again, searchText);
              option = await pickDrugOption(query, dose);
            }
          }
        }
        if (!option) {
          /* Guvenli taraf: ayni etken maddenin onlarca formu var (COLD, HOT,
             IV flakon, suspansiyon...). Hangisi oldugundan emin degilsek
             YANLIS ILACI EKLEMEKTENSE hic eklemeyip doktora birakiyoruz. */
          result.skipped.push(dose
            ? `${name} ${dose}: listede kesin eşleşme yok, doktor seçmeli`
            : `${name}: birden çok form var, doktor seçmeli`);
          bridgeStatus(`${name} için kesin eşleşme yok — doktor seçmeli`, "bad");
          continue;
        }
        pressNode(option.node);
        /* CANLI OLCUM: secimden sonra COMED formu kendisi dolduruyor
           (Veriliş Yolu "Ağız Yoluyla", Miktar 1, Doz 500 mg) ve bu sirada
           "Ekle" PASIF, "Sıklık Bilgisi" bolumu de henuz basilmamis oluyor.
           Sabit beklemek yetmiyordu: 1,8 sn sonra bakildiginda siklik
           dugmeleri "yok", Ekle "pasif" gorunuyordu. Artik formun HAZIR
           olmasini bekliyoruz. */
        const ready = await waitFor(() => {
          const frequencyShown = [...document.querySelectorAll(".toggle-button__item")]
            .some((item) => item.offsetParent !== null && /^\d+ Kez$/.test(textOf(item)));
          const button = dialogButton("co-button-Ekle");
          return frequencyShown && button && !button.disabled ? button : null;
        }, 15000);
        if (!ready) {
          const cancel = dialogButton("co-button-Vazgeç");
          if (cancel) pressNode(cancel);
          await waitForDomQuiet(document.body, 260, 2500);
          result.skipped.push(`${name}: form 15 sn içinde hazır olmadı`);
          bridgeStatus(`${name} formu hazırlanamadı`, "bad");
          continue;
        }
        // Doktor sadece sikligi soylemis olabilir; doz ve veris yolu COMED'in
        // varsayilaninda kalir.
        pressDailyFrequency(drug?.frequency_per_day);
        const reason = String(drug?.reason || "").trim();
        if (reason) setValue(byPlaceholder("İstem Notu / Endikasyon"), reason);
        const addButton = dialogButton("co-button-Ekle");
        if (!addButton || addButton.disabled) {
          /* Bazi ilaclar ek zorunlu alan istiyor (narkotik, kemoterapi gibi).
             Yarim birakmak yerine doktora devrediyoruz. */
          const cancel = dialogButton("co-button-Vazgeç");
          if (cancel) pressNode(cancel);
          await waitForDomQuiet(document.body, 260, 2500);
          result.skipped.push(`${name}: ek zorunlu alan istiyor, doktor tamamlamalı`);
          bridgeStatus(`${name} doktor tarafından tamamlanmalı`, "bad");
          continue;
        }
        pressNode(addButton);
        await waitForDomQuiet(document.body, 320, 4000);
        result.added += 1;
        // Hangi formun secildigi kayda gecsin: doktor imzalamadan once
        // "ben Parol dedim, bu COLD mu Tablet mi" diye bakabilsin.
        result.picked.push(option.text.slice(0, 120));
        bridgeFieldStatus("requested_drugs", true);
      } catch (error) {
        result.skipped.push(`${name}: ${error.message || "beklenmeyen hata"}`);
      }
    }
    return result;
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
      await selectDropdownOption(fieldGroupByLabel("Taraf Tipi", card), side);
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
    // Istek (5 Kasim): tedavi notu verilen ilaclari da soylemeli.
    const note = String(fields.treatment_note_v2 || "");
    const drugLines = (fields.requested_drugs || [])
      .filter((drug) => drug?.name && !note.toLocaleLowerCase("tr-TR")
        .includes(String(drug.name).split(/\s+/)[0].toLocaleLowerCase("tr-TR")))
      .map((drug) => [drug.name, drug.dose,
        drug.frequency_per_day ? `günde ${drug.frequency_per_day} kez` : null].filter(Boolean).join(" "));
    const treatmentText = [note || null,
      drugLines.length ? `Verilen ilaçlar: ${drugLines.join("; ")}.` : null,
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

    await fillOrders(fields, record);
    if (fields.pain?.exists === true) {
      await ensureTogglesOn(cardByTitle("Ağrı"), fields.pain.qualities);
    }

    return {filled, fieldResults, systemSaved: systemResult.saved};
  }

  /* Istek (4 Kasim): aktarim bitince Tanilar (ICD-10) listesi "Tümü"de
     kaliyor; hastanin eski protokollerinin onlarca tanisi gorunuyor ve doktor
     "bir suru ICD kodu yazmis" saniyordu. Sonda "Protokol" sekmesine basilir,
     yalniz bu muayenenin tanilari gorunur. Sekme bulunamazsa dokunulmaz. */
  /* CANLI OLCUM (4 Kasim): sekme ".switch-toggle" icinde gizli <input> +
     <label class="switch-toggle-label"> ciftleri. Ilk surum <span>'a basiyordu,
     tutmadi. LABEL'a click() calisiyor (Tümü 14 satir -> Protokol 3 satir).
     Secili oldugu input.checked ile dogrulanir, olmazsa bir kez daha basilir. */
  async function showProtocolDiagnoses() {
    const group = [...document.querySelectorAll(".switch-toggle")]
      .find((node) => /Protokol/.test(node.textContent)
        && /Tıbbi Bölüm/.test(node.textContent) && /Tümü/.test(node.textContent));
    if (!group) return false;
    const label = [...group.querySelectorAll("label")]
      .find((item) => item.textContent.trim() === "Protokol");
    if (!label) return false;
    const selected = () => {
      const input = label.previousElementSibling;
      return Boolean(input && input.tagName === "INPUT" && input.checked);
    };
    for (let deneme = 0; deneme < 2 && !selected(); deneme += 1) {
      label.click();
      await waitFor(selected, 2500);
      await waitForDomQuiet(document.body, 260, 2500);
    }
    return selected();
  }

  /** Istemleri sabit sirayla gir: Hizmet -> Ilac -> Tetkik.

     fillFormDraft'tan ayri fonksiyona alindi ki canli testte BIREBIR
     uretim kodu calistirilabilsin (scripts/live_order_test.py bu
     fonksiyonu dosyadan cikarip COMED sayfasinda kosturuyor). */
  async function fillOrders(fields, record) {
    /* ---------- İSTEMLER (en sonda, sabit sirayla) ----------

       Sira: muayene formu -> Hizmet Istem -> Ilac Istem -> Tetkik Istem.
       Istemler kart alanlarinin ustune ayri ekran olarak aciliyor; forma
       geri donup alan doldurmak gerekmesin diye hepsi EN SONA alindi.

       Her istem turu bitince ekran KAPATILIYOR (closeOrderScreen): ekranlar
       ust uste binince doktor sonrakini goremiyordu.

       Her istemin EKRANI sunucudan gelir (screen: "hizmet" | "tetkik").
       CANLI OLCUM (26 Ekim): Hizmet Istem katalogunda laboratuvar da var
       (CRP L101850), yani "once Hizmet'te dene" kurali laboratuvari yanlis
       ekrandan ekliyordu. Istek: EKG/EKO Hizmet Istem'de, akciger grafisi
       ve laboratuvar Tetkik Istem'de; bir istem IKI ekranda denenmez.
       Ekrani belli olmayan (eski kayit) istemlerde eski davranis: once
       Hizmet, bulunamazsa Tetkik. */
    const istemler = fields.requested_services || [];
    const hizmetler = istemler.filter((item) => item?.screen !== "tetkik");
    const tetkikler = istemler.filter((item) => item?.screen === "tetkik");
    const istemVar = istemler.length || (fields.requested_drugs || []).length;
    if (istemVar) await closeOrderScreen();

    let serviceResult = {added: 0, picked: [], skipped: [], remaining: []};
    if (hizmetler.length) {
      serviceResult = await fillServiceRequests(hizmetler);
      await closeOrderScreen();
    }
    // Ekrani "hizmet" olan istem Tetkik'e devredilmez; bulunamadiysa doktora.
    const hizmetteKalan = (serviceResult.remaining || [])
      .filter((item) => item?.screen === "hizmet");
    const kalanlar = [...tetkikler, ...(serviceResult.remaining || [])
      .filter((item) => item?.screen !== "hizmet")];

    if ((fields.requested_drugs || []).length) {
      const drugResult = await fillDrugRequests(fields.requested_drugs);
      const toplamIlac = fields.requested_drugs.length;
      // Secilen formu ve atlanan ilaclari ayrintiya yaz: doktor imzadan once
      // "Parol dedim, COLD mu Tablet mi eklendi" diye kontrol edebilsin.
      record("requested_drugs", drugResult.added > 0, [
        `${drugResult.added}/${toplamIlac} ilaç`,
        drugResult.picked.length ? `seçilen: ${drugResult.picked.join(" | ")}` : "",
        drugResult.skipped.length ? `atlanan: ${drugResult.skipped.join(" | ")}` : "",
      ].filter(Boolean).join(" — "));
      await closeOrderScreen();
    }

    if (istemler.length) {
      const studyResult = kalanlar.length
        ? await fillStudyRequests(kalanlar)
        : {added: 0, picked: [], skipped: [], remaining: []};
      if (kalanlar.length) await closeOrderScreen();
      const eklenen = serviceResult.added + studyResult.added;
      const secilen = [...serviceResult.picked, ...studyResult.picked];
      const atlanan = [...serviceResult.skipped, ...studyResult.skipped,
        ...hizmetteKalan.map((item) => `${item?.name || "?"}: ${
          item?.hizmetNotu || "Hizmet İstem'de bulunamadı"} — doktor tamamlamalı`),
        ...(studyResult.remaining || []).map((item) => `${item?.name || "?"}: ${
          item?.screen === "tetkik"
            ? "Tetkik İstem'de bulunamadı — doktor tamamlamalı"
            : item?.hizmetNotu
              ? `${item.hizmetNotu}, Tetkik İstem'de de bulunamadı — doktor tamamlamalı`
              : "hiçbir istem ekranında bulunamadı"}`)];
      record("requested_services", eklenen > 0, [
        `${eklenen}/${fields.requested_services.length} istem`,
        serviceResult.added ? `hizmet: ${serviceResult.added}` : "",
        studyResult.added ? `tetkik: ${studyResult.added}` : "",
        secilen.length ? `seçilen: ${secilen.join(" | ")}` : "",
        atlanan.length ? `atlanan: ${atlanan.join(" | ")}` : "",
      ].filter(Boolean).join(" — "));
    }
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
      });
      // Tum alanlar eklenti uzerinden doldurulur. Dogrulanmis POST sablonu
      // akisi kaldirildi: her protokolde sablon bulunmadigi icin davranis
      // ongorulemez oluyor ve doktora "POST sablonu yok" gibi anlamsiz
      // mesajlar gidiyordu.
      const formResult = await fillFormDraft(transfer, {skipDiagnoses: false});
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
      if (!formResult.filled) {
        throw new Error("COMED form alanları bulunamadı; kartı yenileyip tekrar deneyin");
      }
      bridgeStatus("Son alanlar doğrulanıyor");
      await waitForDomQuiet(document.body, 400, 3500);
      // En son adim: Tanilar listesini bu protokole al, sonra "Aktarım bitti".
      await showProtocolDiagnoses();
      const unresolved = formResult.fieldResults.filter(
        (item) => !["filled", "saved", "reused"].includes(item.status),
      );
      const mode = "eklenti form doldurma";
      const note = `${mode}; ${formResult.filled} alan işlendi${unresolved.length
        ? `, ${unresolved.length} alan doktor kontrolüne bırakıldı`
        : " ve tarayıcı güncellemeleri tamamlandı"}. Doktor Kaydet/İmzala kontrolünü yapmalıdır.`;
      const debug = {
        started_at: startedAt,
        finished_at: new Date().toISOString(),
        mode,
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
      // Sure ve hiz yaziliyor ki doktor hiz ayarinin ise yarayip
      // yaramadigini tahmin etmek yerine rakamla gorsun.
      const gecen = Math.round((Date.now() - Date.parse(startedAt)) / 1000);
      const hizEtiketi = FILL_SPEEDS.find((item) => item.value === fillSpeed)?.label
        || `${fillSpeed}×`;
      /* Doldurulamayan alan varsa bunu balonda SOYLE. Onceden "Aktarım bitti"
         yaziyordu ve doktor hicbir ilacin eklenmedigini ancak COMED'e bakinca
         anliyordu; sessiz basarisizlik yanlis guven veriyor. */
      bridgeStatus(
        `${BRIDGE_FINAL_TEXT} · ${gecen} sn · ${hizEtiketi} hız`
        + (unresolved.length ? ` · ${unresolved.length} alan eksik` : ""),
        unresolved.length ? "bad" : "ok",
      );
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

  /* ---- gorunmez cerceveyle kimlik toplama ----
     COMED is listesinde T.C. kimlik numarasi yok; kimlik yalnizca hasta
     kartinda, HASTA ADINA tiklayinca acilan "Hasta Bilgileri" panelinde
     yaziyor. Hastanin randevusu bu yuzden doktor karti acana kadar
     baglanamiyordu.

     Cozum: is listesi sayfasinin icinde, ekrandan tamamen gizli bir
     <iframe> ile karti yukluyoruz; hasta adina tiklayip kimligi okuyor ve
     cerceveyi siliyoruz. Yeni sekme ACILMAZ, doktor hicbir sey gormez,
     oturum ayni sekmede oldugu icin yeniden giris de gerekmez. */
  /* Ayni hastayi tur tur denemeyelim; ama BASARISIZ bir deneme de kalici
     olmamali. Eskiden visit_id denemeden ONCE isaretleniyordu: kart yavas
     yuklendiyse (30 sn asim) ya da panel acilmadiysa o hasta, doktor sayfayi
     yenileyene kadar bir daha hic denenmiyordu. Simdi deneme sayisi
     tutuluyor -- basarisizlik sinirli sayida tekrarlanir, basari kalici
     olarak kapatir. */
  const IDENTITY_MAX_TRIES = 3;
  const identityTried = new Map();     // visit_id -> deneme sayisi
  let identityFrameBusy = false;

  function frameWaitFor(getter, timeoutMs) {
    return new Promise((resolve) => {
      const deadline = Date.now() + timeoutMs;
      const tick = () => {
        let value = null;
        try { value = getter(); } catch (_) { value = null; }
        if (value) return resolve(value);
        if (Date.now() >= deadline) return resolve(null);
        setTimeout(tick, 300);
      };
      tick();
    });
  }

  /** Kart belgesinden T.C. kimlik ve dogum tarihini oku.

     Burada eskiden govdedeki ILK 11 haneli sayi ve ILK tarih aliniyordu.
     Kartta bunlardan bolca var -- telefon 0XXXXXXXXXX tam 11 hane, gelis
     tarihi, protokol numarasi -- ve hepsi panel ACILMADAN da DOM'da duruyor.
     Bu yuzden bekleme, panel acilmadan hemen YANLIS bir kimlikle doniyordu.
     Sunucuya hatali ozet yazilinca hasta randevusuna baglanamiyor, kayit
     "kimligi tamam" sayildigi icin bir daha da denenmiyordu; yalnizca doktor
     karti elle acinca dogrusuyla uzerine yaziliyordu. Kullanicinin tarif
     ettigi "bazen kartin icine girip yenileyince esliyor" tam olarak buydu.

     Artik cerceve okumasi da panel okumasiyla AYNI etiketli ayristiriciyi
     kullaniyor: "T.C. ..." ve "Dogum Tarihi ..." etiketleri yoksa kimlik yok
     sayilir. Panel gercekten acilana kadar beklenir. */
  function readIdentityFromDocument(doc) {
    const {tckn, birth_date} = parsePatientIdentity(doc);
    return {tckn, birth_date};
  }

  /** Bir hastanin kimligini gorunmez cercevede okuyup sunucuya yolla. */
  async function collectIdentityInFrame(item) {
    const url = item.clinical_card_url || cardUrlForVisit(item.visit_id);
    if (!url) return false;
    const frame = document.createElement("iframe");
    frame.setAttribute("aria-hidden", "true");
    frame.setAttribute("tabindex", "-1");
    // Ekran disinda ve tiklanamaz: doktorun gorsel akisina hic girmez.
    frame.style.cssText = "position:fixed;left:-20000px;top:0;width:1500px;"
      + "height:1000px;opacity:0;border:0;pointer-events:none;visibility:hidden";
    document.body.appendChild(frame);
    try {
      frame.src = url;
      // 1) Kart yuklensin: hasta adi govdede gorunene kadar bekle.
      const ad = String(item.patient_name || "").trim().split(/\s+/)[0] || "";
      const adOgesi = await frameWaitFor(() => {
        const doc = frame.contentDocument;
        if (!doc?.body) return null;
        const adaylar = [...doc.body.querySelectorAll("*")].filter(
          (el) => el.children.length === 0 && el.textContent
            && (ad ? el.textContent.includes(ad) : false),
        );
        return adaylar[0] || null;
      }, 30000);
      if (!adOgesi) return false;
      // 2) HASTA ADINA TIKLA -> "Hasta Bilgileri" paneli acilir.
      adOgesi.click();
      // 3) Kimlik gorunene kadar bekle.
      const kimlikBekle = (sure) => frameWaitFor(() => {
        const value = readIdentityFromDocument(frame.contentDocument);
        return value.tckn && value.birth_date ? value : null;
      }, sure);
      let identity = await kimlikBekle(9000);
      if (!identity) {
        /* Ad tiklamasi her kurulumda paneli acmiyor. Acik hasta kartinda
           calistigi olculen ikinci yol -- profil ikonu -- burada da denenir;
           cerceve gizli oldugu icin doktor hicbir sey gormez. */
        const ikon = frame.contentDocument
          ?.querySelector('[data-test="co-button-icon-patient-profile"]');
        if (ikon) {
          activateNode(ikon);   // dosyanin her yerinde kullanilan tiklama
          identity = await kimlikBekle(9000);
        }
      }
      if (!identity) return false;
      await request("/api/v1/mobile/comed/worklist/sync", {
        method: "POST",
        body: JSON.stringify({
          items: [{
            visit_id: item.visit_id,
            clinical_card_id: "",
            patient_name: item.patient_name || "COMED hastası",
            patient_no: item.patient_no || "",
            clinical_card_url: url,
            tckn: identity.tckn,
            birth_date: identity.birth_date,
          }],
          replace: false,
        }),
      });
      return true;
    } catch (_) {
      return false;
    } finally {
      frame.remove();                 // izi kalmasin
    }
  }

  /** Is listesindeyken kimligi eksik hastalari sessizce tamamla. */
  async function collectMissingIdentities() {
    if (identityFrameBusy) return;
    let bekleyen;
    try {
      bekleyen = await request("/api/v1/mobile/comed/worklist/missing-identity");
    } catch (_) {
      return;                         // sunucu eski surumse sessiz gec
    }
    const hedef = (bekleyen?.items || []).find(
      (item) => item.visit_id
        && (identityTried.get(String(item.visit_id)) || 0) < IDENTITY_MAX_TRIES,
    );
    if (!hedef) return;
    const anahtar = String(hedef.visit_id);
    identityFrameBusy = true;         // ayni anda tek cerceve
    try {
      const basarili = await collectIdentityInFrame(hedef);
      identityTried.set(anahtar, basarili
        ? IDENTITY_MAX_TRIES                       // oldu, bir daha bakma
        : (identityTried.get(anahtar) || 0) + 1);  // olmadi, tekrar denenebilir
    } finally {
      identityFrameBusy = false;
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
        // Yeni kartta kimlik paneli bir kez daha acilabilmeli.
        identityPanelTried = false;
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
        // Kimligi eksik hastalari arka planda tamamla: hasta, doktor karti
        // acmadan da randevusuna baglanabilsin.
        await collectMissingIdentities();
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
    /* "COMED'e aktar" doktorun acik sekmesini hasta kartina yonlendiriyor.
       COMED'de yarim kalmis bir form varsa tarayici "Siteden cikilsin mi?"
       diye soruyor ve doktor her aktarimda bu kutuyla ugrasiyordu. Bayragi
       kuruyoruz; page_trace.js document_start'ta kurdugu dinleyiciyle bir
       sonraki cikisi sessizce geciriyor. Yonlendirme Klinot'un kendi
       istegidir, doktor veri kaybetmez: kart zaten ayni hastaya acilir. */
    if (message?.type === "klinot-suppress-unload-prompt") {
      try {
        sessionStorage.setItem(SUPPRESS_RELOAD_PROMPT_KEY, String(Date.now()));
        sendResponse({ok: true});
      } catch (_) {
        sendResponse({ok: false});
      }
      return false;
    }
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
