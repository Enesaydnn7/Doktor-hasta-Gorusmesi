(() => {
  const CARD_RE = /\/hasta-tibbi-karti\/(\d+)\/patient-clinical-card\/(\d+)\/?/;
  let activeTransferId = null;
  let busy = false;

  function request(path, options = {}) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({type: "klinot-request", path, options}, (response) => {
        if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
        if (!response?.ok) return reject(new Error(response?.error || "Köprü isteği başarısız"));
        resolve(response.data);
      });
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
        font: "600 12px system-ui", boxShadow: "0 8px 28px #0003", maxWidth: "300px",
      });
      document.body.appendChild(box);
    }
    box.style.background = state === "ok" ? "#087454" : state === "bad" ? "#b5322d" : "#3158c8";
    box.textContent = `Klinot · ${text}`;
  }

  function textOf(root) {
    return (root?.innerText || "").replace(/\s+/g, " ").trim();
  }

  function parseWorklist() {
    const seen = new Set();
    return [...document.querySelectorAll(`a[href*="/hasta-tibbi-karti/"]`)].map((anchor) => {
      const match = anchor.href.match(CARD_RE);
      if (!match || seen.has(match[1])) return null;
      seen.add(match[1]);
      const row = anchor.closest("tr,[role=row],.v-data-table__tr,.row") || anchor.parentElement?.parentElement;
      const raw = textOf(row);
      const image = row?.querySelector("img[alt]");
      const protocol = raw.match(/V-\d+/)?.[0] || `V-${match[1]}`;
      const patientNo = raw.match(/(?:Hasta\s*No[:\s]*|\|\s*)(\d{4,})/i)?.[1] || "";
      const name = image?.alt || raw.split(protocol)[0].replace(/\b\d{1,3}yıl\b.*$/i, "").trim();
      return {
        visit_id: match[1], clinical_card_id: match[2], patient_id: patientNo,
        patient_name: name || "COMED hastası", patient_no: patientNo, protocol_no: protocol,
        department: raw.match(/(?:Kardiyoloji|Dermatoloji|İç Hastalıkları|Genel Cerrahi|Ortopedi|Nöroloji)/i)?.[0] || "",
        doctor_name: "", task: raw, status: /Bekliyor/i.test(raw) ? "Bekliyor" : "",
        clinical_card_url: anchor.href,
      };
    }).filter(Boolean);
  }

  async function syncWorklist() {
    const items = parseWorklist();
    if (!items.length) return;
    try {
      await request("/api/v1/mobile/comed/worklist/sync", {
        method: "POST", body: JSON.stringify({items}),
      });
      bridgeStatus(`${items.length} hasta iş listesine eşitlendi`, "ok");
    } catch (error) {
      bridgeStatus(error.message, "bad");
    }
  }

  function setValue(element, value) {
    if (!element || value === null || value === undefined || value === "") return false;
    const proto = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    setter?.call(element, String(value));
    element.dispatchEvent(new Event("input", {bubbles: true}));
    element.dispatchEvent(new Event("change", {bubbles: true}));
    element.dispatchEvent(new Event("blur", {bubbles: true}));
    return true;
  }

  function byPlaceholder(value) {
    return [...document.querySelectorAll("input,textarea")]
      .find((el) => (el.getAttribute("placeholder") || "").trim().toLocaleLowerCase("tr-TR") === value.toLocaleLowerCase("tr-TR"));
  }

  function inputAfterLabel(label) {
    const labelNode = [...document.querySelectorAll("label,span,div")]
      .find((el) => el.children.length < 4 && textOf(el) === label);
    const scope = labelNode?.closest("div")?.parentElement || labelNode?.parentElement;
    return scope?.querySelector("input:not([disabled]),textarea:not([disabled])") || null;
  }

  function clickText(text, root = document) {
    const node = [...root.querySelectorAll("button,label,[role=radio],[role=checkbox],span")]
      .find((el) => textOf(el) === text && el.offsetParent !== null);
    if (!node) return false;
    node.click();
    return true;
  }

  async function updateStatus(id, status, error = null) {
    return request(`/api/v1/mobile/comed/bridge/transfers/${id}/status`, {
      method: "POST", body: JSON.stringify({status, error}),
    });
  }

  async function fillTransfer(transfer) {
    if (busy || !transfer?.bundle) return;
    busy = true;
    activeTransferId = transfer.id;
    await updateStatus(transfer.id, "filling");
    bridgeStatus("COMED alanları dolduruluyor");
    try {
      const requestSpec = transfer.bundle.requests?.find((item) => item.section === "examination") || {};
      const f = requestSpec.fields || {};
      setValue(byPlaceholder("Şikayeti"), f.patient_complaint);
      setValue(byPlaceholder("Öykü"), f.patient_story);
      setValue(byPlaceholder("Sistem Sorgusu"), f.review_of_system_simple);
      setValue(byPlaceholder("Muayene Notu"), f.exam_simple_textarea);
      setValue(byPlaceholder("Tedavi Notu"), f.treatment_note_v2);

      const duration = f.complaint_start_date;
      if (duration?.value) {
        const startArea = [...document.querySelectorAll("div")].find((el) => textOf(el) === "Başlangıç Tarihi")?.parentElement;
        setValue(startArea?.querySelector("input"), duration.value);
        const units = {hour: "saat", day: "gün", week: "hafta", month: "ay", year: "yıl"};
        clickText(units[duration.unit], startArea?.parentElement || document);
      }

      const vitals = f.vitals || {};
      [["Kilo (kg)", vitals.weight], ["Boy (cm)", vitals.height], ["Ateş", vitals.temperature_v2],
       ["Nabız", vitals.pulse], ["KB-S", vitals.pressure_systolic], ["KB-D", vitals.pressure_diastolic],
       ["SPO2", vitals.spo2]].forEach(([label, value]) => setValue(inputAfterLabel(label), value));

      if (f.fall_risk === true) clickText("Var", [...document.querySelectorAll("div")].find((el) => textOf(el) === "Düşme Riski")?.parentElement?.parentElement || document);
      if (f.fall_risk === false) clickText("Yok", [...document.querySelectorAll("div")].find((el) => textOf(el) === "Düşme Riski")?.parentElement?.parentElement || document);
      if (f.pain?.exists === true) clickText("Var", [...document.querySelectorAll("div")].find((el) => textOf(el) === "Ağrı")?.parentElement?.parentElement || document);
      if (f.pain?.exists === false) clickText("Yok", [...document.querySelectorAll("div")].find((el) => textOf(el) === "Ağrı")?.parentElement?.parentElement || document);
      if (f.profile?.no_known_history === true) {
        [...document.querySelectorAll("button")].filter((button) => textOf(button) === "Özellik Yok").forEach((button) => button.click());
      }
      if (f.treatment_plan_label) clickText(f.treatment_plan_label);
      if (f.is_surgery_will_planned === true) clickText("Evet", [...document.querySelectorAll("div")].find((el) => textOf(el) === "Ameliyat Planlanacak mı?")?.parentElement || document);
      if (f.is_surgery_will_planned === false) clickText("Hayır", [...document.querySelectorAll("div")].find((el) => textOf(el) === "Ameliyat Planlanacak mı?")?.parentElement || document);

      await updateStatus(transfer.id, "ready_for_review");
      bridgeStatus("Alanlar aktarıldı · doktor kontrolü bekleniyor", "ok");
    } catch (error) {
      await updateStatus(transfer.id, "failed", error.message).catch(() => {});
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
      if (payload.items?.length) await fillTransfer(payload.items[0]);
    } catch (error) {
      if (!/bağlı değil/i.test(error.message)) bridgeStatus(error.message, "bad");
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!activeTransferId || !button || textOf(button) !== "Kaydet") return;
    const id = activeTransferId;
    setTimeout(() => {
      const success = /Kayıt başarılı/i.test(document.body.innerText);
      if (success) {
        updateStatus(id, "completed").catch(() => {});
        bridgeStatus("COMED kaydı tamamlandı", "ok");
        activeTransferId = null;
      }
    }, 1800);
  }, true);

  if (location.pathname.replace(/\/$/, "") === "/tr-tr/medical") {
    setTimeout(syncWorklist, 2500);
    setInterval(syncWorklist, 60000);
  }
  if (CARD_RE.test(location.pathname)) {
    setTimeout(pollTransfer, 2500);
    setInterval(pollTransfer, 5000);
  }
})();
