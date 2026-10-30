const $ = (id) => document.getElementById(id);
let competitions = [], tasks = [], notes = [];
const pages = {dashboard:"Dashboard",competitions:"Competitions",tasks:"Tasks",notes:"Notes & Links"};
const api = async (path, options={}) => {
  const res = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options});
  let data = {};
  try { data = await res.json(); } catch {}
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
};
const esc = (s="") => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = (s) => { if(!s) return "Not set"; const d=new Date(s); return isNaN(d) ? s : d.toLocaleString([], {month:"short",day:"numeric",year:"numeric",hour: s.includes("T") ? "2-digit" : undefined, minute: s.includes("T") ? "2-digit" : undefined}); };
const shortDate = (s) => { if(!s) return null; const d=new Date(s); return isNaN(d)?null:d; };
const linksMarkup = (raw="") => String(raw).split(/\n+/).map(line => {
  const match = line.match(/https?:\/\/[^\s<>]+/i);
  if (!match) return esc(line);
  const url = match[0].replace(/[),.;]+$/, "");
  const label = line.slice(0, match.index).replace(/[：:]\s*$/, "").trim() || url;
  return `${esc(label)}: <a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open link ↗</a>`;
}).join("<br>");
const active = c => !["Completed","Cancelled","Archived"].includes(c.status);
const deadline = c => {
  const vals = [
    ["Submission",c.submission_deadline],["Registration",c.registration_deadline],["Event starts",c.event_start]
  ].map(([label,value])=>({label,value,date:shortDate(value)})).filter(x=>x.date && active(c)).sort((a,b)=>a.date-b.date);
  return vals[0] || null;
};
const daysLeft = d => Math.ceil((d.getTime()-Date.now())/86400000);
const countdown = d => {const n=daysLeft(d); if(n<0)return `${Math.abs(n)}d overdue`; if(n===0)return "Today"; if(n===1)return "Tomorrow"; return `${n} days left`;};
function showToast(msg){const t=$("toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),3000);}
function showPage(page){document.querySelectorAll(".page").forEach(x=>x.classList.remove("active"));$("page-"+page).classList.add("active");document.querySelectorAll(".nav-btn").forEach(x=>x.classList.toggle("active",x.dataset.page===page));$("pageTitle").textContent=pages[page];}
document.querySelectorAll(".nav-btn").forEach(b=>b.addEventListener("click",()=>showPage(b.dataset.page)));
document.querySelectorAll("[data-go]").forEach(b=>b.addEventListener("click",()=>showPage(b.dataset.go)));
$("todayLabel").textContent=new Date().toLocaleDateString([], {weekday:"long",month:"long",day:"numeric"}).toUpperCase();
function empty(title,sub){return `<div class="empty-state"><b>${title}</b>${sub}</div>`;}
function dateBox(d){if(!d)return `<div class="date-box"><b>—</b><small>date</small></div>`;return `<div class="date-box"><b>${d.getDate()}</b><small>${d.toLocaleDateString([],{month:"short"})}</small></div>`;}
function statusClass(d){if(!d)return "";const n=daysLeft(d);return n<0||n<=1?"urgent":n<=3?"soon":"good";}
function renderDashboard(){
  const live=competitions.filter(active), completed=competitions.filter(c=>c.status==="Completed");
  const upcoming=live.map(c=>({c,d:deadline(c)})).filter(x=>x.d).sort((a,b)=>a.d.date-b.d.date);
  $("statActive").textContent=live.length;
  $("statUrgent").textContent=upcoming.filter(x=>daysLeft(x.d.date)>=0&&daysLeft(x.d.date)<=7).length;
  $("statTasks").textContent=tasks.filter(t=>!t.completed).length;
  $("statCompleted").textContent=completed.length;
  $("upcomingList").innerHTML=upcoming.length?upcoming.slice(0,6).map(({c,d})=>`<div class="item-row">${dateBox(d.date)}<div class="item-main"><strong>${esc(c.name)}</strong><small>${esc(d.label)} · ${esc(countdown(d.date))}</small></div><span class="pill ${statusClass(d.date)}">${daysLeft(d.date)<0?"Overdue":daysLeft(d.date)<=3?"Soon":"Upcoming"}</span></div>`).join(""):empty("No deadlines yet","Add a competition to start your timeline.");
  const todo=tasks.filter(t=>!t.completed).slice(0,5);
  $("focusList").innerHTML=todo.length?todo.map(t=>`<div class="item-row"><input class="task-check" type="checkbox" onchange="toggleTask(${t.id})"><div class="item-main"><strong>${esc(t.title)}</strong><small>${esc(t.competition_name||"Personal task")}${t.due_at?" · Due "+esc(fmt(t.due_at)):""}</small></div></div>`).join(""):empty("Nothing on your focus list","Add a task when you have a next step.");
}
function renderCompetitions(){
  const query=$("competitionSearch").value.toLowerCase(), filter=$("competitionFilter").value;
  let list=competitions.filter(c=>(c.name+" "+c.organizer+" "+c.theme).toLowerCase().includes(query));
  list.sort((a,b)=>{const da=deadline(a)?.date?.getTime() ?? Number.MAX_SAFE_INTEGER;const db=deadline(b)?.date?.getTime() ?? Number.MAX_SAFE_INTEGER;return da-db;});
  if(filter==="active")list=list.filter(active);if(filter==="completed")list=list.filter(c=>c.status==="Completed");
  $("competitionList").innerHTML=list.length?list.map(c=>{
    const d=deadline(c), n=d?daysLeft(d.date):null;
    const state=c.status==="Completed"?"good":d?statusClass(d.date):"";
    const dueLabel=d?`${esc(d.label)} · ${esc(fmt(d.value))}`:"No deadline added";
    const dueCountdown=d&&active(c)?countdown(d.date):"";
    const linkLines=c.important_links?linksMarkup(c.important_links):"";
    return `<article class="competition-card">
      <div class="card-top"><div class="card-title-wrap"><h3>${esc(c.name)}</h3><div class="card-organizer">${esc(c.organizer||"Organizer not specified")}</div></div><span class="pill ${state}">${esc(c.status)}</span></div>
      ${c.theme?`<p class="card-theme">${esc(c.theme)}</p>`:""}
      <div class="next-deadline ${n!==null&&n<=3&&n>=0&&active(c)?"deadline-soon":n!==null&&n<0&&active(c)?"deadline-overdue":""}"><span class="deadline-icon">◷</span><div class="next-deadline-copy"><small>Next important date</small><strong>${dueLabel}</strong></div>${dueCountdown?`<span class="countdown">${dueCountdown}</span>`:""}</div>
      ${c.deliverables?`<div class="quick-detail"><span>To submit</span><p>${esc(c.deliverables)}</p></div>`:""}
      ${(c.eligibility||c.prizes||c.important_links||c.notes||c.registration_deadline||c.event_start||c.event_end)?`<details class="more-details"><summary>More details <span>＋</span></summary><div class="details-content">
        ${c.eligibility?`<div class="detail-item"><strong>Eligibility</strong><p>${esc(c.eligibility)}</p></div>`:""}
        ${c.prizes?`<div class="detail-item"><strong>Prizes & benefits</strong><p>${esc(c.prizes)}</p></div>`:""}
        ${c.registration_deadline?`<div class="detail-item"><strong>Registration deadline</strong><p>${esc(fmt(c.registration_deadline))}</p></div>`:""}
        ${c.event_start?`<div class="detail-item"><strong>Event starts</strong><p>${esc(fmt(c.event_start))}</p></div>`:""}
        ${c.event_end?`<div class="detail-item"><strong>Event ends</strong><p>${esc(fmt(c.event_end))}</p></div>`:""}
        ${c.notes?`<div class="detail-item"><strong>Notes</strong><p>${esc(c.notes)}</p></div>`:""}
        ${linkLines?`<div class="detail-item"><strong>Important links</strong><div class="important-links">${linkLines}</div></div>`:""}
      </div></details>`:""}
      <div class="card-footer">${c.source_url?`<a class="small-btn link-btn" href="${esc(c.source_url)}" target="_blank" rel="noopener noreferrer">Official page ↗</a>`:""}<button class="small-btn" onclick="editCompetition(${c.id})">Edit</button>${c.status!=="Completed"?`<button class="small-btn complete-btn" onclick="setCompetitionStatus(${c.id},'Completed')">✓ Complete</button>`:`<button class="small-btn" onclick="setCompetitionStatus(${c.id},'Registered')">Reopen</button>`}<button class="small-btn danger" onclick="removeCompetition(${c.id})">Delete</button></div>
    </article>`;
  }).join(""):empty("No competitions found","Add one manually or use AI import.");
}
function renderTasks(){
  $("taskList").innerHTML=tasks.length?tasks.map(t=>`<div class="task-row ${t.completed?"done":""}"><input class="task-check" type="checkbox" ${t.completed?"checked":""} onchange="toggleTask(${t.id})"><div class="task-content"><div class="task-title">${esc(t.title)}</div><div class="task-details">${esc(t.details||"")}${t.competition_name?" · "+esc(t.competition_name):""}${t.link?" · <a href='"+esc(t.link)+"' target='_blank' rel='noopener'>Open link ↗</a>":""}</div></div><div class="task-due">${t.due_at?esc(fmt(t.due_at)):"No due date"}</div><button class="small-btn danger" onclick="removeTask(${t.id})">Delete</button></div>`).join(""):empty("No tasks yet","Add a next action so it doesn't get lost.");
}
function renderNotes(){
  $("noteList").innerHTML=notes.length?notes.map(n=>`<article class="note-card"><div class="card-top"><h3>${esc(n.title)}</h3><button class="small-btn danger" onclick="removeNote(${n.id})">Delete</button></div><div class="note-content">${esc(n.content||"No extra details.")}</div>${n.link?`<a class="note-link" href="${esc(n.link)}" target="_blank" rel="noopener">Open saved link ↗</a>`:""}${n.remind_at?`<div class="note-meta">◷ Remind at ${esc(fmt(n.remind_at))}${n.reminded?" · reminder sent":""}</div>`:""}</article>`).join(""):empty("Your notes live here","Save a link, copied message, or reminder.");
}
function renderAll(){renderDashboard();renderCompetitions();renderTasks();renderNotes();fillCompetitionSelect();}
async function refresh(){try{[competitions,tasks,notes]=await Promise.all([api("/api/competitions"),api("/api/tasks"),api("/api/notes")]);renderAll();}catch(e){showToast(e.message);}}
function openDialog(id){$(id).showModal();}
function closeDialogs(){document.querySelectorAll("dialog").forEach(d=>d.close());}
document.querySelectorAll(".close-dialog").forEach(b=>b.addEventListener("click",closeDialogs));
$("quickAddBtn").onclick=$("addCompetitionBtn").onclick=()=>openCompetition();
function clearCompetitionForm(){ $("competitionForm").reset();$("competitionId").value="";$("competitionModalTitle").textContent="Add competition";$("cStatus").value="Registered"; }
function val(id){return $(id).value.trim();}
function openCompetition(c=null){
  clearCompetitionForm();
  if(c){$("competitionId").value=c.id;$("competitionModalTitle").textContent="Edit competition";$("cName").value=c.name||"";$("cOrganizer").value=c.organizer||"";$("cTheme").value=c.theme||"";$("cEligibility").value=c.eligibility||"";$("cPrizes").value=c.prizes||"";$("cImportantLinks").value=c.important_links||"";$("cUrl").value=c.source_url||"";$("cReg").value=(c.registration_deadline||"").slice(0,16);$("cSubmit").value=(c.submission_deadline||"").slice(0,16);$("cStart").value=(c.event_start||"").slice(0,16);$("cEnd").value=(c.event_end||"").slice(0,16);$("cDeliverables").value=c.deliverables||"";$("cNotes").value=c.notes||"";$("cStatus").value=c.status||"Registered";}
  openDialog("competitionDialog");
}
window.editCompetition=id=>openCompetition(competitions.find(c=>c.id===id));
$("competitionForm").addEventListener("submit",async e=>{
  e.preventDefault();
  const id=val("competitionId");
  const payload={name:val("cName"),organizer:val("cOrganizer"),theme:val("cTheme"),eligibility:val("cEligibility"),prizes:val("cPrizes"),important_links:val("cImportantLinks"),source_url:val("cUrl"),registration_deadline:val("cReg"),submission_deadline:val("cSubmit"),event_start:val("cStart"),event_end:val("cEnd"),deliverables:val("cDeliverables"),notes:val("cNotes"),status:val("cStatus"),timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||"Asia/Kolkata"};
  try{await api(id?`/api/competitions/${id}`:"/api/competitions",{method:id?"PUT":"POST",body:JSON.stringify(payload)});closeDialogs();await refresh();showToast(id?"Competition updated":"Competition saved");}catch(err){showToast(err.message);}
});
window.setCompetitionStatus=async(id,status)=>{const c=competitions.find(x=>x.id===id);if(!c)return;try{await api(`/api/competitions/${id}`,{method:"PUT",body:JSON.stringify({...c,status})});await refresh();showToast(`Status changed to ${status}`);}catch(e){showToast(e.message);}};
window.removeCompetition=async id=>{if(!confirm("Delete this competition? Related tasks will remain but become unlinked."))return;try{await api(`/api/competitions/${id}`,{method:"DELETE"});await refresh();showToast("Competition deleted");}catch(e){showToast(e.message);}};
$("competitionSearch").addEventListener("input",renderCompetitions);$("competitionFilter").addEventListener("change",renderCompetitions);
$("importBtn").onclick=()=>{$("importForm").reset();$("importStatus").textContent="";openDialog("importDialog");};
$("importForm").addEventListener("submit",async e=>{
  e.preventDefault();
  const btn=$("runImportBtn"),status=$("importStatus");
  btn.disabled=true;btn.textContent="Reading page…";
  status.textContent="HackTrack is reading the page, extracting details, saving the competition, and creating suggested tasks. This may take up to a minute.";
  try{
    const data=await api("/api/import",{method:"POST",body:JSON.stringify({url:val("importUrl"),text:val("importText")})});
    closeDialogs();
    await refresh();
    showPage("competitions");
    showToast(data.message || "Competition imported and saved automatically");
  } catch(err) {
    status.textContent=err.message;
    showToast(err.message);
  } finally {
    btn.disabled=false;btn.textContent="Auto import & save";
  }
});
function fillCompetitionSelect(){const s=$("tCompetition"),old=s.value;s.innerHTML='<option value="">None</option>'+competitions.filter(active).map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join("");if(old)s.value=old;}
$("addTaskBtn").onclick=()=>{$("taskForm").reset();fillCompetitionSelect();openDialog("taskDialog");};
$("taskForm").addEventListener("submit",async e=>{e.preventDefault();try{await api("/api/tasks",{method:"POST",body:JSON.stringify({title:val("tTitle"),details:val("tDetails"),link:val("tLink"),due_at:val("tDue"),competition_id:val("tCompetition")?Number(val("tCompetition")):null})});closeDialogs();await refresh();showToast("Task saved");}catch(err){showToast(err.message);}});
window.toggleTask=async id=>{try{await api(`/api/tasks/${id}`,{method:"PATCH"});await refresh();}catch(e){showToast(e.message);}};
window.removeTask=async id=>{if(!confirm("Delete this task?"))return;try{await api(`/api/tasks/${id}`,{method:"DELETE"});await refresh();showToast("Task deleted");}catch(e){showToast(e.message);}};
$("addNoteBtn").onclick=()=>{$("noteForm").reset();openDialog("noteDialog");};
$("noteForm").addEventListener("submit",async e=>{e.preventDefault();const message=val("nContent").trim();if(!message){showToast("Paste the message first");return;}const btn=$("analyseMessageBtn");btn.disabled=true;btn.textContent="Analysing…";try{const result=await api("/api/notes/ai-save",{method:"POST",body:JSON.stringify({title:val("nTitle")||"College message",message,link:val("nLink")})});closeDialogs();await refresh();showToast(result.message||"Message analysed and saved");}catch(err){showToast(err.message);}finally{btn.disabled=false;btn.textContent="Analyse & save tasks";}});
window.removeNote=async id=>{if(!confirm("Delete this note?"))return;try{await api(`/api/notes/${id}`,{method:"DELETE"});await refresh();showToast("Note deleted");}catch(e){showToast(e.message);}};
async function loadNotificationStatus(){try{const data=await api("/api/notifications/status");const provider=(data.mode||"ntfy").toUpperCase();$("notificationSettingsStatus").textContent=`Provider: ${provider} · ${data.configured?"configuration detected":"configuration incomplete — check your .env file"} · local scheduler ${data.scheduler_enabled?"enabled":"disabled"}.`; }catch(e){$("notificationSettingsStatus").textContent=e.message;}}
$("testNotificationBtn").onclick=async()=>{const button=$("testNotificationBtn");button.disabled=true;button.textContent="Sending…";try{const data=await api("/api/notifications/test",{method:"POST"});$("notificationSettingsStatus").textContent=`Test request accepted by ${data.mode.toUpperCase()}: ${data.message}.`;showToast("Test notification request sent");}catch(e){$("notificationSettingsStatus").textContent=`Test failed: ${e.message}`;showToast(e.message);}finally{button.disabled=false;button.textContent="Send test notification";}};
loadNotificationStatus();
$("exportBtn").onclick=async()=>{try{const data=await api("/api/export");const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`hacktrack-backup-${new Date().toISOString().slice(0,10)}.json`;a.click();URL.revokeObjectURL(url);showToast("Backup exported");}catch(e){showToast(e.message);}};
refresh();
