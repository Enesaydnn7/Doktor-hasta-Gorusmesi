(() => {
  const CARD_RE = /\/hasta-tibbi-karti\/(\d+)\/patient-clinical-card\/(\d+)\/?/;
  const WORKLIST_RE = /\/medical(?:\/hasta-tibbi-karti)?\/?$/;
  const SELECTED_PATIENT_KEY = "klinot-comed-selected-patient";
  const ACTIVE_TRANSFER_KEY = "klinot-comed-active-transfer";
  const TRACE_SOURCE = "klinot-comed-trace-v1";
  const NATIVE_COMMAND_SOURCE = "klinot-comed-native-command-v1";
  const NATIVE_RESULT_SOURCE = "klinot-comed-native-result-v1";
  const NATIVE_TIMEOUT_MS = 45000;

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

  function ensureCardOpen(title, visiblePlaceholder = null) {
    const card = cardByTitle(title);
    if (!card || (visiblePlaceholder && byPlaceholder(visiblePlaceholder, card)?.offsetParent)) {
      return card;
    }
    const editorAlreadyVisible = [...card.querySelectorAll(
      "input,textarea,table,.autocomplete__input",
    )].some((element) => element.offsetParent !== null);
    if (editorAlreadyVisible) return card;
    const heading = [...card.querySelectorAll(".hasta-detay-card__title,[data-test],span,div")]
      .find((node) => textOf(node) === title);
    heading?.click();
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

  function clickText(text, root = document) {
    const node = [...root.querySelectorAll(
      "button,label,[role=radio],[role=checkbox],.toggle-button__item,.autocomplete__item,span",
    )].find((element) => textOf(element) === text && element.offsetParent !== null);
    if (!node) return false;
    node.click();
    return true;
  }

  function clickCardOption(cardTitle, text) {
    const card = cardByTitle(cardTitle);
    return card ? clickText(text, card) : false;
  }

  function clickFieldOption(label, text, root = document) {
    const group = fieldGroupByLabel(label, root);
    return group ? clickText(text, group) : false;
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
      await sleep(120);
    }
    return added;
  }

  function durationUnitLabel(unit) {
    return ({hour: "saat", day: "gün", week: "hafta", month: "ay", year: "yıl"})[unit];
  }

  function fillDuration(root, duration) {
    if (!root || !duration?.value) return false;
    const input = root.querySelector(".co-date-before input.form-control, input.form-control");
    if (!setValue(input, duration.value)) return false;
    const unit = durationUnitLabel(duration.unit);
    if (unit) clickText(unit, root);
    return true;
  }

  async function fillFallRisk(value) {
    const exists = typeof value === "object" ? value?.exists : value;
    if (exists === false) return clickCardOption("Düşme Riski", "Yok");
    if (exists !== true || typeof value !== "object") return false;
    const detailKeys = ["history", "medications", "addiction", "gait_balance_disorder",
      "vision_disorder", "oriented", "general_health_normal"];
    if (!detailKeys.every((key) => typeof value[key] === "boolean")
      || !["65_plus", "under_65"].includes(value.age_group)) return false;
    if (!clickCardOption("Düşme Riski", "Var")) return false;
    const popover = await waitFor(() => [...document.querySelectorAll(".co-popover.bottom,.co-popover")]
      .find((item) => item.offsetParent !== null));
    if (!popover) return false;
    const choices = [
      ["Yaş", value.age_group === "65_plus", "65 yaş üstü", "65 yaş altı"],
      ["Düşme Hikayesi", value.history, "Var", "Yok"],
      ["Kullandığı İlaçlar", value.medications, "Var", "Yok"],
      ["Alkol / Madde Bağımlılığı", value.addiction, "Var", "Yok"],
      ["Yürüyüş ve Denge Bozuklukları", value.gait_balance_disorder, "Var", "Yok"],
      ["Görme Bozukluğu", value.vision_disorder, "Var", "Yok"],
      ["Ruhsal Durum", value.oriented, "Oryante", "Oryante Değil"],
      ["Genel Sağlık Durumu", value.general_health_normal, "Normal", "Normal Değil"],
    ];
    choices.forEach(([label, selected, yes, no]) => {
      clickFieldOption(label, selected ? yes : no, popover);
    });
    return true;
  }

  async function fillPain(pain) {
    if (pain?.exists === false) return clickCardOption("Ağrı", "Yok");
    if (pain?.exists !== true) return false;
    const card = cardByTitle("Ağrı");
    if (!card || !clickText("Var", card)) return false;
    await sleep(100);
    setValue(byPlaceholder("Bölge", card), pain.location);
    setValue(byPlaceholder("Açıklama", card), pain.description);
    (pain.qualities || []).forEach((quality) => clickText(quality, card));
    if (pain.rhythm) clickText(pain.rhythm, card);
    if (pain.start_date) fillDuration(card, pain.start_date);
    return true;
  }

  async function fillFamilyHistory(profile = {}) {
    if (profile.no_known_family_history === true) {
      return clickCardOption("Soygeçmiş", "Özellik Yok") ? 1 : 0;
    }
    const entries = profile.family_history || [];
    if (!entries.length && typeof profile.parents_related !== "boolean") return 0;
    const card = ensureCardOpen("Soygeçmiş");
    if (!card) return 0;
    await waitFor(() => [...card.querySelectorAll("input,textarea,table")]
      .find((element) => element.offsetParent !== null), 1800);
    let added = 0;
    for (const entry of entries) {
      const relationship = String(entry?.relationship || "").trim();
      const condition = String(entry?.condition || "").trim();
      const row = [...card.querySelectorAll("tr")]
        .find((candidate) => textOf(candidate.querySelector("td,th")) === relationship);
      const headers = [...card.querySelectorAll("thead th")].map(textOf);
      const column = headers.indexOf(condition);
      const cells = [...(row?.querySelectorAll("td") || [])];
      const target = column >= 0 ? cells[column] : null;
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
    const history = ensureCardOpen("Özgeçmiş", "Meslek");
    if (!history) return filled;
    await sleep(100);
    for (const item of profile.addictions || []) {
      const {name, description} = itemParts(item);
      const value = name.toLocaleLowerCase("tr-TR");
      if (value.includes("sigara") && clickText("Sigara", history)) filled += 1;
      if (value.includes("alkol") && clickText("Alkol", history)) filled += 1;
      if (value.includes("madde") && clickText("Madde", history)) filled += 1;
      if (setValue(byPlaceholder("Açıklama", fieldGroupByLabel("Alışkanlık", history) || history), description)) filled += 1;
    }
    const lookupMap = [
      ["Kronik Hastalık", profile.diseases], ["İlaç", profile.pharmacy_products],
      ["Alerji", profile.allergies], ["Ameliyat", profile.operations],
      ["Özel Durumlar", profile.special_conditions], ["Aşı", profile.vaccines],
      ["Cihaz (Vücuda Takılan)", profile.devices],
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
    filled += await fillFamilyHistory(profile);
    return filled;
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
    let filled = 0;
    const write = (element, value) => {
      if (setValue(element, value)) filled += 1;
    };

    const complaintCard = cardByTitle("Yakınması") || document;
    write(byPlaceholder("Şikayeti", complaintCard), fields.patient_complaint);
    write(byPlaceholder("Öykü", complaintCard), fields.patient_story);
    if (fillDuration(complaintCard, fields.complaint_start_date)) filled += 1;
    write(byPlaceholder("Sistem Sorgusu", cardByTitle("Sistem Sorgusu") || document), fields.review_of_system_simple);

    const examCard = cardByTitle("Fizik Muayene Bulguları") || document;
    write(byPlaceholder("Muayene Notu", examCard), fields.exam_simple_textarea);
    const vitals = fields.vitals || {};
    [["Kilo (kg)", vitals.weight], ["Boy (cm)", vitals.height], ["Ateş", vitals.temperature_v2],
      ["Nabız", vitals.pulse], ["KB-S", vitals.pressure_systolic], ["KB-D", vitals.pressure_diastolic],
      ["SPO2", vitals.spo2]].forEach(([label, value]) => write(inputByLabel(label, examCard), value));

    const planCard = cardByTitle("İzlem ve Plan") || document;
    const treatmentText = [fields.treatment_note_v2,
      fields.control_note ? `Kontrol notu: ${fields.control_note}` : null]
      .filter(Boolean).join("\n");
    write(byPlaceholder("Tedavi Notu", planCard), treatmentText);

    filled += await fillProfile(fields.profile || {});
    if (fillPsychologicalStatus(fields.psychological_status || {})) filled += 1;
    if (await fillFallRisk(fields.fall_risk)) filled += 1;
    if (await fillPain(fields.pain)) filled += 1;
    if (!skipDiagnoses) filled += await fillDiagnoses(fields.diagnoses || []);
    if (fields.treatment_plan_label && clickCardOption("İzlem ve Plan", fields.treatment_plan_label)) filled += 1;
    if (fields.is_surgery_will_planned === true
      && clickFieldOption("Ameliyat Planlanacak mı?", "Evet", planCard)) filled += 1;
    if (fields.is_surgery_will_planned === false
      && clickFieldOption("Ameliyat Planlanacak mı?", "Hayır", planCard)) filled += 1;
    const controlSwitch = planCard.querySelector(
      '[data-test="co-switch-Kontrol Önerilme Durumu"] input[type="checkbox"], input[type="checkbox"]',
    );
    if (typeof fields.is_control_suggested === "boolean" && controlSwitch
      && controlSwitch.checked !== fields.is_control_suggested) {
      controlSwitch.click();
      filled += 1;
    }
    return {filled};
  }

  async function updateStatus(id, status, error = null) {
    return request(`/api/v1/mobile/comed/bridge/transfers/${id}/status`, {
      method: "POST", body: JSON.stringify({status, error}),
    });
  }

  async function postTransfer(transfer) {
    if (busy || !transfer?.bundle) return;
    busy = true;
    activeTransferId = transfer.id;
    bridgeStatus("COMED taslağı hazırlanıyor");
    try {
      await updateStatus(transfer.id, "filling");
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
      if (!postResults.length && !formResult.filled) {
        throw postError || new Error("COMED form alanları bulunamadı; kartı yenileyip tekrar deneyin");
      }
      const mode = postResults.length
        ? "POST + form tamamlama"
        : postError ? "POST fallback + eklenti form doldurma" : "eklenti form doldurma";
      const note = `${mode}; ${formResult.filled} alan hazırlandı. Doktor Kaydet/İmzala kontrolünü yapmalıdır.`;
      await updateStatus(transfer.id, "ready_for_review", note);
      sessionStorage.setItem(ACTIVE_TRANSFER_KEY, String(transfer.id));
      bridgeStatus(`${formResult.filled} alan hazırlandı · doktor kontrolü bekleniyor`, "ok");
    } catch (error) {
      await updateStatus(transfer.id, "failed", error.message).catch(() => {});
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
    if (!activeTransferId || !button || textOf(button) !== "Kaydet") return;
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
