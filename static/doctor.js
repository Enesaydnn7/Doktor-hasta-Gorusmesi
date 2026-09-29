let overview={records:[],worklist:[]},selectedPatient=null,selectedRecord=null;
const $=(id)=>document.getElementById(id);
function toast(message,error=false){const el=$("toast");el.textContent=message;el.className=error?"show error":"show";setTimeout(()=>el.className="",4500)}
function esc(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function json(url,options={}){const response=await fetch(url,{...options,headers:{Accept:"application/json",...(options.body?{"Content-Type":"application/json"}:{}),...(options.headers||{})}});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||data.error||`HTTP ${response.status}`);return data}
function render(){
  $("stats").innerHTML=`<div class="stat"><small>GÖRÜŞME KAYDI</small><strong>${overview.stats?.kayit||0}</strong></div><div class="stat"><small>COMED HASTASI</small><strong>${overview.worklist.length}</strong></div><div class="stat"><small>TOPLAM TOKEN</small><strong>${Number(overview.stats?.token||0).toLocaleString("tr-TR")}</strong></div>`;
  $("worklist-count").textContent=overview.worklist.length;$("record-count").textContent=overview.records.length;
  $("worklist").innerHTML=overview.worklist.length?overview.worklist.map((p,i)=>`<div class="item ${selectedPatient?.visit_id===p.visit_id?'selected':''}" data-patient="${i}"><strong>${esc(p.patient_name)}</strong><span>${esc(p.protocol_no||p.visit_id)} · ${esc(p.department||p.task||"COMED")}</span></div>`).join(""):'<div class="empty">Bu doktor için eşitlenmiş COMED hastası yok. Eklentiyi aynı hesapla bağlayıp COMED iş listesini yenileyin.</div>';
  $("records").innerHTML=overview.records.length?overview.records.map((r,i)=>`<div class="item ${selectedRecord?.id===r.id?'selected':''}" data-record="${i}"><strong>#${r.id} · ${esc(r.ozet||"Görüşme")}</strong><span>${esc(r.olusturma)}${r.ses_var?' · Ses kaydı var':''}</span></div>`).join(""):'<div class="empty">Bu doktora ait görüşme kaydı henüz yok.</div>';
  document.querySelectorAll("[data-patient]").forEach(el=>el.onclick=()=>{selectedPatient=overview.worklist[+el.dataset.patient];updateSelection();render()});
  document.querySelectorAll("[data-record]").forEach(el=>el.onclick=async()=>{selectedRecord=overview.records[+el.dataset.record];const full=await json(`/doctor/api/records/${selectedRecord.id}`);selectedRecord={...selectedRecord,...full};updateSelection();render()});
}
function updateSelection(){
  $("selected-patient").textContent=selectedPatient?.patient_name||"Seçilmedi";$("selected-record").textContent=selectedRecord?`#${selectedRecord.id} · ${selectedRecord.ozet||"Görüşme"}`:"Seçilmedi";
  const ep=selectedRecord?.doktor?.epikriz||selectedRecord?.doktor||{};$("report-preview").textContent=selectedRecord?(ep.oyku||ep.sikayet||ep.onTani||selectedRecord.ozet||"Epikriz hazır"):'Rapor seçildiğinde epikriz özeti burada görünür.';
  $("transfer").disabled=!(selectedPatient&&selectedRecord);const pdf=$("pdf-link");if(selectedRecord){pdf.href=`/doctor/pdf/${selectedRecord.id}`;pdf.classList.remove("disabled")}else{pdf.href="#";pdf.classList.add("disabled")}
}
async function load(){try{overview=await json("/doctor/api/overview");render();updateSelection()}catch(e){toast(e.message,true)}}
$("refresh").onclick=load;
$("transfer").onclick=async()=>{if(!selectedPatient||!selectedRecord)return;const opened=window.open(selectedPatient.clinical_card_url,"_blank");$("transfer").disabled=true;$("transfer-state").textContent="Sıraya alınıyor";try{const transfer=await json("/doctor/api/comed/transfers",{method:"POST",body:JSON.stringify({record_id:selectedRecord.id,patient:selectedPatient})});$("transfer-state").textContent="COMED dolduruluyor";toast(`Aktarım #${transfer.id} eklentiye gönderildi.`);if(!opened)toast("Tarayıcı yeni sekmeyi engelledi; hasta kartını iş listesinden açın.",true)}catch(e){if(opened)opened.close();$("transfer-state").textContent="Hata";toast(e.message,true)}finally{$("transfer").disabled=false}};
load();
