let overview={records:[],worklist:[]},selectedPatient=null,selectedRecord=null,activeTransfer=null;
let refreshTimer=null,transferTimer=null,loading=false;
const $=(id)=>document.getElementById(id);
function toast(message,error=false){const el=$("toast");el.textContent=message;el.className=error?"show error":"show";setTimeout(()=>el.className="",4500)}
function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
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
  $("records").innerHTML=records.length?records.map((r,i)=>`<button class="item ${selectedRecord?.id===r.id?'selected':''}" data-record="${i}"><strong>#${r.id} · ${esc(r.ozet||"Görüşme")}</strong><span>${esc(r.olusturma)}${r.ses_var?' · Ses kaydı var':''}</span></button>`).join(""):'<div class="empty">Bu doktora ait görüşme raporu henüz yok.</div>';
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
  const ep=selectedRecord?.doktor?.epikriz||selectedRecord?.doktor||{};
  $("report-preview").textContent=selectedRecord?(ep.oyku||ep.sikayet||ep.onTani||selectedRecord.ozet||"Epikriz hazır"):'Bu hasta için önce bir görüşme raporu seçin.';
  $("transfer").disabled=!(selectedPatient&&selectedRecord)||["queued","filling","ready_for_review","completed"].includes(activeTransfer?.status);
  const pdf=$("pdf-link");if(selectedRecord){pdf.href=`/doctor/pdf/${selectedRecord.id}`;pdf.classList.remove("disabled")}else{pdf.href="#";pdf.classList.add("disabled")}
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
async function pollTransfer(id){
  clearInterval(transferTimer);
  const tick=async()=>{try{activeTransfer=await json(`/doctor/api/comed/transfers/${id}`);$("transfer-state").textContent=statusText(activeTransfer.status);updateSelection();if(["ready_for_review","completed","failed"].includes(activeTransfer.status))clearInterval(transferTimer)}catch(e){clearInterval(transferTimer)}};
  await tick();transferTimer=setInterval(tick,3000);
}
$("refresh").onclick=()=>load();
$("back-to-worklist").onclick=()=>{$("patient-view").classList.add("hidden");$("worklist-view").classList.remove("hidden");selectedPatient=null;selectedRecord=null;activeTransfer=null;clearInterval(transferTimer);render();window.scrollTo({top:0,behavior:"smooth"})};
$("transfer").onclick=async()=>{if(!selectedPatient||!selectedRecord)return;const opened=window.open(selectedPatient.clinical_card_url,"_blank");$("transfer").disabled=true;$("transfer-state").textContent="Sıraya alınıyor";try{activeTransfer=await json("/doctor/api/comed/transfers",{method:"POST",body:JSON.stringify({record_id:selectedRecord.id,patient:selectedPatient})});$("transfer-state").textContent="COMED alanları dolduruluyor";toast("Aktarım eklentiye gönderildi; ilerleme otomatik izleniyor.");await pollTransfer(activeTransfer.id);if(!opened)toast("Tarayıcı yeni sekmeyi engelledi; COMED kartını açın.",true)}catch(e){if(opened)opened.close();$("transfer-state").textContent="Hata";toast(e.message,true);updateSelection()}};
document.addEventListener("visibilitychange",()=>{if(!document.hidden)load({silent:true})});
refreshTimer=setInterval(()=>load({silent:true}),5000);
load();
