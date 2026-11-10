/* ================= Doktor paneli · gorusme kaydi =================
   Mobil uygulamadaki akisin aynisi:
     is listesinden hasta sec -> kaydi baslat -> durdur
     -> /doctor/api/transcriptions (ses arka planda metne dokulur)
     -> /doctor/api/analyze/stream (raporlar + COMED taslagi)
     -> kayit doktora ve secili COMED hastasina baglanir.
   Sonrasi degismez: rapor acilir, "COMED'e aktar" ayni dugmedir.
   doctor.js'teki $, json, toast, overview, selectedPatient, load ve
   openDetail kullanilir; burada ikinci bir esc() TANIMLAMA. */

const REC_SIGNAL_THRESHOLD = 0.006;     // app.js ile ayni sessizlik esigi
const REC_POLL_MS = 2500;
const REC_POLL_LIMIT_MS = 20 * 60 * 1000;

const rec = {
  state: "idle",        // idle | recording | uploading | transcribing | analyzing | error
  patient: null,        // kayit basladiginda kilitlenen hasta
  media: null, stream: null, chunks: [],
  blob: null, filename: "",
  transcription: null,  // {transcript, usage, audio_id}
  startedAt: 0, timer: null,
  peak: null, meterFrame: null, audioCtx: null,
  progress: "", error: "",
};

function recPatientJson(p) {
  // Mobil uygulamanin gonderdigi alanlarla birebir ayni (models.dart toJson).
  const keys = ["visit_id", "clinical_card_id", "patient_id", "patient_name", "patient_no",
                "protocol_no", "department", "doctor_name", "task", "status", "clinical_card_url"];
  return Object.fromEntries(keys.map(k => [k, String(p?.[k] ?? "")]));
}

function recBusy() { return !["idle", "error"].includes(rec.state); }

function recClock() {
  const sec = Math.max(0, Math.floor((Date.now() - rec.startedAt) / 1000));
  return `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
}

function recPatientLabel(p) {
  const name = esc(p?.patient_name || "İsimsiz hasta");
  const sub = [p?.protocol_no || (p?.visit_id ? `V-${p.visit_id}` : ""), p?.patient_no && `No ${p.patient_no}`]
    .filter(Boolean).map(esc).join(" · ");
  return `<b>${name}</b>${sub ? `<small>${sub}</small>` : ""}`;
}

function renderRecorder() {
  const box = $("recorder");
  if (!box) return;
  const p = recBusy() || rec.state === "error" ? rec.patient : selectedPatient;
  if (rec.state === "idle" && !p) {
    box.innerHTML = `<div class="rc-bar rc-idle">
      <span class="rc-icon"><i class="bi bi-mic"></i></span>
      <span class="rc-copy"><b>Görüşme kaydı</b><small>Kayıt almak için yukarıdaki iş listesinden hastayı seçin.</small></span>
      <button class="rc-btn start" disabled><i class="bi bi-record-circle"></i> Kaydı başlat</button>
    </div>`;
    return;
  }
  if (rec.state === "idle") {
    box.innerHTML = `<div class="rc-bar rc-ready">
      <span class="rc-icon"><i class="bi bi-mic-fill"></i></span>
      <span class="rc-copy">${recPatientLabel(p)}</span>
      <button class="rc-btn start" data-rec="start"><i class="bi bi-record-circle"></i> Kaydı başlat</button>
    </div>`;
    return;
  }
  if (rec.state === "recording") {
    box.innerHTML = `<div class="rc-bar rc-live">
      <span class="rc-icon live"><i class="bi bi-mic-fill"></i></span>
      <span class="rc-copy">${recPatientLabel(p)}<small class="rc-hint">Kaydediliyor — konuşurken seviye çubuğu hareket etmeli.</small></span>
      <span class="rc-clock" id="rc-clock">${recClock()}</span>
      <span class="rc-meter"><span id="rc-level"></span></span>
      <button class="rc-btn stop" data-rec="stop"><i class="bi bi-stop-circle"></i> Durdur ve analiz et</button>
      <button class="rc-btn ghost" data-rec="cancel" title="Kaydı sil, gönderme"><i class="bi bi-x-lg"></i> İptal</button>
    </div>`;
    return;
  }
  if (rec.state === "error") {
    box.innerHTML = `<div class="rc-bar rc-error">
      <span class="rc-icon err"><i class="bi bi-exclamation-triangle"></i></span>
      <span class="rc-copy">${recPatientLabel(p)}<small>${esc(rec.error)}</small></span>
      ${rec.blob ? '<button class="rc-btn start" data-rec="retry"><i class="bi bi-arrow-clockwise"></i> Tekrar dene</button>' : ""}
      <button class="rc-btn ghost" data-rec="reset"><i class="bi bi-x-lg"></i> Kapat</button>
    </div>`;
    return;
  }
  const steps = [["uploading", "Ses yükleniyor"], ["transcribing", "Metne dökülüyor"], ["analyzing", "Raporlar hazırlanıyor"]];
  const at = steps.findIndex(([key]) => key === rec.state);
  box.innerHTML = `<div class="rc-bar rc-work">
    <span class="rc-icon"><span class="rc-spin"></span></span>
    <span class="rc-copy">${recPatientLabel(p)}<small>${esc(rec.progress || "İşleniyor…")}</small></span>
    <span class="rc-steps">${steps.map(([key, label], i) =>
      `<span class="rc-step ${i < at ? "done" : i === at ? "active" : ""}">${i < at ? '<i class="bi bi-check2"></i>' : i + 1} ${label}</span>`
    ).join("")}</span>
  </div>`;
}

function recSet(state, extra = {}) {
  Object.assign(rec, {state}, extra);
  renderRecorder();
}

/* ---------- kayit ---------- */
function recFilename(mime) {
  if ((mime || "").includes("mp4")) return "klinot-kayit.m4a";
  if ((mime || "").includes("ogg")) return "klinot-kayit.ogg";
  return "klinot-kayit.webm";
}

function recMicError(e) {
  if (e?.name === "NotAllowedError") return "Mikrofon izni verilmedi. Adres çubuğundaki kilit simgesinden mikrofona izin verin.";
  if (e?.name === "NotFoundError") return "Mikrofon bulunamadı. Mikrofonun takılı olduğundan emin olun.";
  if (e?.name === "NotReadableError") return "Mikrofon başka bir uygulama tarafından kullanılıyor.";
  return e?.message || "Mikrofon açılamadı.";
}

function recStopMeter() {
  if (rec.meterFrame) cancelAnimationFrame(rec.meterFrame);
  rec.meterFrame = null;
  if (rec.audioCtx) { Promise.resolve(rec.audioCtx.close()).catch(() => {}); rec.audioCtx = null; }
}

function recStartMeter(stream) {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    rec.audioCtx = new Ctx();
    const analyser = rec.audioCtx.createAnalyser();
    analyser.fftSize = 1024;
    rec.audioCtx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Float32Array(analyser.fftSize);
    rec.peak = 0;
    const tick = () => {
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (const v of buf) sum += v * v;
      const rms = Math.sqrt(sum / buf.length);
      rec.peak = Math.max(rec.peak || 0, rms);
      const bar = $("rc-level");
      if (bar) {
        bar.style.width = `${Math.min(100, Math.round(rms * 900))}%`;
        bar.className = rms >= REC_SIGNAL_THRESHOLD ? "on" : "";
      }
      rec.meterFrame = requestAnimationFrame(tick);
    };
    tick();
  } catch (_) { rec.peak = null; }
}

function recReleaseMic() {
  recStopMeter();
  clearInterval(rec.timer);
  rec.timer = null;
  rec.stream?.getTracks().forEach(t => t.stop());
  rec.stream = null;
}

async function recStart() {
  if (recBusy() || !selectedPatient) return;
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    recSet("error", {patient: selectedPatient, error: "Bu tarayıcı mikrofon kaydını desteklemiyor.", blob: null});
    return;
  }
  const patient = selectedPatient;
  try {
    rec.stream = await navigator.mediaDevices.getUserMedia({
      audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1},
    });
  } catch (e) {
    recSet("error", {patient, error: recMicError(e), blob: null});
    return;
  }
  rec.chunks = [];
  rec.blob = null;
  rec.transcription = null;
  const options = MediaRecorder.isTypeSupported?.("audio/webm;codecs=opus")
    ? {mimeType: "audio/webm;codecs=opus", audioBitsPerSecond: 64000}
    : {audioBitsPerSecond: 64000};
  rec.media = new MediaRecorder(rec.stream, options);
  rec.media.ondataavailable = ev => { if (ev.data.size > 0) rec.chunks.push(ev.data); };
  rec.media.onstop = recFinished;
  rec.stream.getAudioTracks()[0]?.addEventListener("ended", () => {
    if (rec.media?.state === "recording") { rec.lost = true; rec.media.stop(); }
  });
  rec.lost = false;
  rec.cancelled = false;
  rec.startedAt = Date.now();
  rec.media.start(1000);
  recSet("recording", {patient, error: ""});
  recStartMeter(rec.stream);
  rec.timer = setInterval(() => { const c = $("rc-clock"); if (c) c.textContent = recClock(); }, 500);
}

function recStop(cancel = false) {
  if (rec.media?.state !== "recording") return;
  rec.cancelled = cancel;
  rec.media.stop();
}

function recFinished() {
  const mime = rec.media?.mimeType || "audio/webm";
  const blob = new Blob(rec.chunks, {type: mime});
  const peak = rec.peak;
  recReleaseMic();
  rec.media = null;
  rec.chunks = [];
  if (rec.cancelled) { recSet("idle", {patient: null, blob: null}); toast("Kayıt iptal edildi, gönderilmedi."); return; }
  if (rec.lost) { recSet("error", {error: "Mikrofon bağlantısı kayıt sırasında kesildi.", blob: null}); return; }
  if (peak !== null && peak < REC_SIGNAL_THRESHOLD) {
    recSet("error", {error: "Kayıtta ses algılanmadı; boş kayıt gönderilmedi. Mikrofonu kontrol edin.", blob: null});
    return;
  }
  if (blob.size < 1000) { recSet("error", {error: "Kayıt çok kısa veya boş; gönderilmedi.", blob: null}); return; }
  rec.blob = blob;
  rec.filename = recFilename(mime);
  recProcess();
}

/* ---------- gonderim: dokum + analiz ---------- */
async function recTranscribe() {
  recSet("uploading", {progress: "Ses sunucuya gönderiliyor…"});
  const fd = new FormData();
  fd.append("file", rec.blob, rec.filename);
  const res = await fetch("/doctor/api/transcriptions", {method: "POST", body: fd});
  let job = await res.json().catch(() => ({}));
  if (res.status === 401) throw new Error("Oturum sona erdi. Sayfayı yenileyip tekrar giriş yapın.");
  if (!res.ok) throw new Error(job.detail || job.error || `Ses gönderilemedi (HTTP ${res.status})`);
  recSet("transcribing", {progress: "Ses metne dökülüyor… uzun kayıtlarda birkaç dakika sürebilir."});
  const until = Date.now() + REC_POLL_LIMIT_MS;
  while (job.status !== "completed") {
    if (job.status === "failed") throw new Error(job.error || "Ses metne dökülemedi.");
    if (Date.now() > until) throw new Error("Ses dökümü çok uzun sürdü. Tekrar deneyin.");
    await new Promise(r => setTimeout(r, REC_POLL_MS));
    job = await json(`/doctor/api/transcriptions/${encodeURIComponent(job.job_id)}`);
  }
  if (!String(job.transcript || "").trim()) throw new Error("Kayıtta çevrilebilir konuşma bulunamadı.");
  return {transcript: job.transcript, usage: job.usage || {}, audio_id: job.audio_id || job.job_id};
}

async function recAnalyze(tr) {
  recSet("analyzing", {progress: "Raporlar hazırlanıyor…"});
  const res = await fetch("/doctor/api/analyze/stream", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      transcript: tr.transcript,
      audio_id: tr.audio_id,
      stt_usage: tr.usage,
      source: "doctor_web",
      client_version: $("recorder")?.dataset.version || "",
      metadata: {platform: "web", comed_patient: recPatientJson(rec.patient)},
    }),
  });
  if (res.status === 401) throw new Error("Oturum sona erdi. Sayfayı yenileyip tekrar giriş yapın.");
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || data.error || `Analiz başlatılamadı (HTTP ${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", result = null;
  const handle = (line) => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === "progress") {
      const done = Math.min(event.completed || 0, event.total || 3);
      rec.progress = `Raporlar hazırlanıyor… (${done}/${event.total || 3})`;
      renderRecorder();
    } else if (event.type === "error") {
      throw new Error(event.error + (event.error_id ? ` (hata kodu: ${event.error_id})` : ""));
    } else if (event.type === "result") {
      result = event.data;
    }
  };
  while (true) {
    const {value, done} = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    lines.forEach(handle);
    if (done) break;
  }
  handle(buffer);
  if (!result) throw new Error("Analiz sonucu alınamadı.");
  if (result.kayit_hatasi || !result.kayit_id) throw new Error("Analiz bitti ama kayıt saklanamadı: " + (result.kayit_hatasi || "bilinmeyen hata"));
  return result;
}

async function recProcess() {
  try {
    // Dokum basariliysa "Tekrar dene" yalniz analizi yineler, sesi yeniden gondermez.
    if (!rec.transcription) rec.transcription = await recTranscribe();
    const result = await recAnalyze(rec.transcription);
    const patient = rec.patient;
    recSet("idle", {patient: null, blob: null, transcription: null, progress: ""});
    toast("Görüşme analiz edildi. Raporu kontrol edip COMED'e aktarabilirsiniz.");
    // Yeni kayit listede o hastanin altinda acik gelsin.
    selectedPatient = overview.worklist.find(p => patientKey(p) === patientKey(patient)) || patient;
    await load();
    const id = String(result.kayit_id);
    if ($("det-" + id)) {
      await openDetail(id, "doktor");
      $("det-" + id)?.closest(".rec-item")?.scrollIntoView({behavior: "smooth", block: "start"});
    }
  } catch (e) {
    recSet("error", {error: e.message || String(e)});
  }
}

/* ---------- olaylar ---------- */
document.addEventListener("click", (e) => {
  // Hasta secimi doctor.js'te degisir; onbellekte eski doctor.js kalsa da
  // cubuk yeni secimi gostersin diye her tiklamadan sonra yeniden cizilir.
  if (e.target.closest("[data-patient], #filtre-temizle, #date-clear")) setTimeout(renderRecorder, 0);
  const btn = e.target.closest("[data-rec]");
  if (!btn) return;
  const act = btn.dataset.rec;
  if (act === "start") recStart();
  else if (act === "stop") recStop(false);
  else if (act === "cancel") recStop(true);
  else if (act === "retry") recProcess();
  else if (act === "reset") recSet("idle", {patient: null, blob: null, transcription: null, error: ""});
});

// Kayit ya da analiz surerken sayfadan cikilirsa gorusme kaybolur.
window.addEventListener("beforeunload", (e) => {
  if (rec.state === "recording" || recBusy()) { e.preventDefault(); e.returnValue = ""; }
});

renderRecorder();
