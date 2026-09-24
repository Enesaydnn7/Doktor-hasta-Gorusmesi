(() => {
  const CARD_RE = /\/hasta-tibbi-karti\/(\d+)\/patient-clinical-card\/(\d+)\/?/;
  const WORKLIST_RE = /\/medical(?:\/hasta-tibbi-karti)?\/?$/;
  const SELECTED_PATIENT_KEY = "klinot-comed-selected-patient";
  const ACTIVE_TRANSFER_KEY = "klinot-comed-active-transfer";
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
      return url.protocol === "http:"
        && url.hostname === "goztepe.comedtestapi.mlpcare.com"
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

  function bridgeStatus(text, state = "idle") {
    let box = document.getElementById("klinot-comed-bridge");
    if (!box) {
      box = document.createElement("div");
      box.id = "klinot-comed-bridge";
      Object.assign(box.style, {
        position: "fixed", right: "18px", bottom: "66px", zIndex: "2147483647",
        padding: "10px 13px", borderRadius: "12px", color: "#fff",
        font: "600 12px system-ui", boxShadow: "0 8px 28px #0003", maxWidth: "340px",
      });
      document.body.appendChild(box);
    }
    box.style.background = state === "ok" ? "#087454" : state === "bad" ? "#b5322d" : "#3158c8";
    box.textContent = `Klinot · ${text}`;
  }

  function textOf(root) {
    return (root?.innerText || "").replace(/\s+/g, " ").trim();
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
    const patientName = patientCell?.querySelector("img[alt]")?.alt
      || patientLines[0] || "COMED hastası";
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
      patient_name: headerText.match(/^([^|\n]{3,80})/)?.[1]?.trim() || "COMED hastası",
      patient_no: headerText.match(/Hasta\s*No[:\s]*(\d+)/i)?.[1] || "",
      protocol_no: `V-${match[1]}`,
      task: "Açık hasta tıbbi kartı",
    };
    const item = {
      ...fallback,
      ...(selected?.visit_id === match[1] ? selected : {}),
      visit_id: match[1],
      clinical_card_id: match[2],
      clinical_card_url: location.href,
    };
    await request("/api/v1/mobile/comed/worklist/sync", {
      method: "POST", body: JSON.stringify({items: [item], replace: false}),
    });
    sessionStorage.removeItem(SELECTED_PATIENT_KEY);
  }

  async function syncWorklist() {
    const items = parseWorklist();
    try {
      await request("/api/v1/mobile/comed/worklist/sync", {
        method: "POST", body: JSON.stringify({items, replace: true}),
      });
      bridgeStatus(
        items.length ? `${items.length} hasta iş listesine eşitlendi` : "İş listesi boş olarak eşitlendi",
        "ok",
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
    if (exists === false) return clickCardOption("Düşme Riski", "Yok");
    if (exists !== true || typeof value !== "object") return false;
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
      const opener = [...document.querySelectorAll("button")]
        .find((button) => textOf(button) === "Sistem Sorgulama" && button.offsetParent !== null);
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
      return ok;
    };
    const write = (field, element, value) => {
      record(field, setValue(element, value));
    };

    const systemResult = await fillSystemInquiry(fields.review_of_system || {});
    systemResult.fields.forEach((field) => fieldResults.push({
      field, channel: "extension", status: "filled",
      source: fallbackFields.has(field.split(".").slice(0, 2).join("."))
        ? "operational_default" : "analysis",
    }));
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

  async function postTransfer(transfer) {
    if (busy || !transfer?.bundle) return;
    busy = true;
    activeTransferId = transfer.id;
    bridgeStatus("COMED taslağı hazırlanıyor");
    const startedAt = new Date().toISOString();
    try {
      await updateStatus(transfer.id, "filling", null, {
        started_at: startedAt,
        stage: "starting",
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
      bridgeStatus(unresolved.length
        ? `Aktarım bitti · ${unresolved.length} alan doktor kontrolünde`
        : "Aktarım bitti · doktor kontrolü bekleniyor", "ok");
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
      }
      if (WORKLIST_RE.test(path)) {
        if (routeChanged || Date.now() - lastWorklistSyncAt >= 60000) {
          await syncWorklist();
          lastWorklistSyncAt = Date.now();
        }
        await openPendingTransferFromWorklist();
      } else if (CARD_RE.test(path)) {
        if (routeChanged) await syncCurrentCard();
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
    if (!activeTransferId || !button || !/^Kaydet(?: ve İmzala)?$/.test(textOf(button))) return;
    const id = activeTransferId;
    setTimeout(() => {
      const success = /Kayıt başarılı/i.test(document.body.innerText);
      if (success) {
        updateStatus(id, "completed").catch(() => {});
        bridgeStatus("COMED kaydı tamamlandı", "ok");
        sessionStorage.removeItem(ACTIVE_TRANSFER_KEY);
        activeTransferId = null;
      }
    }, 1800);
  }, true);

  setTimeout(monitorRoute, 1500);
  setInterval(monitorRoute, 5000);
})();
