/* ================= Doktor paneli =================
   Yonetici paneliyle ayni duzen ve ayni rapor katmani (report_view.js).
   Fark: veriler /doctor/api/* uclarindan gelir ve yalnizca bu doktora
   atanmis kayitlari icerir. */

let overview = {records: [], worklist: [], stats: {}};
const cache = {};              // id -> tam kayit
let selectedPatient = null;    // COMED aktarimi icin secili hasta
let activeTransfer = null;
let refreshTimer = null;
let transferTimer = null;
let loading = false;

const $ = (id) => document.getElementById(id);

function toast(message, error = false) {
  const el = $("toast");
  el.textContent = message;
  el.className = error ? "show error" : "show";
  setTimeout(() => el.className = "", 4500);
}

async function json(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? {"Content-Type": "application/json"} : {}),
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
  return data;
}

function patientKey(p) { return String(p?.visit_id || ""); }

function linkedPatient(record) {
  const linked = (record?.metadata || {}).comed_patient || {};
  if (linked.visit_id) return linked;
  return selectedPatient || null;
}

/* ---------- ust serit ---------- */
function renderStats() {
  const stat = overview.stats || {};
  $("stat-worklist").textContent = overview.worklist.length;
  $("stat-records").textContent = stat.kayit ?? overview.records.length;
  $("stat-token").textContent = Number(stat.token || 0).toLocaleString("tr-TR");
  $("stat-cost").textContent = fmtUsd(stat.cost_usd);
}

/* ---------- COMED is listesi ---------- */
function renderWorklist() {
  $("worklist-count").textContent = `${overview.worklist.length} hasta`;
  $("worklist").innerHTML = overview.worklist.length
    ? overview.worklist.map((p, i) => `<button class="patient-card ${patientKey(p) === patientKey(selectedPatient) ? "selected" : ""}" data-patient="${i}">
        <span class="patient-avatar">${esc((p.patient_name || "H").trim().charAt(0).toUpperCase())}</span>
        <span class="patient-copy"><strong>${esc(p.patient_name)}</strong>
          <small>${esc(p.protocol_no || p.visit_id)} · ${esc(p.department || p.task || "COMED")}</small>
          <em>${esc(p.status || "Görüşme bekliyor")}</em></span>
      </button>`).join("")
    : '<div class="empty-box">Bu doktor için eşitlenmiş COMED hastası yok. Eklentiyi aynı doktor hesabıyla bağlayıp COMED iş listesini açın.</div>';
  document.querySelectorAll("[data-patient]").forEach(el => el.onclick = () => {
    const picked = overview.worklist[+el.dataset.patient];
    selectedPatient = patientKey(picked) === patientKey(selectedPatient) ? null : picked;
    renderWorklist();
  });
}

/* ---------- kayit listesi (yonetici paneliyle ayni satir duzeni) ---------- */
function renderRecords() {
  const list = $("rec-list");
  if (!overview.records.length) {
    list.innerHTML = '<div class="empty-box"><i class="bi bi-inbox"></i><p>Size atanmış görüşme kaydı yok. Mobil uygulamadan bir görüşme analiz edildiğinde burada listelenir.</p></div>';
    return;
  }
  list.innerHTML = overview.records.map(k => {
    const comed = k.comed_status === "completed"
      ? '<span class="badge-comed done" title="COMED"><i class="bi bi-check-circle"></i> COMED</span>'
      : k.comed_status === "ready_for_review"
        ? '<span class="badge-comed review" title="COMED doktor kontrolü"><i class="bi bi-eye"></i> COMED</span>'
        : k.comed_status
          ? '<span class="badge-comed pending" title="COMED aktarımı sürüyor"><i class="bi bi-arrow-repeat"></i> COMED</span>'
          : "";
    return `<div class="rec-item" data-id="${k.id}" data-search="${esc(((k.ozet || "") + " " + k.id).toLowerCase())}">
      <div class="rec-row">
        <span class="rec-no">#${k.id}</span>
        <span class="rec-date">${esc((k.olusturma || "").replace("T", " "))}</span>
        <span class="rec-ozet" title="${esc(k.ozet)}">${esc(k.ozet) || "—"}</span>
        <span class="rec-audio">${k.ses_var
          ? '<span class="badge-ses"><i class="bi bi-volume-up"></i> var</span>'
          : '<span class="badge-none">yok</span>'}</span>
        <span class="rec-act">${comed}
          <button class="mini-btn primary" data-act="ac" data-id="${k.id}"><i class="bi bi-file-earmark-text"></i> Raporlar</button>
        </span>
      </div>
      <div class="rec-detail hidden" id="det-${k.id}"></div>
    </div>`;
  }).join("");
}

function render() { renderStats(); renderWorklist(); renderRecords(); }

/* ---------- detay (yonetici panelindeki ayni govde) ---------- */
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-act]");
  if (btn && btn.dataset.act === "ac") { toggleDetail(btn.dataset.id); return; }
  const tab = e.target.closest(".det-tab");
  if (tab) { drawDetail(tab.dataset.rid, tab.dataset.tab); return; }
  const pdf = e.target.closest("[data-pdf]");
  if (pdf) { indirPdf(pdf); return; }
  const send = e.target.closest("[data-comed-send]");
  if (send) comedAktar(send.dataset.comedSend, send);
});

async function toggleDetail(id) {
  const det = $("det-" + id);
  if (!det.classList.contains("hidden")) { det.classList.add("hidden"); return; }
  await openDetail(id, "doktor");
}

async function openDetail(id, sekme) {
  const det = $("det-" + id);
  det.classList.remove("hidden");
  if (!cache[id]) {
    det.innerHTML = '<div class="det-loading">Kayıt yükleniyor…</div>';
    try {
      cache[id] = await json(`/doctor/api/records/${id}`);
    } catch (error) {
      det.innerHTML = `<div class="det-loading">Yüklenemedi: ${esc(error.message)}</div>`;
      return;
    }
  }
  drawDetail(id, sekme || "doktor");
}

function drawDetail(id, sekme) {
  const k = cache[id];
  const det = $("det-" + id);
  const u = k.usage || {};
  const ua = u.analiz || {}, us = u.ses || {}, ur = us.role_usage || {}, uf = us.fallback_usage || {};
  const totTok = (ua.total || 0) + (us.total || 0) + (uf.total || 0) + (ur.total || 0);
  const totCost = (ua.cost_usd || 0) + (us.cost_usd || 0) + (uf.cost_usd || 0) + (ur.cost_usd || 0);

  const meta = `<div class="det-meta">
    <span>Kayıt <b>#${k.id}</b></span>
    <span>Tarih <b>${esc((k.olusturma || "").replace("T", " "))}</b></span>
    <span>Token <b>${fmtNum(totTok)}</b></span>
    <span>Maliyet <b>${fmtUsd(totCost)}</b></span>
    ${ua.seconds != null ? `<span>Analiz süresi <b>${ua.seconds} sn</b></span>` : ""}
  </div>`;

  const audio = k.ses_var ? `<div class="det-audio">
      <span class="da-lbl"><i class="bi bi-volume-up"></i> Görüşme ses kaydı</span>
      <audio controls preload="metadata" src="/doctor/audio/${k.id}"></audio>
    </div>` : "";

  const tabs = [["doktor", "Doktor epikrizi", "file-medical"], ["comed", "COMED taslağı", "send-check"],
                ["hasta", "Hasta özeti", "person-heart"], ["yonetim", "Yönetim raporu", "shield-check"],
                ["transkript", "Görüşme metni", "chat-left-text"]];
  const patient = linkedPatient(k) || {};
  const transfer = k.comed_transfer || {};
  const comedUrl = transfer.clinical_card_url || patient.clinical_card_url || "";
  const locked = ["queued", "filling", "ready_for_review", "completed"].includes(transfer.status);

  det.innerHTML = `
    ${meta}${audio}
    <div class="comed-action-bar">
      <div class="comed-action-copy"><i class="bi bi-hospital"></i><span><b>COMED</b>${comedStatusHTML(transfer.status)}</span></div>
      <div class="comed-action-buttons">
        <button class="mini-btn comed-send" data-comed-send="${id}" ${!patient.visit_id || locked ? "disabled" : ""}><i class="bi bi-send"></i> COMED'e aktar ve kartı aç</button>
        ${comedUrl ? `<a class="mini-btn comed-open" href="${esc(comedUrl)}" target="_blank" rel="noopener"><i class="bi bi-box-arrow-up-right"></i> COMED'de aç</a>` : ""}
      </div>
    </div>
    ${!patient.visit_id ? '<div class="comed-warning"><i class="bi bi-info-circle"></i><div><b>Hasta seçilmedi</b><p>Aktarım için yukarıdaki COMED iş listesinden bu görüşmenin hastasını seçin.</p></div></div>' : ""}
    <div class="det-tabs">
      ${tabs.map(([key, lbl, ic]) => `<button class="det-tab ${key === sekme ? "active" : ""}" data-tab="${key}" data-rid="${id}"><i class="bi bi-${ic}"></i> ${lbl}</button>`).join("")}
    </div>
    ${["doktor", "hasta", "yonetim"].includes(sekme) ? `<div class="det-pdf">
       <button class="mini-btn pdf" data-pdf="${sekme}" data-rid="${id}"><i class="bi bi-file-earmark-pdf"></i> Bu raporu PDF indir</button>
     </div>` : ""}
    <div class="det-body">${bodyHTML(k, sekme)}</div>`;

  const audioEl = det.querySelector("audio");
  if (audioEl) prepareAudioTimeline(audioEl);
}

async function indirPdf(btn) {
  const rec = btn.dataset.pdf, id = btn.dataset.rid, orig = btn.innerHTML;
  btn.disabled = true; btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Hazırlanıyor…';
  try {
    const res = await fetch(`/doctor/pdf/${id}/${rec}`);
    if (res.status === 401) throw new Error("Oturum sona erdi. Tekrar giriş yapın.");
    if (!res.ok) {
      let message = "PDF hatası";
      try { message = (await res.json()).error || message; } catch (_) {}
      throw new Error(message);
    }
    const blob = await res.blob();
    if (!blob.size || !String(blob.type).startsWith("application/pdf")) throw new Error("Sunucu geçerli bir PDF döndürmedi.");
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = ({hasta: "hasta_ozeti", doktor: "epikriz", yonetim: "yonetim_raporu"}[rec] || "rapor") + `_${id}.pdf`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e) { toast("PDF indirilemedi: " + e.message, true); }
  finally { btn.disabled = false; btn.innerHTML = orig; }
}

/* ---------- COMED aktarimi ---------- */
function statusText(status) {
  return {
    queued: "Aktarım sırada", filling: "COMED alanları dolduruluyor",
    ready_for_review: "Aktarım bitti · Genel doktor kontrolü gerekli",
    completed: "COMED kaydı tamamlandı", failed: "Aktarım başarısız",
  }[status] || "Hazır";
}

function openComedWithBridge(url, transferId) {
  return new Promise((resolve) => {
    const requestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve(value);
    };
    const onMessage = (event) => {
      if (event.source !== window || event.origin !== location.origin
        || event.data?.source !== "klinot-doctor-comed-open-result-v1"
        || event.data?.request_id !== requestId) return;
      finish(event.data);
    };
    const timer = setTimeout(() => finish({ok: false, error: "Klinot COMED eklentisi yanıt vermedi"}), 1800);
    window.addEventListener("message", onMessage);
    window.postMessage({source: "klinot-doctor-comed-open-v1", request_id: requestId, url, transfer_id: transferId}, location.origin);
  });
}

async function comedAktar(id, btn) {
  const k = cache[id];
  const patient = linkedPatient(k);
  if (!patient?.visit_id) { toast("Önce COMED iş listesinden hastayı seçin.", true); return; }
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Sıraya alınıyor…';
  try {
    activeTransfer = await json("/doctor/api/comed/transfers", {
      method: "POST",
      body: JSON.stringify({record_id: Number(id), patient}),
    });
    cache[id].comed_transfer = activeTransfer;
    drawDetail(id, "comed");
    const opened = await openComedWithBridge(patient.clinical_card_url, activeTransfer.id);
    toast(opened.ok
      ? (opened.reused ? "Açık COMED sekmesi kullanıldı; giriş gerekirse aktarım girişten sonra devam eder." : "COMED kartı açıldı; giriş gerekirse aktarım otomatik devam eder.")
      : (window.open(patient.clinical_card_url, "_blank") ? "Eklenti yanıt vermedi; COMED kartı yeni sekmede açıldı." : "COMED eklentisi yanıt vermedi; kartı elle açın."),
      !opened.ok);
    await pollTransfer(id, activeTransfer.id);
  } catch (error) {
    toast(error.message, true);
    btn.disabled = false;
    btn.innerHTML = old;
  }
}

async function pollTransfer(recordId, transferId) {
  clearInterval(transferTimer);
  const tick = async () => {
    try {
      const fresh = await json(`/doctor/api/comed/transfers/${transferId}`);
      activeTransfer = fresh;
      if (cache[recordId]) {
        cache[recordId].comed_transfer = fresh;
        const det = $("det-" + recordId);
        if (det && !det.classList.contains("hidden")) {
          const current = det.querySelector(".det-tab.active")?.dataset.tab || "comed";
          drawDetail(recordId, current);
        }
      }
      if (["ready_for_review", "completed", "failed"].includes(fresh.status)) {
        clearInterval(transferTimer);
        toast(statusText(fresh.status));
      }
    } catch (_) { clearInterval(transferTimer); }
  };
  await tick();
  transferTimer = setInterval(tick, 3000);
}

/* ---------- arama ---------- */
const q = $("q");
if (q) q.addEventListener("input", () => {
  const t = q.value.trim().toLowerCase();
  let gorunen = 0;
  document.querySelectorAll(".rec-item").forEach(it => {
    const ok = !t || (it.dataset.search || "").includes(t);
    it.classList.toggle("hidden", !ok);
    if (ok) gorunen++;
  });
  $("bos-arama").classList.toggle("hidden", gorunen !== 0);
});

/* ---------- yukleme ---------- */
async function load({silent = false} = {}) {
  if (loading) return;
  loading = true;
  try {
    const next = await json("/doctor/api/overview");
    const prior = patientKey(selectedPatient);
    const openIds = [...document.querySelectorAll(".rec-detail:not(.hidden)")]
      .map(el => el.id.replace("det-", ""));
    overview = next;
    if (prior) selectedPatient = overview.worklist.find(p => patientKey(p) === prior) || selectedPatient;
    render();
    // Acik duran detaylar yenilemeden sonra kapanmasin.
    openIds.forEach(id => { if (cache[id]) openDetail(id, "doktor"); });
  } catch (e) {
    if (!silent) toast(e.message, true);
  } finally { loading = false; }
}

$("refresh").onclick = () => load();
document.addEventListener("visibilitychange", () => { if (!document.hidden) load({silent: true}); });
refreshTimer = setInterval(() => load({silent: true}), 15000);
load();
