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

/* ---------- COMED is listesi ----------
   Kartlar sirayla farkli renk alir; yan yana iki kart hicbir zaman ayni
   renkte olmaz, boylece hangi bilginin hangi hastaya ait oldugu karismaz. */
const CARD_COLORS = [
  {c: "#0e8a80", bg: "#e6f5f3"}, {c: "#4256c8", bg: "#eaedfb"},
  {c: "#b06a07", bg: "#fdf1df"}, {c: "#b83a66", bg: "#fdeaf0"},
  {c: "#6f42c0", bg: "#f1eafb"}, {c: "#0b7ba4", bg: "#e4f3fa"},
  {c: "#4a7d1f", bg: "#eef7e3"}, {c: "#8a5a2b", bg: "#f7efe6"},
];

function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "H";
  const first = parts[0][0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

/* Bu hastaya bagli kayitlar: kart artik sadece isim degil, is durumu gosterir. */
function patientRecords(p) {
  const key = patientKey(p);
  if (!key) return [];
  return overview.records.filter(
    r => String((r.metadata || {}).comed_patient?.visit_id || "") === key
  );
}

function patientBadge(records) {
  if (!records.length) {
    return '<span class="pc-tag wait"><i class="bi bi-mic"></i> Kayıt bekleniyor</span>';
  }
  const done = records.some(r => r.comed_status === "completed");
  const review = records.some(r => r.comed_status === "ready_for_review");
  const busy = records.some(r => r.comed_status && !["completed", "ready_for_review"].includes(r.comed_status));
  if (done) return '<span class="pc-tag ok"><i class="bi bi-check-circle-fill"></i> COMED tamam</span>';
  if (review) return '<span class="pc-tag review"><i class="bi bi-eye-fill"></i> Kontrol bekliyor</span>';
  if (busy) return '<span class="pc-tag busy"><i class="bi bi-arrow-repeat"></i> Aktarılıyor</span>';
  return `<span class="pc-tag ready"><i class="bi bi-file-earmark-text-fill"></i> ${records.length} rapor hazır</span>`;
}

function renderWorklist() {
  $("worklist-count").textContent = `${overview.worklist.length} hasta`;
  $("worklist").innerHTML = overview.worklist.length
    ? overview.worklist.map((p, i) => {
        const color = CARD_COLORS[i % CARD_COLORS.length];
        const on = patientKey(p) === patientKey(selectedPatient);
        const records = patientRecords(p);
        const sub = [p.department || p.task, p.doctor_name].filter(Boolean).join(" · ");
        return `<button class="patient-card ${on ? "selected" : ""}" data-patient="${i}"
            style="--c:${color.c};--cbg:${color.bg}"
            title="${esc(p.patient_name)} — seçmek için tıklayın">
          <span class="pc-head">
            <span class="patient-avatar">${esc(initials(p.patient_name))}</span>
            <span class="pc-id">
              <strong>${esc(p.patient_name || "İsimsiz hasta")}</strong>
              <small>${esc(p.protocol_no || p.patient_no || p.visit_id)}</small>
            </span>
            <span class="pc-check"><i class="bi bi-check-lg"></i></span>
          </span>
          ${sub ? `<span class="pc-sub"><i class="bi bi-hospital"></i> ${esc(sub)}</span>` : ""}
          <span class="pc-tags">
            ${patientBadge(records)}
            ${p.birth_date ? `<span class="pc-tag plain"><i class="bi bi-cake2"></i> ${esc(p.birth_date)}</span>` : ""}
            ${p.status ? `<span class="pc-tag plain"><i class="bi bi-clock-history"></i> ${esc(p.status)}</span>` : ""}
          </span>
        </button>`;
      }).join("")
    : '<div class="empty-box">Bu doktor için eşitlenmiş COMED hastası yok. Eklentiyi aynı doktor hesabıyla bağlayıp COMED iş listesini açın.</div>';
  document.querySelectorAll("[data-patient]").forEach(el => el.onclick = () => {
    const picked = overview.worklist[+el.dataset.patient];
    selectedPatient = patientKey(picked) === patientKey(selectedPatient) ? null : picked;
    renderWorklist();
    renderRecords();
  });
}

/* ---------- kayit listesi (yonetici paneliyle ayni satir duzeni) ---------- */
function renderRecords() {
  const list = $("rec-list");
  // Liste komple yeniden yazilir; calan ses once parka alinir, detay
  // yeniden cizilince (drawDetail → restoreLiveAudio) yerine geri doner.
  parkLiveAudio(list);
  if (!overview.records.length) {
    list.innerHTML = '<div class="empty-box"><i class="bi bi-inbox"></i><p>Size atanmış görüşme kaydı yok. Mobil uygulamadan bir görüşme analiz edildiğinde burada listelenir.</p></div>';
    return;
  }
  // Hasta kartina tiklamak listeyi suzsun: o hastanin kayitlari + henuz
  // hicbir hastaya baglanmamis kayitlar (aktarilacak adaylar) kalir.
  const key = patientKey(selectedPatient);
  const shown = key
    ? overview.records.filter(r => {
        const link = String((r.metadata || {}).comed_patient?.visit_id || "");
        return !link || link === key;
      })
    : overview.records;
  const banner = key
    ? `<div class="rec-filter"><span><i class="bi bi-funnel-fill"></i>
         <b>${esc(selectedPatient.patient_name || "Seçili hasta")}</b> için süzüldü · ${shown.length} kayıt</span>
       <button class="mini-btn" id="filtre-temizle"><i class="bi bi-x-lg"></i> Tümünü göster</button></div>`
    : "";
  if (!shown.length) {
    list.innerHTML = banner + '<div class="empty-box"><i class="bi bi-inbox"></i><p>Bu hastaya bağlı kayıt yok. Mobil uygulamadan görüşmeyi kaydedip analiz edin.</p></div>';
    const clear = $("filtre-temizle");
    if (clear) clear.onclick = () => { selectedPatient = null; renderWorklist(); renderRecords(); };
    return;
  }
  list.innerHTML = banner + shown.map(k => {
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
  const clear = $("filtre-temizle");
  if (clear) clear.onclick = () => { selectedPatient = null; renderWorklist(); renderRecords(); };
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

/* ---------- calan sesi yeniden cizimden koru ----------
   Panel yenilendiginde detay HTML'i bastan yazilir ve <audio> dugumu yok
   olurdu; ses bu yuzden kendi kendine duruyordu.

   Onemli: Chrome bir medya dugumunu DOM'dan CIKARINCA oynatmayi durdurur,
   bu yuzden remove() ise yaramaz. Dugum bunun yerine gorunmez bir park
   kabina TASINIR -- tasima tek islemdir, eleman belgeden hic ayrilmaz --
   ve yeni HTML hazir olunca yerine geri takilir. */
function audioPark() {
  let park = document.getElementById("audio-park");
  if (!park) {
    park = document.createElement("div");
    park.id = "audio-park";
    park.setAttribute("aria-hidden", "true");
    park.style.cssText =
      "position:absolute;width:0;height:0;overflow:hidden;opacity:0;pointer-events:none";
    document.body.appendChild(park);
  }
  return park;
}

/* Calan sesi parka al. Duran/hic baslamamis sesler korunmaz, park sisirmesin. */
function parkLiveAudio(root) {
  const park = audioPark();
  // Onceki turlardan kalan, artik calmayan dugumleri temizle.
  park.querySelectorAll("audio").forEach(old => { if (old.paused) old.remove(); });
  const audio = root?.querySelector("audio");
  if (!audio || (audio.paused && !audio.currentTime)) return null;
  park.appendChild(audio);
  return audio;
}

/* Yeni HTML'deki bos oynaticiyi, parktaki ayni kaydin calan dugumuyle degistir. */
function restoreLiveAudio(root) {
  const slot = root?.querySelector("audio");
  if (!slot) return;
  const src = slot.getAttribute("src");
  const kept = [...audioPark().querySelectorAll("audio")]
    .find(audio => audio.getAttribute("src") === src);
  if (kept) slot.replaceWith(kept);
  else prepareAudioTimeline(slot);
}

function drawDetail(id, sekme) {
  const k = cache[id];
  const det = $("det-" + id);
  parkLiveAudio(det);
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

  const tabs = [["doktor", "AI epikriz", "file-medical"], ["comed", "COMED taslağı", "send-check"],
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

  restoreLiveAudio(det);
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
function audioPlaying() {
  return [...document.querySelectorAll("audio")].some(a => !a.paused && !a.ended);
}

async function load({silent = false} = {}) {
  if (loading) return;
  // Ses calarken arka plan yenilemesi listeyi bastan cizip oynatmayi kesiyordu.
  if (silent && audioPlaying()) return;
  loading = true;
  try {
    const next = await json("/doctor/api/overview");
    const prior = patientKey(selectedPatient);
    // Acik detaylar kapanmasin, acik sekme de "doktor"a geri atlamasin.
    const open = [...document.querySelectorAll(".rec-detail:not(.hidden)")].map(el => ({
      id: el.id.replace("det-", ""),
      tab: el.querySelector(".det-tab.active")?.dataset.tab || "doktor",
    }));
    overview = next;
    if (prior) selectedPatient = overview.worklist.find(p => patientKey(p) === prior) || selectedPatient;
    render();
    open.forEach(({id, tab}) => { if (cache[id]) openDetail(id, tab); });
  } catch (e) {
    if (!silent) toast(e.message, true);
  } finally { loading = false; }
}

$("refresh").onclick = () => load();
document.addEventListener("visibilitychange", () => { if (!document.hidden) load({silent: true}); });
refreshTimer = setInterval(() => load({silent: true}), 15000);
load();
