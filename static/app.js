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

$("btn-example").addEventListener("click", () => { $("transcript").value = EXAMPLE; lastTranscribeUsage = null; lastAudioId = null; });
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
      body: JSON.stringify({ transcript, audio_id: lastAudioId, stt_usage: lastTranscribeUsage })
    });
    const data = await readApiResponse(res);
    if (!res.ok || data.error) throw new Error(formatApiError(data));
    window.__son = data;
    renderHasta(data.hasta);
    renderDoktor(data.doktor);
    renderYonetim(data.yonetim);
    renderMonitor(data.usage, lastTranscribeUsage);
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

async function readApiResponse(res) {
  const raw = await res.text();
  if (!raw) return {};
  try { return JSON.parse(raw); }
  catch (_) {
    if ([502, 503, 504].includes(res.status)) {
      return {error: "Sunucu geçici olarak yanıt veremedi. Lütfen biraz sonra tekrar deneyin."};
    }
    return {error: "Sunucudan beklenmeyen bir yanıt geldi. Lütfen tekrar deneyin."};
  }
}

function formatApiError(data) {
  const id = data && data.error_id ? ` (Hata kodu: ${data.error_id})` : "";
  return ((data && data.error) || "Bilinmeyen hata") + id;
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

/* ---------------- Ses -> metin ---------------- */
let mediaRec=null, recChunks=[], recStream=null, micTestStream=null;
let micAudioContext=null, micAnalyser=null, micSource=null, micMeterFrame=null, micSilenceTimer=null;
let recordPeak=null, recordingDeviceLost=false, micTestActive=false;
const MIC_SIGNAL_THRESHOLD=0.006;
const audStatus=()=>$("audio-status");
$("btn-upload").addEventListener("click",()=>$("audio-file").click());
$("audio-file").addEventListener("change",e=>{const f=e.target.files[0];if(f)sendAudio(f,f.name);e.target.value="";});
$("btn-rec").addEventListener("click",toggleRec);
$("btn-mic-test").addEventListener("click",toggleMicTest);
$("mic-select").addEventListener("change",async()=>{
  if(micTestActive){stopMicTest(false);await startMicTest();}
});

function micErrorMessage(e){
  if(!window.isSecureContext)return "Mikrofon yalnızca HTTPS bağlantısında kullanılabilir.";
  if(e&&e.name==="NotAllowedError")return "Mikrofon izni kapalı. Tarayıcıdaki kilit simgesinden mikrofon iznini açın.";
  if(e&&e.name==="NotFoundError")return "Kullanılabilir mikrofon bulunamadı. Windows ses girişini kontrol edin.";
  if(e&&e.name==="NotReadableError")return "Mikrofon başka bir uygulama tarafından kullanılıyor veya Windows erişimi engelliyor.";
  return "Mikrofon açılamadı. Mikrofon seçimini ve Windows ses ayarını kontrol edin.";
}

function micConstraints(useSelected=true){
  const selected=$("mic-select").value;
  const audio={channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true};
  if(useSelected&&selected&&selected!=="default")audio.deviceId={exact:selected};
  return {audio};
}

async function refreshMicDevices(preferredId=""){
  if(!navigator.mediaDevices||!navigator.mediaDevices.enumerateDevices)return [];
  const select=$("mic-select");
  const previous=preferredId||select.value||"default";
  const inputs=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==="audioinput");
  select.innerHTML="";
  const defaultOption=document.createElement("option");
  defaultOption.value="default";defaultOption.textContent="Varsayılan mikrofon";select.appendChild(defaultOption);
  inputs.filter(d=>d.deviceId&&d.deviceId!=="default").forEach((device,index)=>{
    const option=document.createElement("option");
    option.value=device.deviceId;
    option.textContent=device.label||`Mikrofon ${index+1}`;
    select.appendChild(option);
  });
  select.value=[...select.options].some(o=>o.value===previous)?previous:"default";
  return inputs;
}

async function openMicStream(){
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia||!window.MediaRecorder){
    throw new Error("Bu tarayıcı mikrofon kaydını desteklemiyor.");
  }
  let stream;
  try{
    stream=await navigator.mediaDevices.getUserMedia(micConstraints(true));
  }catch(e){
    const selected=$("mic-select").value;
    if(selected!=="default"&&(e.name==="OverconstrainedError"||e.name==="NotFoundError")){
      $("mic-select").value="default";
      stream=await navigator.mediaDevices.getUserMedia(micConstraints(false));
    }else{throw e;}
  }
  const track=stream.getAudioTracks()[0];
  if(!track||track.readyState!=="live"){
    stream.getTracks().forEach(t=>t.stop());
    throw new Error("Seçilen mikrofon aktif değil.");
  }
  const actualId=(track.getSettings&&track.getSettings().deviceId)||"";
  await refreshMicDevices(actualId);
  $("mic-device").textContent=`Aktif: ${track.label||$("mic-select").selectedOptions[0]?.textContent||"Mikrofon"}`;
  return stream;
}

function stopMeter(){
  if(micMeterFrame)cancelAnimationFrame(micMeterFrame);
  if(micSilenceTimer)clearTimeout(micSilenceTimer);
  micMeterFrame=micSilenceTimer=null;micAnalyser=micSource=null;
  if(micAudioContext){Promise.resolve(micAudioContext.close()).catch(()=>{});micAudioContext=null;}
  $("mic-meter-fill").style.width="0%";
  $("mic-meter").className="mic-meter";
  $("mic-meter").setAttribute("aria-valuenow","0");
  $("mic-level").textContent="Ses seviyesi: —";
}

async function startMeter(stream){
  stopMeter();recordPeak=0;
  const AudioContextClass=window.AudioContext||window.webkitAudioContext;
  if(!AudioContextClass){recordPeak=null;$("mic-level").textContent="Ses ölçümü desteklenmiyor";return;}
  try{
    micAudioContext=new AudioContextClass();
    if(micAudioContext.state==="suspended")await micAudioContext.resume();
    micAnalyser=micAudioContext.createAnalyser();micAnalyser.fftSize=2048;
    micSource=micAudioContext.createMediaStreamSource(stream);micSource.connect(micAnalyser);
  }catch(_){stopMeter();recordPeak=null;$("mic-level").textContent="Ses ölçümü desteklenmiyor";return;}
  const samples=new Uint8Array(micAnalyser.fftSize);
  const meter=$("mic-meter"),fill=$("mic-meter-fill");
  const draw=()=>{
    if(!micAnalyser)return;
    micAnalyser.getByteTimeDomainData(samples);
    let sum=0;
    for(const sample of samples){const normalized=(sample-128)/128;sum+=normalized*normalized;}
    const rms=Math.sqrt(sum/samples.length);
    recordPeak=Math.max(recordPeak||0,rms);
    const db=rms>0?20*Math.log10(rms):-60;
    const percent=Math.max(0,Math.min(100,Math.round((db+60)*2)));
    fill.style.width=`${percent}%`;meter.setAttribute("aria-valuenow",String(percent));
    meter.className=`mic-meter ${rms>=0.012?"is-loud":rms>=MIC_SIGNAL_THRESHOLD?"is-live":"is-silent"}`;
    $("mic-level").textContent=rms>=MIC_SIGNAL_THRESHOLD?`Ses geliyor: ${Math.round(db)} dB`:"Ses yok / çok düşük";
    micMeterFrame=requestAnimationFrame(draw);
  };
  draw();
  micSilenceTimer=setTimeout(()=>{
    if(recordPeak!==null&&recordPeak<MIC_SIGNAL_THRESHOLD){
      audStatus().innerHTML='<i class="bi bi-exclamation-triangle" style="color:var(--warn)"></i> Mikrofondan ses gelmiyor. Listeden laptop mikrofonunu seçin veya Windows giriş ayarını kontrol edin.';
    }
  },2500);
}

function stopStream(stream){if(stream)stream.getTracks().forEach(t=>t.stop());}

async function toggleMicTest(){
  if(micTestActive){stopMicTest(true);return;}
  await startMicTest();
}

async function startMicTest(){
  if(mediaRec&&mediaRec.state==="recording")return;
  const btn=$("btn-mic-test");btn.disabled=true;
  try{
    micTestStream=await openMicStream();micTestActive=true;
    micTestStream.getAudioTracks()[0].addEventListener("ended",()=>{
      if(micTestActive){stopMicTest(false);audStatus().textContent="Mikrofon bağlantısı kesildi. Listeden laptop mikrofonunu seçip yeniden test edin.";}
    });
    await startMeter(micTestStream);
    btn.innerHTML='<i class="bi bi-stop-circle"></i> Testi bitir';btn.classList.add("test-on");
    audStatus().textContent="Mikrofon testi açık — konuşunca seviye çubuğu hareket etmeli.";
  }catch(e){audStatus().textContent=e.message&&e.message.startsWith("Bu tarayıcı")?e.message:micErrorMessage(e);}
  finally{btn.disabled=false;}
}

function stopMicTest(showMessage){
  micTestActive=false;stopMeter();stopStream(micTestStream);micTestStream=null;
  const btn=$("btn-mic-test");btn.innerHTML='<i class="bi bi-soundwave"></i> Mikrofonu test et';btn.classList.remove("test-on");
  if(showMessage)audStatus().textContent="Mikrofon testi kapatıldı.";
}

function recordingFilename(mime){
  if((mime||"").includes("mp4"))return "kayit.m4a";
  if((mime||"").includes("ogg"))return "kayit.ogg";
  return "kayit.webm";
}

async function toggleRec(){
  const btn=$("btn-rec");
  if(mediaRec&&mediaRec.state==="recording"){mediaRec.stop();return;}
  if(micTestActive)stopMicTest(false);
  btn.disabled=true;$("btn-mic-test").disabled=true;$("mic-select").disabled=true;
  try{recStream=await openMicStream();}
  catch(e){
    audStatus().textContent=e.message&&e.message.startsWith("Bu tarayıcı")?e.message:micErrorMessage(e);
    btn.disabled=false;$("btn-mic-test").disabled=false;$("mic-select").disabled=false;return;
  }
  recChunks=[];recordingDeviceLost=false;
  await startMeter(recStream);
  mediaRec=new MediaRecorder(recStream);
  mediaRec.ondataavailable=ev=>{if(ev.data.size>0)recChunks.push(ev.data);};
  recStream.getAudioTracks()[0].addEventListener("ended",()=>{
    if(mediaRec&&mediaRec.state==="recording"){recordingDeviceLost=true;mediaRec.stop();}
  });
  mediaRec.onstop=()=>{
    const mime=mediaRec.mimeType||"audio/webm";
    const blob=new Blob(recChunks,{type:mime});
    const peak=recordPeak;
    stopMeter();stopStream(recStream);recStream=null;
    btn.innerHTML='<i class="bi bi-mic"></i> Kaydet';btn.classList.remove("rec-on");
    btn.disabled=false;$("btn-mic-test").disabled=false;$("mic-select").disabled=false;
    mediaRec=null;
    if(recordingDeviceLost){audStatus().textContent="Mikrofon bağlantısı kayıt sırasında kesildi. Mikrofonu yeniden seçip tekrar deneyin.";return;}
    if(peak!==null&&peak<MIC_SIGNAL_THRESHOLD){audStatus().textContent="Kayıtta ses algılanmadı; boş kayıt API'ye gönderilmedi. Listeden doğru mikrofonu seçip test edin.";return;}
    if(blob.size<1000){audStatus().textContent="Kayıt çok kısa veya boş; API'ye gönderilmedi.";return;}
    sendAudio(blob,recordingFilename(mime));
  };
  mediaRec.onerror=()=>{audStatus().textContent="Tarayıcı ses kaydını tamamlayamadı. Tekrar deneyin.";};
  mediaRec.start(1000);
  btn.innerHTML='<i class="bi bi-stop-circle"></i> Durdur';btn.classList.add("rec-on");
  btn.disabled=false;
  audStatus().textContent="Kaydediliyor… konuşurken seviye çubuğunun hareket ettiğini kontrol edin.";
}

async function handleDeviceChange(){
  try{
    const selected=$("mic-select").value;
    const inputs=await refreshMicDevices();
    if(selected!=="default"&&!inputs.some(d=>d.deviceId===selected)){
      audStatus().textContent="Seçili mikrofon çıkarıldı. Varsayılan/laptop mikrofonuna geçildi; kayıttan önce test edin.";
    }
  }catch(_){audStatus().textContent="Mikrofon listesi yenilenemedi; sayfayı yenileyip tekrar test edin.";}
}

if(navigator.mediaDevices){
  refreshMicDevices().catch(()=>{});
  if(navigator.mediaDevices.addEventListener)navigator.mediaDevices.addEventListener("devicechange",handleDeviceChange);
}else{
  $("btn-rec").disabled=true;$("btn-mic-test").disabled=true;$("mic-select").disabled=true;
  audStatus().textContent="Bu tarayıcı mikrofon erişimini desteklemiyor.";
}

async function sendAudio(fileOrBlob,name){
  const fd=new FormData();
  fd.append("file",fileOrBlob,name||"ses");
  audStatus().innerHTML='<span class="mini-spin"></span> Ses metne dökülüyor…';
  try{
    const res=await fetch("/transcribe",{method:"POST",body:fd});
    const data=await readApiResponse(res);
    if(!res.ok||data.error)throw new Error(formatApiError(data));
    $("transcript").value=data.transcript;
    lastTranscribeUsage = data.usage || null;
    lastAudioId = data.audio_id || null;
    let ek="";
    if(data.usage){
      const olcu=data.usage.total ? `${fmtNum(data.usage.total)} token` : `${fmtNum(data.usage.audio_seconds)} sn ses`;
      const rol=data.usage.role_usage;
      const yedek=data.usage.fallback_usage;
      const rolEk=rol ? ` + rol tespiti: ${fmtNum(rol.total)} token, ${fmtUsd(rol.cost_usd)}` : "";
      const yedekEk=yedek ? ` + yedek STT: ${fmtNum(yedek.audio_seconds)} sn, ${fmtUsd(yedek.cost_usd)}` : "";
      ek=` <span class="mon-sub">(${olcu}, ${fmtUsd(data.usage.cost_usd)}${yedekEk}${rolEk})</span>`;
      if(yedek) ek += ' <span class="mon-sub">İlk STT boş döndü; yedek OpenAI modeli kullanıldı.</span>';
      if(data.usage.provider_fallback_used) ek += ' <span class="mon-sub">Scribe kullanılamadı; OpenAI yedeği kullanıldı.</span>';
      ek += String(data.usage.role_method||"").startsWith("semantic")
        ? ' <span class="mon-sub">Doktor/hasta anlamdan belirlendi.</span>'
        : ' <span class="mon-sub">Rol kesinleşmedi; etiketleri kontrol edin.</span>';
    }
    audStatus().innerHTML='<i class="bi bi-check-circle" style="color:var(--ok)"></i> Metne döküldü — kontrol edip “Analiz et”e basın.'+ek;
  }catch(e){audStatus().textContent="Ses metne dökülemedi: "+e.message;}
}


/* ---------------- İzleme (token / maliyet / süre) ---------------- */
function fmtNum(n){return Number(n||0).toLocaleString("tr-TR");}
function fmtUsd(c){
  if(c==null||c==="")return "—";
  c=Number(c);
  const d = c>0 && c<0.01 ? 6 : 4;
  return "$"+c.toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d});
}
function monRow(label, u){
  const sub = u.total
    ? `<span class="mon-sub">(${fmtNum(u.input)}+${fmtNum(u.output)})</span>`
    : (u.audio_seconds!=null ? `<span class="mon-sub">(${fmtNum(u.audio_seconds)} sn ses)</span>` : "");
  const sure = (u.seconds!=null) ? (u.seconds + " sn") : "—";
  return `<div class="mon-row"><span>${label}</span><span>${fmtNum(u.total)} ${sub}</span><span>${fmtUsd(u.cost_usd)}</span><span>${sure}</span></div>`;
}
function renderMonitor(analiz, ses){
  const box=$("monitor");
  if(!analiz){ box.classList.add("hidden"); return; }
  const model=((document.querySelector(".pill-model")||{}).textContent||"Gemini").trim();
  const sttModel=ses ? `${ses.provider||"STT"} · ${ses.model||""}` : "";
  const rows=[];
  if(ses){ rows.push(monRow("Ses → metin", ses)); }
  const yedek=ses&&ses.fallback_usage ? ses.fallback_usage : null;
  if(yedek){ rows.push(monRow("Yedek ses → metin", yedek)); }
  const rol=ses&&ses.role_usage ? ses.role_usage : null;
  if(rol){ rows.push(monRow("Doktor/hasta rol tespiti", rol)); }
  rows.push(monRow("Analiz (3 rapor)", analiz));
  const totTok=(ses?ses.total:0)+(yedek?yedek.total:0)+(rol?rol.total:0)+analiz.total;
  const totCost=(ses&&ses.cost_usd!=null?Number(ses.cost_usd):0)
    +(yedek?Number(yedek.cost_usd||0):0)+(rol?Number(rol.cost_usd||0):0)+Number(analiz.cost_usd||0);
  box.innerHTML=`
    <div class="mon-title"><i class="bi bi-graph-up-arrow"></i> İzleme · maliyet <span class="mon-model">${model}</span></div>
    <div class="mon-table">
      <div class="mon-hd"><span>İşlem</span><span>Token</span><span>Maliyet</span><span>Süre</span></div>
      ${rows.join("")}
      <div class="mon-row mon-tot"><span>TOPLAM</span><span>${fmtNum(totTok)}</span><span>${fmtUsd(totCost)}</span><span>—</span></div>
    </div>
    <div class="mon-foot">Ses dökümü ${sttModel||"STT API"}; rol tespiti ve üç rapor analizi Gemini API ile çalışır.
      Scribe kullanılamazsa mevcut OpenAI STT otomatik yedek olarak çağrılır.</div>`;
  box.classList.remove("hidden");
}
