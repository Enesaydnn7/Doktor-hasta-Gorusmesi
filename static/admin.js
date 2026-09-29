/* ================= Admin paneli ================= */
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MISS = "belirtilmedi";
const isMiss = (v) => !v || String(v).trim().toLowerCase() === MISS;
const val = (v) => isMiss(v) ? `<span class="val-missing">belirtilmedi</span>` : esc(v);
const fmtNum = (n) => Number(n || 0).toLocaleString("tr-TR");
const fmtUsd = (c) => { c = Number(c || 0); const d = (c > 0 && c < 0.01) ? 6 : 4; return "$" + c.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }); };

const cache = {};   // id -> kayıt

/* ---------- arama ---------- */
const q = document.getElementById("q");
if (q) q.addEventListener("input", () => {
  const t = q.value.trim().toLowerCase();
  let görünen = 0;
  document.querySelectorAll(".rec-item").forEach(it => {
    const ok = !t || (it.dataset.search || "").includes(t);
    it.classList.toggle("hidden", !ok);
    if (ok) görünen++;
  });
  const bos = document.getElementById("bos-arama");
  if (bos) bos.classList.toggle("hidden", görünen !== 0);
});

/* ---------- satır butonları ---------- */
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const id = btn.dataset.id;
  const act = btn.dataset.act;
  if (act === "ac") toggleDetail(id, btn);
  else if (act === "ses") openDetail(id, "ses");
  else if (act === "sil") silKayit(id);
});

async function silKayit(id) {
  if (!confirm(`#${id} numaralı kaydı silmek istediğinize emin misiniz?`)) return;
  try {
    const res = await fetch(`/admin/kayit/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("silinemedi");
    const item = document.querySelector(`.rec-item[data-id="${id}"]`);
    if (item) item.remove();
  } catch (err) { alert("Silinemedi: " + err.message); }
}

async function toggleDetail(id, btn) {
  const det = document.getElementById("det-" + id);
  if (!det.classList.contains("hidden")) { det.classList.add("hidden"); return; }
  await openDetail(id, "doktor", btn);
}

async function openDetail(id, sekme, btn) {
  const det = document.getElementById("det-" + id);
  det.classList.remove("hidden");
  if (!cache[id]) {
    det.innerHTML = `<div class="det-loading">Kayıt yükleniyor…</div>`;
    try {
      const res = await fetch(`/admin/kayit/${id}`);
      if (!res.ok) throw new Error("kayıt alınamadı");
      cache[id] = await res.json();
    } catch (err) {
      det.innerHTML = `<div class="det-loading">Yüklenemedi: ${esc(err.message)}</div>`;
      return;
    }
  }
  drawDetail(id, sekme || "doktor");
}

function drawDetail(id, sekme) {
  const k = cache[id];
  const det = document.getElementById("det-" + id);
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
      <audio controls preload="metadata" src="/admin/ses/${k.id}"></audio>
    </div>` : "";

  const tabs = [["doktor", "Doktor epikrizi", "file-medical"], ["comed", "COMED taslağı", "send-check"],
                ["hasta", "Hasta özeti", "person-heart"], ["yonetim", "Yönetim raporu", "shield-check"],
                ["transkript", "Görüşme metni", "chat-left-text"]];
  const patient = (k.metadata || {}).comed_patient || {};
  const transfer = k.comed_transfer || {};
  const comedUrl = transfer.clinical_card_url || patient.clinical_card_url || "";
  const comedStatus = comedStatusHTML(transfer.status);

  det.innerHTML = `
    ${meta}${audio}
    <div class="comed-action-bar">
      <div class="comed-action-copy"><i class="bi bi-hospital"></i><span><b>COMED</b>${comedStatus}</span></div>
      <div class="comed-action-buttons">
        <button class="mini-btn comed-send" data-comed-send="${id}" ${!patient.visit_id ? "disabled" : ""}><i class="bi bi-send"></i> COMED'e aktar</button>
        ${comedUrl ? `<a class="mini-btn comed-open" href="${esc(comedUrl)}" target="_blank" rel="noopener"><i class="bi bi-box-arrow-up-right"></i> COMED'de aç</a>` : ""}
      </div>
    </div>
    <div class="det-tabs">
      ${tabs.map(([key, lbl, ic]) => `<button class="det-tab ${key === sekme ? "active" : ""}" data-tab="${key}" data-rid="${id}"><i class="bi bi-${ic}"></i> ${lbl}</button>`).join("")}
    </div>
    ${["doktor", "hasta", "yonetim"].includes(sekme) ? `<div class="det-pdf">
       <button class="mini-btn pdf" data-pdf="${sekme}" data-rid="${id}"><i class="bi bi-file-earmark-pdf"></i> Bu raporu PDF indir</button>
     </div>` : ""}
    <div class="det-body">${bodyHTML(k, sekme)}</div>`;

  const audioEl = det.querySelector("audio");
  if (audioEl) prepareAudioTimeline(audioEl);
  det.querySelectorAll(".det-tab").forEach(b => b.onclick = () => drawDetail(b.dataset.rid, b.dataset.tab));
  const pdfBtn = det.querySelector("[data-pdf]");
  if (pdfBtn) pdfBtn.onclick = () => indirPdf(pdfBtn);
  const comedBtn = det.querySelector("[data-comed-send]");
  if (comedBtn) comedBtn.onclick = () => comedAktar(id, comedBtn);
}

function comedStatusHTML(status) {
  const labels = {
    queued: ["Aktarım sırasında", "pending"], filling: ["Alanlar dolduruluyor", "pending"],
    ready_for_review: ["Aktarım bitti · genel doktor kontrolü gerekli", "review"],
    completed: ["COMED kaydı tamamlandı", "done"], failed: ["Aktarım başarısız", "failed"]
  };
  const item = labels[status] || ["Henüz aktarılmadı", "idle"];
  return `<small class="comed-inline-status ${item[1]}">${item[0]}</small>`;
}

async function comedAktar(id, btn) {
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Gönderiliyor…';
  try {
    const response = await fetch(`/admin/comed/transfer/${id}`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || "Aktarım başlatılamadı");
    cache[id].comed_transfer = payload;
    drawDetail(id, "comed");
  } catch (error) {
    alert("COMED aktarımı başlatılamadı: " + error.message);
    btn.disabled = false;
    btn.innerHTML = old;
  }
}

function prepareAudioTimeline(audio) {
  const repairDuration = () => {
    if (audio.duration !== Infinity) return;
    const resetToStart = () => {
      audio.currentTime = 0;
    };
    audio.addEventListener("timeupdate", resetToStart, { once: true });
    audio.currentTime = Number.MAX_SAFE_INTEGER;
  };
  if (audio.readyState >= 1) repairDuration();
  else audio.addEventListener("loadedmetadata", repairDuration, { once: true });
  audio.load();
}

function bodyHTML(k, sekme) {
  if (sekme === "transkript") return `<div class="det-trans">${esc(k.transkript || "")}</div>`;
  if (sekme === "comed") return comedHTML(k);
  if (sekme === "hasta") return hastaHTML(k.hasta || {});
  if (sekme === "yonetim") return yonetimHTML(k.yonetim || {});
  return doktorHTML(k.doktor || {});
}

function comedHTML(k) {
  const d = k.comed || {};
  const hasDraft = Object.keys(d).length > 0;
  const patient = (k.metadata || {}).comed_patient || {};
  const transfer = k.comed_transfer || {};
  const debug = transfer.debug || {};
  const required = (transfer.bundle || {}).missing_required || [];
  const diagnoses = d.diagnoses || [];
  const line = (label, value) => `<div class="comed-field"><span>${label}</span><b>${val(value)}</b></div>`;
  return `<div class="panel-body comed-draft">
    <div class="comed-draft-hero">
      <div><span class="eyebrow">SEÇİLİ HASTA</span><h3>${esc(patient.patient_name || "Hasta seçilmedi")}</h3>
      <p>${esc(patient.protocol_no || patient.visit_id || "")} · ${esc(patient.department || "")}</p></div>
      ${comedStatusHTML(transfer.status)}
    </div>
    ${!hasDraft ? `<div class="comed-warning"><i class="bi bi-info-circle"></i><div><b>COMED taslağı bulunmuyor</b><p>Bu kayıt COMED entegrasyonundan önce hazırlanmış. Yeni görüşmelerde alan taslağı analizle birlikte oluşturulur.</p></div></div>` : required.length ? `<div class="comed-warning"><i class="bi bi-exclamation-triangle"></i><div><b>${required.length} zorunlu alan eksik</b><p>Bu alanlar doktor tarafından COMED'de tamamlanmalıdır: ${required.map(esc).join(", ")}</p></div></div>` : `<div class="comed-ok"><i class="bi bi-check-circle"></i> Zorunlu taslak alanları hazır.</div>`}
    ${comedDebugHTML(debug)}
    <div class="sec"><div class="sec-title"><i class="bi bi-card-text"></i> Muayene formu taslağı</div>
      <div class="comed-field-grid">${line("Şikâyet", d.patient_complaint)}${line("Öykü", d.patient_story)}${line("Muayene notu", d.exam_simple_textarea)}${line("Tedavi notu", d.treatment_note_v2)}</div></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-activity"></i> Tanı önerileri</div>
      <div class="comed-diagnoses">${diagnoses.map(x => `<span><b>${esc(x.code)}</b>${esc(x.description)}</span>`).join("") || '<div class="empty-mut">Tanı önerisi yok.</div>'}</div></div>
    <div class="comed-review-note"><i class="bi bi-shield-check"></i><span>Otomatik imza kapalıdır. Alanlar COMED'e taşındıktan sonra doktor kontrol edip kaydeder.</span></div>
  </div>`;
}

function comedDebugHTML(debug) {
  if (!debug || !Object.keys(debug).length) return "";
  const postFields = debug.post?.fields || [];
  const extensionFields = (debug.extension?.fields || []).filter(x => x.status === "filled" || x.status === "saved");
  const notFound = (debug.extension?.fields || []).filter(x => x.status === "not_found" || x.status === "not_saved");
  const defaults = debug.fallback_fields || [];
  const chips = (items, cls) => items.length
    ? items.map(item => `<span class="comed-debug-chip ${cls}">${esc(typeof item === "string" ? item : item.field)}</span>`).join("")
    : '<span class="empty-mut">Yok</span>';
  return `<div class="comed-debug">
    <div class="comed-debug-head"><span><i class="bi bi-bug"></i> Aktarım debug</span><b>${esc(debug.mode || debug.stage || "hazırlanıyor")}</b></div>
    <div class="comed-debug-grid">
      <section><h4>POST ile giden</h4><div>${chips(postFields, "post")}</div></section>
      <section><h4>Eklentinin doldurduğu</h4><div>${chips(extensionFields, "extension")}</div></section>
      <section><h4>Operasyonel varsayılan</h4><div>${chips(defaults, "default")}</div></section>
      <section><h4>Bulunamayan / kaydedilemeyen</h4><div>${chips(notFound, "missing")}</div></section>
    </div>
    <p class="comed-debug-note">Sistem sorgusu alt belgesi: <b>${debug.extension?.system_inquiry_saved ? "kaydedildi" : "kaydedilmedi"}</b> · Otomatik imza: <b>kapalı</b></p>
  </div>`;
}

async function indirPdf(btn) {
  const aliases = {
    hasta: "hasta", hasta_ozeti: "hasta",
    doktor: "doktor", doctor: "doktor", epikriz: "doktor", doktor_epikrizi: "doktor",
    yonetim: "yonetim", yonetim_raporu: "yonetim"
  };
  const rawRec = String(btn.dataset.pdf || "").trim().toLowerCase().replace(/[ -]+/g, "_");
  const rec = aliases[rawRec] || "doktor", id = btn.dataset.rid;
  const orig = btn.innerHTML;
  btn.disabled = true; btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Hazırlanıyor…';
  try {
    const res = await fetch(`/admin/pdf/${id}/${rec}`, { method: "POST" });
    if (res.status === 401) throw new Error("Yönetici oturumu sona erdi. Tekrar giriş yapın.");
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
    a.download = ({ hasta: "hasta_ozeti", doktor: "epikriz", yonetim: "yonetim_raporu" }[rec]) + `_${id}.pdf`;
    document.body.appendChild(a); a.click(); a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (e) { alert("PDF indirilemedi: " + e.message); }
  finally { btn.disabled = false; btn.innerHTML = orig; }
}

/* ---------- rapor görünümleri ---------- */
function hastaHTML(d) {
  const meds = (d.ilaclar || []).length
    ? d.ilaclar.map(m => `<div class="med"><i class="bi bi-capsule"></i><span>${esc(m)}</span></div>`).join("")
    : `<div class="empty-mut">İlaç önerisi belirtilmedi.</div>`;
  return `<div class="panel-body">
    <div class="sec"><div class="lead">${esc(d.ozet)}</div></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-clipboard2-pulse"></i> Değerlendirme</div><div>${esc(d.tani)}</div></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-check2-circle"></i> Yapmanız gerekenler</div>
      <ul class="checklist">${(d.yapilacaklar || []).map(x => `<li><i class="bi bi-check-lg"></i><span>${esc(x)}</span></li>`).join("")}</ul></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-capsule-pill"></i> İlaçlar</div>${meds}</div>
    <div class="sec"><div class="sec-title"><i class="bi bi-calendar-check"></i> Kontrol</div><div>${esc(d.kontrol)}</div></div>
    <div class="sec"><div class="note-soft">${esc(d.kapanis)}</div></div>
  </div>`;
}

function ozBox(t, ic, items, empty) {
  const l = (items || []).length
    ? `<ul>${items.map(x => `<li><i class="bi bi-dot"></i><span>${esc(x)}</span></li>`).join("")}</ul>`
    : `<div class="empty-mut">${empty}</div>`;
  return `<div class="oz-box"><div class="oz-t"><i class="bi bi-${ic}"></i> ${t}</div>${l}</div>`;
}

function doktorHTML(d) {
  const e = d.epikriz || {}, k = d.koclugu || {}, oz = e.ozgecmis || {}, kn = e.kontrol || {};
  const meta = `<div class="meta-strip">
    <div class="meta-box"><div class="m-lbl">Görüşme tarihi</div><div class="m-val">${val(e.gorusmeTarihi)}</div></div>
    <div class="meta-box"><div class="m-lbl">Doktor</div><div class="m-val">${val(e.doktor)}</div></div>
    <div class="meta-box hl"><div class="m-lbl">Başlangıç</div><div class="m-val">${val(e.baslangic)}</div></div>
    <div class="meta-box hl"><div class="m-lbl">Ağrı skoru</div><div class="m-val">${val(e.agriSkoru)}</div></div></div>`;
  const fields = [["Şikayet", e.sikayet], ["Öykü", e.oyku], ["Fizik muayene", e.fizikMuayene]]
    .map(([l, v]) => `<div class="field"><div class="f-label">${l}</div><div class="f-val">${val(v)}</div></div>`).join("");
  const icdStr = (e.icd || []).map(c => esc(c.kod)).filter(Boolean).join(", ");
  const kesinVar = !isMiss(e.kesinTani);
  const onT = isMiss(e.onTani) ? `<span class="val-missing">belirtilmedi</span>`
    : esc(e.onTani) + (icdStr && !kesinVar ? ` <span class="icd-inline">ICD-10: ${icdStr}</span>` : "");
  const kesinT = !kesinVar ? `<span class="val-missing">Görüşmede kesin tanı konmadı.</span>`
    : esc(e.kesinTani) + (icdStr ? ` <span class="icd-inline">ICD-10: ${icdStr}</span>` : "");
  const tedavi = (e.tedavi || []).length
    ? e.tedavi.map(x => `<div class="med"><i class="bi bi-capsule"></i><span>${esc(x)}</span></div>`).join("")
    : `<div class="empty-mut">Tedavi belirtilmedi.</div>`;
  const oneriler = (k.oneriler || []).map((o, index) => `<article class="coach-v2">
      <div class="coach-index">${index + 1}</div>
      <div class="coach-content"><div class="c-an"><span class="coach-label">GÖRÜŞME ANI</span><p>${esc(o.an)}</p></div>
      <div class="c-oneri"><i class="bi bi-lightbulb-fill"></i><div><span class="coach-label">ÖNERİ</span><p>${esc(o.oneri)}</p></div></div></div></article>`).join("");
  return `<div class="panel-body">
    <div class="sec">${meta}</div>
    <div class="sec"><div class="sec-title"><i class="bi bi-file-earmark-medical"></i> Şikayet & öykü</div>${fields}</div>
    <div class="sec"><div class="sec-title"><i class="bi bi-person-lines-fill"></i> Özgeçmiş</div><div class="oz-grid">
      ${ozBox("Kronik hastalıklar", "heart-pulse", oz.kronik, "Belirtilmedi.")}
      ${ozBox("Ameliyatlar", "bandaid", oz.ameliyatlar, "Belirtilmedi.")}
      ${ozBox("Kullandığı ilaçlar", "capsule", oz.ilaclar, "Belirtilmedi.")}
      ${ozBox("Alerjiler", "exclamation-diamond", oz.alerji, "Belirtilmedi.")}
      ${ozBox("Alışkanlıklar", "cup-hot", oz.aliskanlik, "Belirtilmedi.")}</div></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-people"></i> Soygeçmiş</div>
      ${(e.soygecmis || []).length ? `<ul class="checklist">${e.soygecmis.map(x => `<li><i class="bi bi-diagram-2"></i><span>${esc(x)}</span></li>`).join("")}</ul>` : `<div class="empty-mut">Belirtilmedi.</div>`}</div>
    <div class="sec"><div class="sec-title"><i class="bi bi-droplet-half"></i> Laboratuvar / tetkik</div>
      ${(e.lab || []).length ? `<ul class="checklist">${e.lab.map(x => `<li><i class="bi bi-droplet"></i><span>${esc(x)}</span></li>`).join("")}</ul>` : `<div class="empty-mut">Belirtilmedi.</div>`}</div>
    <div class="sec"><div class="sec-title"><i class="bi bi-clipboard2-pulse"></i> Tanılar</div>
      <div class="dx dx-on"><span class="dx-tag">Ön tanı</span><span>${onT}</span></div>
      <div class="dx dx-kesin ${kesinVar ? "" : "missing"}"><span class="dx-tag">Kesin tanı</span><span>${kesinT}</span></div></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-capsule-pill"></i> Tedavi</div>${tedavi}</div>
    <div class="sec"><div class="sec-title"><i class="bi bi-signpost-2"></i> İzlem & plan</div><div>${val(e.plan)}</div></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-calendar-check"></i> Kontrol</div>
      <div class="kontrol-box">
        <div class="k-line"><span class="k-lbl">Önerildi mi</span><span>${kn.onerildi === true ? "Evet" : kn.onerildi === false ? "Hayır" : "belirtilmedi"}</span></div>
        <div class="k-line"><span class="k-lbl">Zaman</span><span>${val(kn.zaman)}</span></div>
        <div class="k-line"><span class="k-lbl">Not</span><span>${val(kn.not)}</span></div></div></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-hand-thumbs-up"></i> Güçlü yönler</div>
      <ul class="strong-list">${(k.guclu || []).map(x => `<li><i class="bi bi-check-circle-fill"></i><span>${esc(x)}</span></li>`).join("") || '<li class="empty-mut">—</li>'}</ul></div>
    <div class="sec communication-sec"><div class="communication-head"><span class="communication-icon"><i class="bi bi-chat-heart"></i></span><div><div class="sec-title">İletişim önerileri</div><p>Görüşmeden alınan somut, uygulanabilir gelişim notları</p></div></div>${oneriler || '<div class="empty-mut">Öneri yok.</div>'}</div>
  </div>`;
}

function yonetimHTML(d) {
  const g = d.guvenlik || {}, s = d.skor || {};
  const scoreTone = value => Number(value || 0) < 50 ? "score-low" : Number(value || 0) < 75 ? "score-mid" : "score-high";
  const durum = (g.durum || "temiz").toLowerCase();
  const dL = { temiz: "Temiz", dikkat: "Dikkat", sorun: "Sorun" }[durum] || g.durum || "—";
  const dI = { temiz: "shield-check", dikkat: "shield-exclamation", sorun: "shield-x" }[durum] || "shield";
  const bar = (l, v) => `<div class="bar-row"><span class="br-lbl">${l}</span>
    <div class="bar-track"><div class="bar-fill ${scoreTone(v)}" style="width:${Math.round(v || 0)}%"></div></div>
    <span class="br-val">${Math.round(v || 0)}</span></div>`;
  const risk = (d.risk || "yok").toLowerCase();
  const rI = { yok: "check-circle", "düşük": "info-circle", orta: "exclamation-triangle", "yüksek": "exclamation-octagon" }[risk] || "info-circle";
  return `<div class="panel-body">
    <div class="sec"><div class="sec-title"><i class="bi bi-shield"></i> Güvenlik / üslup</div>
      <div class="status s-${durum}"><i class="bi bi-${dI}"></i> ${esc(dL)}</div>
      <div style="margin-top:12px">
        <div class="lang-line"><span class="ll-tag">Hasta</span><span>${esc(g.hasta)}</span></div>
        <div class="lang-line"><span class="ll-tag">Doktor</span><span>${esc(g.doktor)}</span></div></div>
      <div style="margin-top:10px">${(g.tespitler || []).length
        ? `<ul class="checklist">${g.tespitler.map(t => `<li><i class="bi bi-exclamation-circle" style="color:var(--bad)"></i><span>${esc(t)}</span></li>`).join("")}</ul>`
        : `<div class="empty-mut">Uygunsuz / argo ifade saptanmadı.</div>`}</div></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-speedometer2"></i> Doktor skoru <span class="scale">(0-100)</span></div>
      <div class="score-top"><div class="score-big ${scoreTone(s.genel)}"><div class="sb-num">${Math.round(s.genel || 0)}</div><div class="sb-lbl">GENEL</div></div>
        <div class="score-bars">${bar("Empati", s.empati)}${bar("Netlik", s.netlik)}${bar("Dinleme", s.dinleme)}${bar("Verimlilik", s.verimlilik)}</div></div>
      ${d.verimlilikNotu ? `<div class="vr-note"><i class="bi bi-stopwatch"></i> <strong>Verimlilik notu:</strong> ${esc(d.verimlilikNotu)}</div>` : ""}</div>
    <div class="sec"><div class="sec-title"><i class="bi bi-clipboard2-data"></i> Genel değerlendirme</div><div>${esc(d.degerlendirme)}</div></div>
    <div class="sec"><div class="sec-title"><i class="bi bi-flag"></i> Risk bayrağı</div>
      <div class="risk risk-${risk}"><i class="bi bi-${rI}"></i> <strong>${esc((d.risk || "yok").toUpperCase())}</strong></div></div>
  </div>`;
}
