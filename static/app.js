// ---- Örnek diyalog (gerilim tipi baş ağrısı — detaylı anamnez) ----
const EXAMPLE = `Doktor: Merhaba, hoş geldiniz. Bugün sizi buraya getiren şikayet nedir?
Hasta: Merhaba doktor bey. Yaklaşık üç haftadır sürekli baş ağrım var, bir türlü geçmiyor.
Doktor: Anladım. Ağrı günün belli bir saatinde mi oluyor, yoksa gün boyu sürekli mi?
Hasta: Genelde öğleden sonra başlıyor, akşama doğru artıyor. Bazen sabah da oluyor.
Doktor: Ağrıyı nasıl tarif edersiniz, zonklayıcı mı yoksa baskı hissi gibi mi?
Hasta: Daha çok başımın iki yanında sıkıştıran bir baskı gibi, bazen enseme de vuruyor.
Doktor: Şiddetini 10 üzerinden puanlasanız kaç verirsiniz?
Hasta: 6 falan derim, çalışmamı engelliyor ama dayanılmaz değil.
Doktor: Bulantı, kusma ya da ışıktan rahatsız olma oluyor mu?
Hasta: Yok öyle bir şey. Sadece ağrı, ama konsantre olamıyorum, işim de masa başı.
Doktor: Uyku düzeniniz nasıl son zamanlarda? Stresli bir dönemden mi geçiyorsunuz?
Hasta: Açıkçası çok yoğun bir dönem, işte baskı var, geceleri de zor uyuyorum, günde 4-5 saat.
Doktor: Ağrı kesici kullandınız mı, işe yaradı mı?
Hasta: Birkaç kez Parol içtim, o an biraz hafifletiyor ama sonra tekrar başlıyor.
Doktor: Bilinen kronik bir hastalığınız var mı? Düzenli kullandığınız ilaç?
Hasta: Yok, düzenli ilaç kullanmıyorum. Sadece 2015'te apandisit ameliyatı olmuştum.
Doktor: Bilinen ilaç alerjiniz var mı? Sigara, alkol kullanıyor musunuz?
Hasta: Alerjim yok. Sigara içmiyorum, alkolü de nadiren, sosyal olarak.
Doktor: Ailede tansiyon, migren ya da benzeri bir hastalık öyküsü var mı?
Hasta: Annemde tansiyon var. Migreni bilmiyorum, duymadım.
Doktor: Şimdi tansiyonunuza bakalım, kısa bir nörolojik muayene de yapacağım; endişelenecek bir tablo görünmüyor.
Hasta: Tamam doktor bey. Ciddi bir şey değil di mi? Açıkçası biraz korktum, tümör falan mı diye.
Doktor: Anlattıklarınız büyük ihtimalle gerilim tipi baş ağrısı; uykusuzluk ve stresle tetiklenmiş görünüyor.
Hasta: Çok rahatladım, teşekkür ederim. Peki ne yapmam gerekiyor?
Doktor: Önce uyku düzenini toparlayacağız, gerektiğinde Parol'e devam edebilirsiniz. İki hafta sonra kontrole gelin; ağrı aniden şiddetlenir, ateş ya da görme bozukluğu olursa beklemeden gelin.
Hasta: Tamamdır, çok teşekkürler doktor bey.`;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MISS = "belirtilmedi";
const isMiss = (v) => !v || String(v).trim().toLowerCase() === MISS;
const val = (v) => isMiss(v) ? `<span class="val-missing">belirtilmedi</span>` : esc(v);

$("btn-example").addEventListener("click", () => { $("transcript").value = EXAMPLE; });
$("btn-analyze").addEventListener("click", analyze);
document.querySelectorAll(".recipient").forEach(btn =>
  btn.addEventListener("click", () => showTab(btn.dataset.tab)));

function showTab(name) {
  document.querySelectorAll(".recipient").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  ["hasta", "doktor", "yonetim"].forEach(n => $("panel-" + n).classList.toggle("hidden", n !== name));
}

async function analyze() {
  const transcript = $("transcript").value.trim();
  $("error").classList.add("hidden");
  if (!transcript) { showError("Lütfen önce bir görüşme metni girin."); return; }
  $("results").classList.add("hidden");
  $("loading").classList.remove("hidden");
  $("btn-analyze").disabled = true;
  try {
    const res = await fetch("/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || "Bilinmeyen hata");
    window.__son = data;
    renderHasta(data.hasta);
    renderDoktor(data.doktor);
    renderYonetim(data.yonetim);
    bindPdfButtons();
    showTab("hasta");
    $("results").classList.remove("hidden");
  } catch (e) {
    showError("Analiz başarısız oldu: " + e.message);
  } finally {
    $("loading").classList.add("hidden");
    $("btn-analyze").disabled = false;
  }
}

function showError(msg) {
  const el = $("error");
  el.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${esc(msg)}`;
  el.classList.remove("hidden");
}

// ---------------- HASTA ----------------
function renderHasta(d) {
  d = d || {};
  const meds = (d.ilaclar || []).length
    ? (d.ilaclar || []).map(m => `<div class="med"><i class="bi bi-capsule"></i><span>${esc(m)}</span></div>`).join("")
    : `<div class="empty-mut">İlaç önerisi belirtilmedi.</div>`;
  $("panel-hasta").innerHTML = `
    <div class="panel-head head-hasta"><span class="ph-icon"><i class="bi bi-person-heart"></i></span>
      <div class="ph-txt"><h3>Hasta raporu</h3><div class="ph-sub">sade dille görüşme özeti</div></div>
      <button class="pdf-btn" data-pdf="hasta"><i class="bi bi-file-earmark-pdf"></i> PDF indir</button></div>
    <div class="panel-body">
      <div class="sec"><div class="lead">${esc(d.ozet)}</div></div>
      <div class="sec"><div class="sec-title"><i class="bi bi-clipboard2-pulse"></i> Değerlendirme</div><div>${esc(d.tani)}</div></div>
      <div class="sec"><div class="sec-title"><i class="bi bi-check2-circle"></i> Yapmanız gerekenler</div>
        <ul class="checklist">${(d.yapilacaklar || []).map(x => `<li><i class="bi bi-check-lg"></i><span>${esc(x)}</span></li>`).join("")}</ul></div>
      <div class="sec"><div class="sec-title"><i class="bi bi-capsule-pill"></i> İlaçlar</div>${meds}</div>
      <div class="sec"><div class="sec-title"><i class="bi bi-calendar-check"></i> Kontrol</div><div>${esc(d.kontrol)}</div></div>
      <div class="sec"><div class="note-soft"><i class="bi bi-heart-pulse"></i> ${esc(d.kapanis)}</div></div>
    </div>`;
}

// ---------------- DOKTOR (detaylı epikriz) ----------------
function ozBox(title, icon, items, emptyText) {
  const list = (items || []).length
    ? `<ul>${items.map(x => `<li><i class="bi bi-dot"></i><span>${esc(x)}</span></li>`).join("")}</ul>`
    : `<div class="empty-mut">${emptyText}</div>`;
  return `<div class="oz-box"><div class="oz-t"><i class="bi bi-${icon}"></i> ${title}</div>${list}</div>`;
}

function renderDoktor(d) {
  d = d || {}; const e = d.epikriz || {}, k = d.koclugu || {}, oz = e.ozgecmis || {}, kn = e.kontrol || {};

  const meta = `
    <div class="meta-strip">
      <div class="meta-box"><div class="m-lbl">Görüşme tarihi</div><div class="m-val">${val(e.gorusmeTarihi)}</div></div>
      <div class="meta-box"><div class="m-lbl">Doktor</div><div class="m-val">${val(e.doktor)}</div></div>
      <div class="meta-box hl"><div class="m-lbl">Şikayet başlangıcı</div><div class="m-val">${val(e.baslangic)}</div></div>
      <div class="meta-box hl"><div class="m-lbl">Ağrı skoru</div><div class="m-val">${val(e.agriSkoru)}</div></div>
    </div>`;

  const fields = [["Şikayet", e.sikayet], ["Öykü", e.oyku], ["Fizik muayene", e.fizikMuayene]]
    .map(([l, v]) => `<div class="field"><div class="f-label">${l}</div><div class="f-val">${val(v)}</div></div>`).join("");

  const lab = (e.lab || []).length
    ? `<ul class="checklist">${e.lab.map(x => `<li><i class="bi bi-droplet"></i><span>${esc(x)}</span></li>`).join("")}</ul>`
    : `<div class="empty-mut">Görüşmede tetkik/lab sonucu geçmedi.</div>`;

  const icdStr = (e.icd || []).map(c => esc(c.kod)).filter(Boolean).join(", ");
  const kesinVar = !isMiss(e.kesinTani);
  const onTaniTxt = isMiss(e.onTani) ? `<span class="val-missing">belirtilmedi</span>`
    : esc(e.onTani) + (icdStr && !kesinVar ? ` <span class="icd-inline">ICD-10: ${icdStr}</span>` : "");
  const kesinTaniTxt = !kesinVar
    ? `<span class="val-missing">Görüşmede kesin tanı konmadı.</span>`
    : esc(e.kesinTani) + (icdStr ? ` <span class="icd-inline">ICD-10: ${icdStr}</span>` : "");
  const dx = `
    <div class="dx dx-on"><span class="dx-tag">Ön tanı</span><span>${onTaniTxt}</span></div>
    <div class="dx dx-kesin ${kesinVar ? "" : "missing"}">
      <span class="dx-tag">Kesin tanı</span><span>${kesinTaniTxt}</span></div>`;

  const tedavi = (e.tedavi || []).length
    ? (e.tedavi || []).map(t => `<div class="med"><i class="bi bi-capsule"></i><span>${esc(t)}</span></div>`).join("")
    : `<div class="empty-mut">Tedavi belirtilmedi.</div>`;

  const kontrol = `
    <div class="kontrol-box">
      <div class="k-line"><span class="k-lbl">Önerildi mi</span><span>${kn.onerildi === true ? "Evet" : kn.onerildi === false ? "Hayır" : "belirtilmedi"}</span></div>
      <div class="k-line"><span class="k-lbl">Zaman</span><span>${val(kn.zaman)}</span></div>
      <div class="k-line"><span class="k-lbl">Not</span><span>${val(kn.not)}</span></div>
    </div>`;

  const guclu = (k.guclu || []).map(x => `<li><i class="bi bi-check-circle-fill"></i><span>${esc(x)}</span></li>`).join("");
  const oneriler = (k.oneriler || []).map(o => `
    <div class="coach"><div class="c-an"><i class="bi bi-chat-quote"></i><span>${esc(o.an)}</span></div>
      <div class="c-oneri"><i class="bi bi-lightbulb"></i> ${esc(o.oneri)}</div></div>`).join("");

  $("panel-doktor").innerHTML = `
    <div class="panel-head head-doktor"><span class="ph-icon"><i class="bi bi-file-medical"></i></span>
      <div class="ph-txt"><h3>Doktor raporu</h3><div class="ph-sub">detaylı epikriz (sigorta/kayıt uyumlu) + iletişim koçluğu</div></div>
      <button class="pdf-btn" data-pdf="doktor"><i class="bi bi-file-earmark-pdf"></i> Epikrizi PDF indir</button></div>
    <div class="panel-body">
      <div class="sec">${meta}</div>
      <div class="sec"><div class="sec-title"><i class="bi bi-file-earmark-medical"></i> Şikayet & öykü</div>${fields}</div>
      <div class="sec"><div class="sec-title"><i class="bi bi-person-lines-fill"></i> Özgeçmiş</div>
        <div class="oz-grid">
          ${ozBox("Kronik hastalıklar", "heart-pulse", oz.kronik, "Bilinen kronik hastalık belirtilmedi.")}
          ${ozBox("Ameliyatlar", "bandaid", oz.ameliyatlar, "Geçirilmiş ameliyat belirtilmedi.")}
          ${ozBox("Kullandığı ilaçlar", "capsule", oz.ilaclar, "Düzenli ilaç belirtilmedi.")}
          ${ozBox("Alerjiler", "exclamation-diamond", oz.alerji, "Bilinen alerji belirtilmedi.")}
          ${ozBox("Alışkanlıklar", "cup-hot", oz.aliskanlik, "Belirtilmedi.")}
        </div></div>
      <div class="sec"><div class="sec-title"><i class="bi bi-people"></i> Soygeçmiş</div>
        ${(e.soygecmis || []).length
          ? `<ul class="checklist">${e.soygecmis.map(x => `<li><i class="bi bi-diagram-2"></i><span>${esc(x)}</span></li>`).join("")}</ul>`
          : `<div class="empty-mut">Ailesel/genetik hastalık belirtilmedi.</div>`}</div>
      <div class="sec"><div class="sec-title"><i class="bi bi-droplet-half"></i> Laboratuvar / tetkik</div>${lab}</div>
      <div class="sec"><div class="sec-title"><i class="bi bi-clipboard2-pulse"></i> Tanılar</div>${dx}</div>
      <div class="sec"><div class="sec-title"><i class="bi bi-capsule-pill"></i> Tedavi / ilaç uygulamaları</div>${tedavi}</div>
      <div class="sec"><div class="sec-title"><i class="bi bi-signpost-2"></i> İzlem & plan</div><div>${val(e.plan)}</div></div>
      <div class="sec"><div class="sec-title"><i class="bi bi-calendar-check"></i> Kontrol</div>${kontrol}</div>
      <div class="sec"><div class="sec-title"><i class="bi bi-hand-thumbs-up"></i> Güçlü yönler</div>
        <ul class="strong-list">${guclu || '<li class="empty-mut">—</li>'}</ul></div>
      <div class="sec"><div class="sec-title"><i class="bi bi-lightbulb"></i> İletişim önerileri</div>
        ${oneriler || '<div class="empty-mut">Öneri yok.</div>'}</div>
    </div>`;
}

// ---------------- YÖNETİM ----------------
function renderYonetim(d) {
  d = d || {}; const g = d.guvenlik || {}, s = d.skor || {};
  const durum = (g.durum || "temiz").toLowerCase();
  const durumLabel = { temiz: "Temiz", dikkat: "Dikkat", sorun: "Sorun" }[durum] || g.durum || "—";
  const durumIcon = { temiz: "shield-check", dikkat: "shield-exclamation", sorun: "shield-x" }[durum] || "shield";
  const tespitler = (g.tespitler || []).length
    ? `<ul class="checklist">${g.tespitler.map(t => `<li><i class="bi bi-exclamation-circle" style="color:var(--bad)"></i><span>${esc(t)}</span></li>`).join("")}</ul>`
    : `<div class="empty-mut">Uygunsuz / argo ifade saptanmadı.</div>`;
  const bar = (lbl, v, extra = "") => `<div class="bar-row ${extra}"><span class="br-lbl">${lbl}</span>
    <div class="bar-track"><div class="bar-fill" style="width:${Math.round(v || 0)}%"></div></div>
    <span class="br-val">${Math.round(v || 0)}</span></div>`;
  const risk = (d.risk || "yok").toLowerCase();
  const riskIcon = { yok: "check-circle", "düşük": "info-circle", orta: "exclamation-triangle", "yüksek": "exclamation-octagon" }[risk] || "info-circle";

  $("panel-yonetim").innerHTML = `
    <div class="panel-head head-yonetim"><span class="ph-icon"><i class="bi bi-shield-check"></i></span>
      <div class="ph-txt"><h3>Yönetim raporu</h3><div class="ph-sub">güvenlik, doktor skoru, verimlilik ve risk</div></div>
      <button class="pdf-btn" data-pdf="yonetim"><i class="bi bi-file-earmark-pdf"></i> PDF indir</button></div>
    <div class="panel-body">
      <div class="sec"><div class="sec-title"><i class="bi bi-shield"></i> Güvenlik / üslup</div>
        <div class="status s-${durum}"><i class="bi bi-${durumIcon}"></i> ${esc(durumLabel)}</div>
        <div style="margin-top:12px">
          <div class="lang-line"><span class="ll-tag">Hasta</span><span>${esc(g.hasta)}</span></div>
          <div class="lang-line"><span class="ll-tag">Doktor</span><span>${esc(g.doktor)}</span></div></div>
        <div style="margin-top:10px">${tespitler}</div></div>

      <div class="sec"><div class="sec-title"><i class="bi bi-speedometer2"></i> Doktor skoru <span class="scale">(0-100)</span></div>
        <div class="score-top">
          <div class="score-big"><div class="sb-num">${Math.round(s.genel || 0)}</div><div class="sb-lbl">GENEL</div></div>
          <div class="score-bars">
            ${bar("Empati", s.empati)}
            ${bar("Netlik", s.netlik)}
            ${bar("Dinleme", s.dinleme)}
            ${bar("Verimlilik", s.verimlilik)}
          </div></div>
        ${d.verimlilikNotu ? `<div class="vr-note"><i class="bi bi-stopwatch"></i> <strong>Verimlilik notu:</strong> ${esc(d.verimlilikNotu)}</div>` : ""}</div>

      <div class="sec"><div class="sec-title"><i class="bi bi-clipboard2-data"></i> Genel değerlendirme</div><div>${esc(d.degerlendirme)}</div></div>
      <div class="sec"><div class="sec-title"><i class="bi bi-flag"></i> Risk bayrağı</div>
        <div class="risk risk-${risk}"><i class="bi bi-${riskIcon}"></i> <strong>${esc((d.risk || "yok").toUpperCase())}</strong></div></div>
    </div>`;
}


// ---------------- PDF indirme ----------------
function bindPdfButtons() {
  document.querySelectorAll(".pdf-btn").forEach(btn => {
    btn.onclick = () => downloadPdf(btn);
  });
}

async function downloadPdf(btn) {
  const rec = btn.dataset.pdf;
  const data = window.__son && window.__son[rec];
  if (!data) return;
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Hazırlanıyor…';
  try {
    const res = await fetch("/pdf", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rec, data })
    });
    if (!res.ok) throw new Error("PDF hatası");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = ({ hasta: "hasta_ozeti", doktor: "epikriz", yonetim: "yonetim_raporu" }[rec]) + ".pdf";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert("PDF indirilemedi: " + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}
