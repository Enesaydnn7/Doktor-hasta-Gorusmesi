/* ================= Admin paneli ================= */

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

  const tabs = [["doktor", "AI epikriz", "file-medical"], ["comed", "COMED taslağı", "send-check"],
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

