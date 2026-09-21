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

  async function updateStatus(id, status, error = null) {
    return request(`/api/v1/mobile/comed/bridge/transfers/${id}/status`, {
      method: "POST", body: JSON.stringify({status, error}),
    });
  }

  async function postTransfer(transfer) {
    if (busy || !transfer?.bundle) return;
    busy = true;
    activeTransferId = transfer.id;
    bridgeStatus("COMED kayıt POST'ları gönderiliyor");
    try {
      await updateStatus(transfer.id, "filling");
      if (transfer.bundle.execution_mode !== "native_api_post") {
        throw new Error("Bu aktarım paketi doğrudan COMED POST biçiminde değil");
      }
      const nativeRequests = transfer.bundle.native_requests || [];
      if (!nativeRequests.length) {
        const detail = (transfer.bundle.manual_review_notes || [])[0]
          || "Bu protokol için doğrulanmış COMED POST gövdesi bulunamadı";
        throw new Error(detail);
      }
      const results = await executeNativePosts(transfer.visit_id, nativeRequests);
      const warnings = (transfer.bundle.manual_review_notes || []).join(" ").slice(0, 1000) || null;
      await updateStatus(transfer.id, "ready_for_review", warnings);
      sessionStorage.setItem(ACTIVE_TRANSFER_KEY, String(transfer.id));
      bridgeStatus(`${results.length} COMED POST tamamlandı · doktor kontrolü bekleniyor`, "ok");
      setTimeout(() => location.reload(), 1400);
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
