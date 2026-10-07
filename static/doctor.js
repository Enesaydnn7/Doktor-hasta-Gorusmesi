let overview={records:[],worklist:[]},selectedPatient=null,selectedRecord=null,activeTransfer=null;
let refreshTimer=null,transferTimer=null,loading=false;
const $=(id)=>document.getElementById(id);
function toast(message,error=false){const el=$("toast");el.textContent=message;el.className=error?"show error":"show";setTimeout(()=>el.className="",4500)}
// esc / val / isMiss ve rapor render fonksiyonlari report_view.js icinde
// tanimlidir; yonetici paneliyle ayni katman kullanilir.
let activeTab="doktor";
async function json(url,options={}){const response=await fetch(url,{...options,headers:{Accept:"application/json",...(options.body?{"Content-Type":"application/json"}:{}),...(options.headers||{})}});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||data.error||`HTTP ${response.status}`);return data}
function patientKey(p){return String(p?.visit_id||"")}
function recordMatchesPatient(record,patient){const linked=record?.metadata?.comed_patient||{};return Boolean(linked.visit_id)&&String(linked.visit_id)===patientKey(patient)}
function visibleRecords(){if(!selectedPatient)return overview.records;return overview.records.filter(r=>recordMatchesPatient(r,selectedPatient))}
function renderStats(){
  $("stats").innerHTML=`<div class="stat"><small>COMED HASTASI</small><strong>${overview.worklist.length}</strong></div><div class="stat"><small>GÖRÜŞME RAPORU</small><strong>${overview.stats?.kayit||overview.records.length||0}</strong></div>`;
}
function renderWorklist(){
  $("worklist-count").textContent=overview.worklist.length;
  $("worklist").innerHTML=overview.worklist.length?overview.worklist.map((p,i)=>`<button class="patient-card" data-patient="${i}"><span class="patient-avatar">${esc((p.patient_name||"H").trim().charAt(0).toUpperCase())}</span><span class="patient-copy"><strong>${esc(p.patient_name)}</strong><small>${esc(p.protocol_no||p.visit_id)} · ${esc(p.department||p.task||"COMED")}</small><em>${esc(p.status||"Görüşme bekliyor")}</em></span><span class="patient-arrow">›</span></button>`).join(""):'<div class="empty">Bu doktor için eşitlenmiş COMED hastası yok. Eklentiyi aynı doktor hesabıyla bağlayıp COMED iş listesini açın.</div>';
  document.querySelectorAll("[data-patient]").forEach(el=>el.onclick=()=>openPatient(+el.dataset.patient));
}
function renderRecords(){
  const records=visibleRecords();
  $("record-count").textContent=records.length;
  $("records").innerHTML=records.length?records.map((r,i)=>`<button class="item ${selectedRecord?.id===r.id?'selected':''}" data-record="${i}"><strong>#${r.id} · ${esc(r.ozet||"Görüşme")}</strong>${r.patient_submitted?'<em class="patient-submitted">Hastadan gelen görüşme</em>':''}<span>${esc(r.olusturma)}${r.ses_var?' · Ses kaydı var':''}</span></button>`).join(""):'<div class="empty">Bu hasta için aktarılabilir görüşme raporu henüz yok.</div>';
  document.querySelectorAll("[data-record]").forEach(el=>el.onclick=()=>selectRecord(records[+el.dataset.record]));
}
function render(){renderStats();renderWorklist();if(selectedPatient)renderRecords();updateSelection()}
async function openPatient(index){
  selectedPatient=overview.worklist[index];selectedRecord=null;activeTransfer=null;
  $("worklist-view").classList.add("hidden");$("patient-view").classList.remove("hidden");
  $("patient-title").textContent=selectedPatient.patient_name||"Hasta";
  $("patient-meta").textContent=`${selectedPatient.protocol_no||selectedPatient.visit_id} · ${selectedPatient.department||selectedPatient.task||"COMED"}`;
  renderRecords();
  const records=visibleRecords();if(records.length)await selectRecord(records[0]);else updateSelection();
  window.scrollTo({top:0,behavior:"smooth"});
}
async function selectRecord(summary){
  selectedRecord=summary;renderRecords();updateSelection();
  try{const full=await json(`/doctor/api/records/${summary.id}`);selectedRecord={...summary,...full};activeTransfer=full.comed_transfer||null;$("transfer-state").textContent=activeTransfer?statusText(activeTransfer.status):"Aktarıma hazır";renderRecords();updateSelection();if(activeTransfer&&["queued","filling"].includes(activeTransfer.status))await pollTransfer(activeTransfer.id)}catch(e){toast(e.message,true)}
}
function updateSelection(){
  $("transfer").disabled=!(selectedPatient&&selectedRecord)||["queued","filling","ready_for_review","completed"].includes(activeTransfer?.status);
  renderReport();
}

/* Yonetici panelindeki ayni rapor katmani; sekmeler, ses ve PDF. */
function renderReport(){
  const body=$("report-body");
  const badge=$("report-record-id");
  const wrap=$("audio-wrap");
  const audio=$("record-audio");
  if(!selectedRecord||!selectedRecord.doktor){
    badge.textContent="—";
    wrap.classList.add("hidden");
    audio.removeAttribute("src");
    body.innerHTML='<div class="empty">Soldaki listeden bir rapor seçin.</div>';
    document.querySelectorAll("[data-pdf]").forEach(b=>b.disabled=true);
    return;
  }
  badge.textContent=`#${selectedRecord.id}`;
  document.querySelectorAll("[data-pdf]").forEach(b=>b.disabled=false);
  // Ses yalnizca kayitta varsa gosterilir; her secimde yeniden baglanir.
  const wanted=`/doctor/audio/${selectedRecord.id}`;
  if(selectedRecord.ses_var){
    wrap.classList.remove("hidden");
    if(!audio.src.endsWith(wanted)){audio.src=wanted;prepareAudioTimeline(audio)}
  }else{
    wrap.classList.add("hidden");
    audio.removeAttribute("src");
  }
  try{
    body.innerHTML=bodyHTML(selectedRecord,activeTab);
  }catch(error){
    body.innerHTML=`<div class="empty">Rapor görüntülenemedi: ${esc(error.message)}</div>`;
  }
}

document.addEventListener("click",(event)=>{
  const tab=event.target.closest("#report-tabs [data-tab]");
  if(tab){
    activeTab=tab.dataset.tab;
    document.querySelectorAll("#report-tabs [data-tab]").forEach(b=>b.classList.toggle("active",b===tab));
    renderReport();
    return;
  }
  const pdf=event.target.closest("[data-pdf]");
  if(pdf&&selectedRecord)indirDoktorPdf(pdf);
});

async function indirDoktorPdf(btn){
  const rec=btn.dataset.pdf,id=selectedRecord.id,orig=btn.innerHTML;
  btn.disabled=true;btn.innerHTML='<i class="bi bi-hourglass-split"></i> Hazırlanıyor…';
  try{
    const res=await fetch(`/doctor/pdf/${id}/${rec}`);
    if(res.status===401)throw new Error("Oturum sona erdi. Tekrar giriş yapın.");
    if(!res.ok){let m="PDF hatası";try{m=(await res.json()).error||m}catch(_){}throw new Error(m)}
    const blob=await res.blob();
    if(!blob.size||!String(blob.type).startsWith("application/pdf"))throw new Error("Sunucu geçerli bir PDF döndürmedi.");
    const url=URL.createObjectURL(blob),a=document.createElement("a");
    a.href=url;a.download=({hasta:"hasta_ozeti",doktor:"epikriz",yonetim:"yonetim_raporu"}[rec]||"rapor")+`_${id}.pdf`;
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){toast("PDF indirilemedi: "+e.message,true)}
  finally{btn.disabled=false;btn.innerHTML=orig}
}
async function load({silent=false}={}){
  if(loading)return;loading=true;
  try{
    const next=await json("/doctor/api/overview");
    const priorPatient=patientKey(selectedPatient),priorRecord=selectedRecord?.id;
    overview=next;
    if(priorPatient)selectedPatient=overview.worklist.find(p=>patientKey(p)===priorPatient)||selectedPatient;
    if(priorRecord){const fresh=overview.records.find(r=>r.id===priorRecord);if(fresh)selectedRecord={...selectedRecord,...fresh}}
    render();
    if(selectedPatient&&!selectedRecord){const records=visibleRecords();if(records.length)await selectRecord(records[0])}
  }catch(e){if(!silent)toast(e.message,true)}finally{loading=false}
}
function statusText(status){return {queued:"Aktarım sırada",filling:"COMED alanları dolduruluyor",ready_for_review:"Aktarım bitti · Genel doktor kontrolü gerekli",completed:"COMED kaydı tamamlandı",failed:"Aktarım başarısız"}[status]||"Hazır"}
function openComedWithBridge(url,transferId){return new Promise((resolve)=>{const requestId=`${Date.now()}-${Math.random().toString(16).slice(2)}`;let settled=false;const finish=(value)=>{if(settled)return;settled=true;clearTimeout(timer);window.removeEventListener("message",onMessage);resolve(value)};const onMessage=(event)=>{if(event.source!==window||event.origin!==location.origin||event.data?.source!=="klinot-doctor-comed-open-result-v1"||event.data?.request_id!==requestId)return;finish(event.data)};const timer=setTimeout(()=>finish({ok:false,error:"Klinot COMED eklentisi yanıt vermedi"}),1800);window.addEventListener("message",onMessage);window.postMessage({source:"klinot-doctor-comed-open-v1",request_id:requestId,url,transfer_id:transferId},location.origin)})}
async function pollTransfer(id){
  clearInterval(transferTimer);
  const tick=async()=>{try{activeTransfer=await json(`/doctor/api/comed/transfers/${id}`);$("transfer-state").textContent=statusText(activeTransfer.status);updateSelection();if(["ready_for_review","completed","failed"].includes(activeTransfer.status))clearInterval(transferTimer)}catch(e){clearInterval(transferTimer)}};
  await tick();transferTimer=setInterval(tick,3000);
}
$("refresh").onclick=()=>load();
$("back-to-worklist").onclick=()=>{$("patient-view").classList.add("hidden");$("worklist-view").classList.remove("hidden");selectedPatient=null;selectedRecord=null;activeTransfer=null;clearInterval(transferTimer);render();window.scrollTo({top:0,behavior:"smooth"})};
$("transfer").onclick=async()=>{if(!selectedPatient||!selectedRecord)return;$("transfer").disabled=true;$("transfer-state").textContent="Sıraya alınıyor";try{activeTransfer=await json("/doctor/api/comed/transfers",{method:"POST",body:JSON.stringify({record_id:selectedRecord.id,patient:selectedPatient})});$("transfer-state").textContent="COMED sekmesi hazırlanıyor";const opened=await openComedWithBridge(selectedPatient.clinical_card_url,activeTransfer.id);if(opened.ok){toast(opened.reused?"Açık COMED sekmesi kullanıldı; giriş gerekirse aktarım girişten sonra otomatik devam edecek.":"COMED kartı açıldı; giriş gerekirse aktarım otomatik devam edecek.")}else{const fallback=window.open(selectedPatient.clinical_card_url,"_blank");toast(fallback?"Eklenti yanıt vermedi; COMED kartı yeni sekmede açıldı.":"COMED eklentisi yanıt vermedi; kartı elle açın.",true)}$("transfer-state").textContent="COMED alanları dolduruluyor";await pollTransfer(activeTransfer.id)}catch(e){$("transfer-state").textContent="Hata";toast(e.message,true);updateSelection()}};
document.addEventListener("visibilitychange",()=>{if(!document.hidden)load({silent:true})});
refreshTimer=setInterval(()=>load({silent:true}),5000);
load();
