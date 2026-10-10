// Import avatar components - using TalkingHead.js version
import { Avatar3D } from './components/Avatar3D-TalkingHead.js';
import { ttsService } from './components/TTSService.js';

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths = {
 library:'M3 5h7v14H3z M14 5h7v14h-7z M6 8h1 M17 8h1',
 studio:'M4 20h16 M7 16l-3 1 1-3L16 3l4 4z M13 6l4 4',
 history:'M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v5l3 2',
 file:'M14 2H5v20h14V7z M14 2v6h5 M8 12h8 M8 16h6',
 arrow:'M5 12h14 M13 6l6 6-6 6',back:'M19 12H5 M11 6l-6 6 6 6',
 plus:'M12 5v14 M5 12h14',search:'M21 21l-6-6 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0',
 check:'M5 12l4 4L19 6',shield:'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z M8 12l3 3 5-6',
 send:'M22 2L9 15 M22 2l-7 20-6-7-7-6z',close:'M6 6l12 12 M18 6L6 18',
 down:'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',info:'M12 11v6 M12 7v1 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
 dot:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 8v4l3 2',
 sound:'M11 5L6 9H3v6h3l5 4z M15 8a6 6 0 0 1 0 8 M18 5a10 10 0 0 1 0 14',
 eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0'
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.file}"/></svg>`;
const S = {role:'student', patients:[], encounters:[], rubric:null, route:'', filter:'all', query:'', editor:null, attachments:[], validation:null, dirty:false, encounter:null, chartTab:'findings', sending:false, speak:false, epoch:0, avatar:null, avatarEnabled:true};
const main = $('#main');
let toastTimer;
function toast(message,error=false){const el=$('#toast');el.textContent=message;el.className=error?'error':'';el.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.hidden=true,5000);}
async function api(path,method='GET',body){
 const res=await fetch('/api'+path,{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 const data=await res.json();if(!res.ok)throw new Error(data.error || `Request failed (${res.status})`);return data;
}
const badge=(text,type='')=>`<span class="badge ${type}">${esc(text)}</span>`;
const button=(label,action,id='',type='btn-primary',ic='')=>`<button type="button" class="btn ${type}" data-action="${action}" data-id="${esc(id)}">${ic?icon(ic):''}${esc(label)}</button>`;
const notice=(text,kind='')=>`<div class="notice ${kind}">${icon('info')}<div>${text}</div></div>`;
const date=(s)=>new Date(s).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
const initials=(s)=>s.split(' ').map(x=>x[0]).slice(0,2).join('');
function portrait(p,cls=''){return p.image?`<img class="${cls}" src="${esc(p.image)}" alt="Organizer-provided synthetic portrait of ${esc(p.name)}" loading="lazy">`:`<div class="placeholder-portrait ${cls}">${esc(initials(p.name || 'New Patient'))}</div>`;}

// Initialize avatar for current encounter
function initializeAvatar(){
  const container = $('#avatar-container');
  if(!container || !S.encounter || !S.avatarEnabled) return;

  // Clean up existing avatar
  if(S.avatar){
    S.avatar.destroy();
    S.avatar = null;
  }

  try{
    const p = S.encounter.patient;
    S.avatar = new Avatar3D(container, {
      name: p.name,
      gender: p.gender,
      patientId: p.id,
      imageUrl: p.image,
      enableLipSync: true,
      enableIdleAnimation: true
    });
  }catch(err){
    console.error('Avatar initialization error:', err);
    container.innerHTML = `<div class="avatar-error">Avatar unavailable. ${portrait(S.encounter.patient)}</div>`;
  }
}
function navigation(){
 const r=S.route.split('/')[0];const links=[['cases','library','Practice library'],...(S.role==='faculty'?[['studio','studio','Patient Studio']]:[]),['reviews','history','Encounter history'],['rubric','file','Assessment rubric'],...(S.role==='faculty'?[['resources','file','Source materials']]:[])];
 $('#navigation').innerHTML=links.map(([key,ic,label])=>`<a class="nav-link ${r===key || key==='reviews'&&r==='report'?'active':''}" href="#${key}" aria-label="${label}">${icon(ic)}<span>${label}</span>${r===key?'<i class="nav-dot"></i>':''}</a>`).join('');
 $('#role-switch').innerHTML=['student','faculty'].map(role=>`<button class="${S.role===role?'active':''}" data-action="role" data-id="${role}" aria-pressed="${S.role===role}" title="Switch local demo workspace">${role==='student'?'Student':'Faculty'}</button>`).join('');
 const labels={cases:'Practice library',studio:'Patient Studio',reviews:'Encounter history',report:'Encounter feedback',encounter:'Patient encounter',rubric:'Assessment rubric',resources:'Source materials'};
 $('#page-label').textContent=labels[r] || 'Workspace';
}
function heading(kicker,title,desc,action=''){return `<div class="page-heading"><div><div class="eyebrow">${esc(kicker)}</div><h1>${esc(title)}</h1><p>${esc(desc)}</p></div>${action}</div>`;}
async function route(){
 const target=location.hash.slice(1) || 'cases';
 if(S.dirty && target!==S.route && !confirm('Leave without saving your case edits?')){location.hash=S.route;return;}
 S.dirty=false;S.route=target;const epoch=++S.epoch;navigation();
 main.innerHTML='<div class="loading-state"><span class="spinner"></span>Loading workspace…</div>';
 try{
   const [page,id]=target.split('/');
   let view;
   if(page==='cases'||page==='studio'&&!id){S.patients=(await api('/patients')).patients;view=page==='cases'?casesView():studioView();}
   else if(page==='studio'&&id){
     if(S.role!=='faculty')throw new Error('Switch to the Faculty workspace to edit a patient.');
     if(id==='new'){S.editor=newProfile();S.attachments=[];S.validation=null;}
     else {const r=await api('/patients/'+encodeURIComponent(id));S.editor=r.profile;S.attachments=r.attachments;S.validation=r.validation;}
     view=editorView();
   }else if(page==='encounter'||page==='report'){
     S.encounter=await api('/encounters/'+encodeURIComponent(id));view=page==='report'?reportView():encounterView();
     // Initialize avatar after render
     if(page==='encounter'){
       setTimeout(()=>initializeAvatar(),100);
     }
   }else if(page==='reviews'){S.encounters=(await api('/encounters')).encounters;view=historyView();}
   else if(page==='rubric'){view=rubricView();}
   else if(page==='resources'){const r=await api('/resources');view=resourcesView(r.resources);}
   else {location.hash='cases';return;}
   if(epoch!==S.epoch)return;main.innerHTML=view;
   if(page==='encounter'){scrollChat();updateClock();}
 }catch(err){if(epoch===S.epoch)main.innerHTML=notice(esc(err.message),'error')+button('Back to library','navigate','cases','btn-primary','back');}
}
function casesView(){
 const available=S.patients.filter(p=>p.has_published_version).map(p=>p.published_card||p);const featured=available.find(p=>p.name.startsWith('Omar')) || available[0];
 return heading('LEARN THROUGH CONVERSATION','Every encounter is an opportunity.','Build confidence through thoughtful conversations, one patient at a time.')+
 `<section class="hero"><div class="hero-copy"><div class="eyebrow">YOUR NEXT CONVERSATION</div><h2>Listen closely.<br>Connect the whole story.</h2><p>Meet a virtual patient, explore their history, and reflect on your approach with evidence from the encounter.</p>${featured?button('Begin an encounter','start',featured.id,'btn-light','arrow'):button('Create a patient','navigate','studio/new','btn-light','plus')}</div><div class="hero-art"><div class="orbit"></div><div class="orbit second"></div>${featured?portrait(featured,'hero-portrait'):''}<span class="hero-star" aria-hidden="true">✳</span><div class="float-label"><span class="status-dot"></span> Sample-backed conversations · Your pace</div></div></section>
 <div class="section-heading"><h2>Meet your patients <span class="count-pill">${available.length}</span></h2><label class="search">${icon('search')}<input type="search" id="patient-search" placeholder="Search patients or cases…" value="${esc(S.query)}" aria-label="Search patients"></label></div>
 <div class="filter-row">${[['all','All patients'],['cardio','Cardiometabolic'],['communication','Communication & context']].map(([key,label])=>`<button class="chip ${S.filter===key?'active':''}" data-action="filter" data-id="${key}" aria-pressed="${S.filter===key}">${label}</button>`).join('')}</div>
 <div class="patient-grid" id="patient-grid">${patientCards()}</div>
 <div class="spacer-top">${notice('These are organizer-provided synthetic cases. Dialogue uses a deterministic sample adapter; unprovided clinical details remain unknown.')}</div>`;
}
function patientCards(){
 const list=S.patients.filter(p=>p.has_published_version).map(p=>p.published_card||p).filter(p=>(p.name+' '+p.summary).toLowerCase().includes(S.query.toLowerCase())).filter(p=>S.filter==='all'||(S.filter==='cardio'?/heart|lipid|hypertension|obesity/i.test(p.summary):!/heart|lipid|hypertension|obesity/i.test(p.summary)));
 return list.length?list.map(p=>`<article class="patient-card"><div class="portrait-wrap">${portrait(p)}<span class="portrait-tag">SYNTHETIC PATIENT</span></div><div class="card-body"><div class="patient-name-line"><h3>${esc(p.name)}</h3><span class="age">${p.age} years · ${esc(p.gender)}</span></div><p class="summary">${esc(p.summary)}</p><div class="card-bottom"><span>Guided interview practice</span><button class="start-link" data-action="start" data-id="${p.id}">Start encounter ${icon('arrow')}</button></div></div></article>`).join(''):'<div class="empty-state"><h3>No matching patients</h3><p>Try a different name or select All patients.</p></div>';
}
function studioView(){
 return heading('FACULTY WORKSPACE','Patient Studio','Shape the case. Set the learning goals. Publish when you’re ready.',button('Create patient','navigate','studio/new','btn-primary','plus'))+
 notice('Local demo roles are switchable for testing. Use synthetic content only; this is not a production login system.')+
 `<div class="panel"><div class="panel-header"><h2>Your case collection</h2>${badge(S.patients.length+' patients')}</div><div class="table-scroll"><table class="data-table"><thead><tr><th>PATIENT</th><th>CASE</th><th>STATUS</th><th>VERSION</th><th></th></tr></thead><tbody>${S.patients.map(p=>`<tr><td><div class="table-person">${portrait(p)}<div><strong>${esc(p.name)}</strong><div class="muted small">${p.age} years · ${esc(p.gender)}</div></div></div></td><td>${esc(p.summary)}</td><td>${badge(p.status==='published'?'Published':'Draft',p.status==='draft'?'warning':'')}</td><td class="muted">v${p.version}</td><td>${button('Edit case','navigate','studio/'+p.id,'btn-small','studio')}</td></tr>`).join('')}</tbody></table></div></div>`;
}
function newProfile(){return {name:'',age:30,gender:'Not specified',summary:'',background:'',persona:'Conversational and thoughtful',source_notes:'',version:0,status:'draft',facts:[{id:'f1',label:'Presenting case',record:'',patient_text:'',topic:'concern',keywords:['what brings','main concern','symptoms','medical history'],release:'initial',source:'Faculty-authored local sample'},{id:'f2',label:'Personal background',record:'',patient_text:'',topic:'background',keywords:['work','home','background','family','live'],release:'question',source:'Faculty-authored local sample'}],objectives:[{id:'o1',label:'Explore personal background',fact_ids:['f2'],suggestion:'Ask about the patient’s circumstances and clarify their response.'}],validation_notes:[]};}
const field=(label,name,value,type='text',hint='')=>`<div class="field"><label for="${name}">${esc(label)}</label>${type==='textarea'?`<textarea id="${name}" name="${name}">${esc(value)}</textarea>`:`<input id="${name}" name="${name}" type="${type}" value="${esc(value)}" ${type==='number'?'min="0" max="120"':''}>`}${hint?`<small>${esc(hint)}</small>`:''}</div>`;
function editorView(){const p=S.editor;
 return heading('FACULTY / CASE AUTHORING',p.id?p.name:'Create a new patient','Clinical facts stay under your control. Published encounters use a frozen case version.',button('Back to cases','navigate','studio','btn','back'))+
 `<div class="editor-layout"><form class="editor-main" id="case-form">
 <section class="panel"><div class="panel-header"><h2>Patient identity</h2>${badge(p.status==='published'?'Published v'+p.version:'Working draft',p.status==='draft'?'warning':'')}</div><div class="panel-content"><div class="form-grid">${field('Full name','name',p.name)}${field('Age','age',p.age,'number')}${field('Gender','gender',p.gender)}${field('Conversational style','persona',p.persona)}<div class="field full"><label for="summary">Case summary</label><textarea id="summary" name="summary">${esc(p.summary)}</textarea><small>Visible in the practice library. Avoid hidden learning answers.</small></div><div class="field full"><label for="background">Background</label><textarea id="background" name="background">${esc(p.background)}</textarea></div></div></div></section>
 <section class="panel"><div class="panel-header"><h2>Facts & progressive disclosure</h2>${button('Add fact','add-fact','','btn-small','plus')}</div><div class="panel-content" id="facts-editor">${p.facts.map(f=>factEditor(f)).join('')}</div></section>
 <section class="panel"><div class="panel-header"><h2>Learning checkpoints</h2>${button('Add checkpoint','add-objective','','btn-small','plus')}</div><div class="panel-content"><p class="source-description">App-authored checkpoints track elicited facts. The official seven-domain rubric remains a separate faculty assessment.</p>${p.objectives.map(o=>`<div class="objective-card" data-objective="${esc(o.id)}"><div class="fact-top"><strong>${esc(o.id)}</strong><button type="button" class="icon-button" data-action="remove-objective" data-id="${esc(o.id)}" aria-label="Remove checkpoint">${icon('close')}</button></div><div class="field"><label>Learning objective<input data-key="label" value="${esc(o.label)}"></label></div><div class="field"><label>Required fact IDs, separated by commas<input data-key="fact_ids" value="${esc(o.fact_ids.join(', '))}"></label></div><div class="field"><label>Next-attempt suggestion<textarea data-key="suggestion">${esc(o.suggestion)}</textarea></label></div></div>`).join('')}</div></section>
 <section class="panel"><div class="panel-header"><h2>Source notes & review flags</h2>${icon('file')}</div><div class="panel-content">${field('Original notes / provenance','source_notes',p.source_notes,'textarea','Faculty-only context. Facts must be entered explicitly above to enter the encounter.')}${field('Flags for faculty review — one per line','validation_notes',(p.validation_notes||[]).join('\n'),'textarea')}</div></section>
 </form><aside class="editor-aside"><section class="panel"><div class="panel-content"><div class="eyebrow">REVIEW & PUBLISH</div><h3 class="spacer-top">Ready for an encounter?</h3><p>Save your edits, check the structure, and confirm clinical review. Publishing never changes an encounter already in progress.</p><div id="validation-result">${validationView()}</div><label class="check-line"><input type="checkbox" id="approve-case"><span>I reviewed the clinical content, source limitations, disclosure rules, and learning checkpoints.</span></label>${button('Save draft','save-case','','btn','studio')}${button('Check structure','validate-case','','btn','shield')}${button('Approve & publish','publish-case','','btn-primary','check')}</div></section></aside></div>
 <section class="panel spacer-top"><div class="panel-header"><h2>Knowledge sources & clinical artifacts</h2>${badge(S.attachments.length+' files','neutral')}</div><div class="panel-content"><p class="source-description">Sources remain faculty-only. Artifacts are released by their rule. Uploads are stored locally; document text is not automatically extracted. Publish again to include new attachments in future encounters.</p><div class="attachment-list">${S.attachments.map(a=>`<div class="attachment-row">${icon('file')}<div><strong>${esc(a.name)}</strong><small>${a.kind==='source'?'Faculty knowledge source':a.release==='initial'?'Artifact · available at start':'Artifact · released on request'} · ${(a.size/1024).toFixed(0)} KB</small></div><a class="btn btn-small" href="/api/attachments/${a.id}">${icon('down')} Download</a></div>`).join('')}</div>${p.id?`<form id="upload-form" class="file-upload"><div class="form-grid"><div class="field"><label for="upload-file">Choose file — up to 5 MB</label><input id="upload-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,.md,.json" required></div><div class="field"><label for="upload-kind">File purpose</label><select id="upload-kind"><option value="artifact">Clinical artifact</option><option value="source">Faculty knowledge source</option></select></div><div class="field"><label for="upload-release">Release rule</label><select id="upload-release"><option value="question">On a relevant question</option><option value="initial">At encounter start</option></select></div><div class="field"><label for="upload-keywords">Trigger phrases, separated by commas</label><input id="upload-keywords" value="lab results, blood test, show records"></div></div><div class="button-row spacer-top"><button class="btn" type="submit">${icon('plus')}Attach file</button><span class="small muted">No uploads are sent to an external service.</span></div></form>`:notice('Save this new patient once to enable file attachments.')}</div></section>`;
}
function factEditor(f){return `<div class="fact-card" data-fact="${esc(f.id)}"><div class="fact-top"><strong>FACT ${esc(f.id)}</strong><button type="button" class="icon-button" data-action="remove-fact" data-id="${esc(f.id)}" aria-label="Remove fact">${icon('close')}</button></div><div class="fact-grid"><div class="field"><label>Record label<input data-key="label" value="${esc(f.label)}"></label></div><div class="field"><label>Release rule<select data-key="release">${[['initial','At encounter start'],['question','When asked'],['faculty_only','Faculty only']].map(([k,v])=>`<option value="${k}" ${f.release===k?'selected':''}>${v}</option>`).join('')}</select></label></div><div class="field"><label>Clinical record text<textarea data-key="record">${esc(f.record)}</textarea></label></div><div class="field"><label>Approved patient wording<textarea data-key="patient_text">${esc(f.patient_text)}</textarea></label></div><div class="field full"><label>Trigger words and phrases<input data-key="keywords" value="${esc((f.keywords||[]).join(', '))}"></label><small>Deterministic matching supports these phrases. Broader semantic understanding needs an LLM adapter.</small></div><div class="field full"><label>Source / provenance<input data-key="source" value="${esc(f.source)}"></label></div></div></div>`;}
function validationView(){const v=S.validation;if(!v)return '<p>Run structural checks before publishing.</p>';return `<ul class="validation-list">${v.errors.length?v.errors.map(x=>`<li>${esc(x)}</li>`).join(''):'<li>Required structure and references are valid.</li>'}${v.warnings.map(x=>`<li>${esc(x)}</li>`).join('')}<li>Clinical accuracy requires faculty review.</li></ul>`;}
function collectEditor(){const form=$('#case-form');if(!form)return S.editor;const p=structuredClone(S.editor);
 ['name','gender','summary','background','persona','source_notes'].forEach(k=>p[k]=form.elements.namedItem(k).value.trim());p.age=Number(form.elements.namedItem('age').value);p.validation_notes=form.elements.namedItem('validation_notes').value.split('\n').map(x=>x.trim()).filter(Boolean);
 p.facts=$$('[data-fact]',form).map(el=>{const original=p.facts.find(f=>f.id===el.dataset.fact)||{};const f={...original,id:el.dataset.fact};$$('[data-key]',el).forEach(i=>f[i.dataset.key]=i.dataset.key==='keywords'?i.value.split(',').map(x=>x.trim()).filter(Boolean):i.value.trim());return f;});
 if(!p.id){const a=p.facts.find(f=>f.id==='f1'),b=p.facts.find(f=>f.id==='f2');if(a){a.record ||=p.summary;a.patient_text ||=p.summary;}if(b){b.record ||=p.background;b.patient_text ||=p.background;}}
 p.objectives=$$('[data-objective]',form).map(el=>{const o={id:el.dataset.objective};$$('[data-key]',el).forEach(i=>o[i.dataset.key]=i.dataset.key==='fact_ids'?i.value.split(',').map(x=>x.trim()).filter(Boolean):i.value.trim());return o;});return p;
}
async function saveCase(publish=false){
 const p=collectEditor();if(publish&&!$('#approve-case').checked)throw new Error('Confirm faculty review before publishing.');
 const r=await api(p.id?'/patients/'+p.id:'/patients',p.id?'PUT':'POST',{profile:p});S.editor=r.profile;S.attachments=r.attachments;S.validation=r.validation;S.dirty=false;
 if(publish){const published=await api('/patients/'+S.editor.id+'/publish','POST',{approved:true});S.editor=published.profile;S.attachments=published.attachments;S.validation=published.validation;}
 const newRoute='studio/'+S.editor.id;S.route=newRoute;history.replaceState(null,'','#'+newRoute);navigation();main.innerHTML=editorView();toast(publish?'Patient published. Ready for a new encounter.':'Draft saved.');
}
function encounterView(){const e=S.encounter;const p=e.patient;
 return `<div class="encounter-top"><div class="encounter-heading"><a class="back-button" href="#cases" aria-label="Save and leave encounter">${icon('back')}</a><div><h1>Patient encounter</h1><p class="muted">Your conversation is saved automatically.</p></div></div><div class="button-row">${badge(e.status==='active'?'In progress':'Completed',e.status==='active'?'':'neutral')}${e.status==='active'?button('Finish encounter','finish',e.id,'btn-primary','check'):button('View feedback','navigate','report/'+e.id,'btn-primary','arrow')}<button class="btn btn-small" data-action="toggle-transcript" id="transcript-toggle">${icon('history')} View transcript</button></div></div>
 <div class="encounter-layout-3d"><section class="avatar-main-panel"><div class="avatar-display-area"><div id="avatar-container" style="width:100%;height:100%">${S.avatarEnabled?'<div class="avatar-loading-3d"><span class="spinner"></span><span>Initializing 3D avatar...</span></div>':portrait(p)}</div></div><div class="avatar-controls-bar"><div class="avatar-patient-info"><div><h3>${esc(p.name)}</h3><p>${p.age} years · ${esc(p.gender)} · Case v${p.version} · ${badge('Synthetic','neutral')}</p></div><span class="session-clock" id="session-clock" style="margin-left:auto;font-size:11px;color:var(--muted)"></span></div></div>${e.status==='active'?`<div style="padding:18px 24px;border-top:1px solid var(--line);background:#fff"><div class="starters" style="margin-bottom:12px"><button class="starter" data-action="starter" data-text="Hello, my name is Alex. I'm a student clinician. What brings you in today?">Open the conversation</button><button class="starter" data-action="starter" data-text="Could you tell me about your work and home life?">Explore context</button><button class="starter" data-action="starter" data-text="What questions or concerns do you have?">Ask about concerns</button></div><form class="avatar-input-section" id="chat-form"><textarea id="question" maxlength="4000" placeholder="Ask your patient a question…" aria-label="Your question" rows="2" required></textarea><button type="submit" class="avatar-send-btn" aria-label="Send question">${icon('send')} Send</button></form><div style="margin-top:10px;font-size:9px;color:var(--muted);display:flex;gap:12px;justify-content:space-between"><span>Enter to send · Shift + Enter for new line</span>${ttsService.isAvailable()?`<label class="avatar-toggle"><input type="checkbox" id="avatar-toggle" ${S.avatarEnabled?'checked':''}> 3D Avatar with voice</label>`:''}</div></div>`:`<div class="completed-composer">This encounter is complete. Your transcript is preserved.<br>${button('Review your encounter','navigate','report/'+e.id,'btn-primary','arrow')}</div>`}</section>
 <aside class="panel compact-chart-panel"><div class="panel-header"><div class="chart-title">${icon('file')}<div><h2>Medical record</h2><small>Updates as information becomes available</small></div></div>${icon('shield')}</div><div class="chart-tabs" role="tablist" aria-label="Medical record sections">${[['findings','Findings'],['documents','Documents'],['timeline','Timeline']].map(([k,label])=>`<button type="button" role="tab" aria-selected="${S.chartTab===k}" aria-controls="chart-body" class="${S.chartTab===k?'active':''}" data-action="chart-tab" data-id="${k}">${label}</button>`).join('')}</div><div class="compact-chart-body" id="chart-body" role="tabpanel">${chartView()}</div></aside></div>
 <dialog id="transcript-dialog"><div style="max-width:800px"><h2>Conversation transcript</h2><p style="color:var(--muted);margin-bottom:20px">${esc(p.name)} · Full conversation history</p><div class="transcript" id="transcript-view" style="max-height:60vh;overflow:auto;padding:20px;background:#fafcf6;border-radius:10px;margin-bottom:20px">${messagesView()}</div><div class="dialog-actions">${button('Close','close-dialog','','btn-primary')}</div></div></dialog>`;
}
function messagesView(){return S.encounter.messages.map(m=>`<article class="message ${m.role}" id="message-${esc(m.id)}"><div class="message-meta"><strong>${m.role==='student'?'You':esc(S.encounter.patient.name.split(' ')[0])}</strong><span>${esc(m.id)} · ${new Date(m.timestamp).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span></div><div class="message-bubble">${esc(m.text).replace(/\n/g,'<br>')}</div>${m.role==='patient'?`<div class="message-label">${icon(m.kind==='not_provided'?'info':'shield')}${m.kind==='profile'?'Approved sample wording':m.kind==='not_provided'?'Not provided in sample':'Scripted sample response'}</div>`:''}</article>`).join('');}
function chartView(){const e=S.encounter;
 if(S.chartTab==='documents')return e.artifacts.length?e.artifacts.map(a=>`<div class="attachment-row">${icon('file')}<div><strong>${esc(a.name)}</strong><small>Released clinical artifact · ${(a.size/1024).toFixed(0)} KB</small></div><button class="btn btn-small" data-action="open-artifact" data-id="${a.id}">${icon('down')}Open</button></div>`).join('')+`<p class="chart-note">Opening a document is logged separately from its release.</p>`:`<div class="empty-state">${icon('file')}<h3>No documents available yet</h3><p>Attached clinical artifacts appear when their release rules are met. The original sample includes narrative notes, not individual patient lab PDFs.</p></div>`;
 if(S.chartTab==='timeline')return e.events.map(v=>{const f=e.records.find(f=>f.id===v.fact_id);const labels={encounter_started:'Encounter started',fact_available:'Baseline information available',student_turn:'Question recorded',fact_disclosed:'Clinical information disclosed',artifact_released:'Document released',artifact_opened:'Document opened',encounter_finished:'Encounter completed',assessment_created:'Observations generated',faculty_review_saved:'Faculty review saved'};return `<div class="timeline-item"><div><strong>${esc(labels[v.type]||v.type)}</strong>${f?`<div>${esc(f.label)}</div>`:''}<small>${date(v.timestamp)}${v.turn_id?' · '+esc(v.turn_id):''}</small></div></div>`;}).join('');
 return `<div class="chart-basics"><div><span>PATIENT</span><strong>${esc(e.patient.name.split(' ')[0])}</strong></div><div><span>AGE</span><strong>${e.patient.age} years</strong></div><div><span>CASE VERSION</span><strong>v${e.patient.version}</strong></div></div>${e.records.map(f=>`<article class="record-card"><h3>${esc(f.label)}</h3><p>${esc(f.record)}</p><div class="record-meta">${icon('shield')}${f.release==='initial'?'Baseline case information':'Disclosed during this encounter'}</div></article>`).join('')}<p class="chart-note">Only released information is displayed. Missing values are not normal or negative findings. Source: supplied case data or faculty-authored facts.</p>`;
}
function scrollChat(){const el=$('#transcript');if(el)el.scrollTop=el.scrollHeight;}
function updateClock(){const el=$('#session-clock');const e=S.encounter;if(!el||!e)return;const seconds=Math.max(0,Math.floor(((e.ended_at?new Date(e.ended_at):new Date())-new Date(e.started_at))/1000));el.textContent=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
setInterval(updateClock,1000);
async function sendQuestion(){
 if(S.sending)return;const input=$('#question');const text=input.value.trim();if(!text)return;S.sending=true;const submit=$('#chat-form button[type=submit]');submit.disabled=true;input.disabled=true;const activeId=S.encounter.id;
 try{
   const r=await api('/encounters/'+activeId+'/turns','POST',{text,request_id:crypto.randomUUID()});
   if(S.route!=='encounter/'+activeId)return;
   S.encounter=r;
   // Update transcript dialog if it's open
   const transcriptView=$('#transcript-view');
   if(transcriptView){transcriptView.innerHTML=messagesView();}
   $('#chart-body').innerHTML=chartView();
   input.value='';
   if(transcriptView)scrollChat();

   // Use avatar speech if enabled and available
   const lastMessage = r.messages.at(-1);
   if(lastMessage && lastMessage.role === 'patient'){
     if(S.avatar && S.avatarEnabled){
       try{
         const emotion = lastMessage.emotion || 'neutral';
         await S.avatar.speak(lastMessage.text, emotion);
       }catch(avatarErr){
         console.error('Avatar speech error:', avatarErr);
         // Fallback to basic TTS if avatar fails
         if(ttsService.isAvailable()){
           await ttsService.speak(lastMessage.text, {}, lastMessage.emotion || 'neutral');
         }
       }
     }else if(ttsService.isAvailable()){
       // Fallback: use TTS directly without avatar
       await ttsService.speak(lastMessage.text, {}, lastMessage.emotion || 'neutral');
     }
   }
 }catch(err){toast(err.message,true);}finally{S.sending=false;submit.disabled=false;input.disabled=false;if(input.isConnected)input.focus();}
}
function historyView(){const all=S.encounters;const completed=all.filter(e=>e.status==='completed');
 return heading('REFLECT & RETURN','Your encounter history','Pick up a conversation or revisit the evidence behind your feedback.')+`<div class="stats-row"><div class="stat"><strong>${all.length}</strong><span>Saved encounters</span></div><div class="stat"><strong>${completed.length}</strong><span>Completed encounters</span></div><div class="stat"><strong>${all.filter(e=>e.feedback_status==='reviewed').length}</strong><span>Faculty-reviewed</span></div></div>`+(all.length?`<div class="panel"><div class="table-scroll"><table class="data-table"><thead><tr><th>PATIENT</th><th>STARTED</th><th>QUESTIONS</th><th>STATUS</th><th></th></tr></thead><tbody>${all.map(e=>`<tr><td><div class="table-person">${portrait(e.patient)}<div><strong>${esc(e.patient.name)}</strong><div class="small muted">Case v${e.patient.version}</div></div></div></td><td>${date(e.started_at)}</td><td>${e.turns}</td><td>${badge(e.status==='active'?'In progress':e.feedback_status==='reviewed'?'Reviewed':'Awaiting review',e.status==='active'?'neutral':e.feedback_status==='reviewed'?'':'warning')}</td><td>${button(e.status==='active'?'Continue':'View feedback','navigate',(e.status==='active'?'encounter/':'report/')+e.id,'btn-small','arrow')}</td></tr>`).join('')}</tbody></table></div></div>`:`<div class="empty-state">${icon('history')}<h3>Your first encounter starts here</h3><p>Choose a patient from the practice library. Each conversation is saved automatically.</p>${button('Meet your patients','navigate','cases','btn-primary','arrow')}</div>`);
}
function reportView(){const e=S.encounter,r=e.feedback;if(!r)return notice('This encounter is still in progress. Finish it to generate observations.')+button('Continue encounter','navigate','encounter/'+e.id,'btn-primary','arrow');
 const observed=r.checkpoints.filter(c=>c.status==='observed').length;
 return heading('ENCOUNTER / REFLECTION','A closer look at your conversation',`${e.patient.name} · ${date(e.started_at)} · Case v${e.patient.version}`,`<div class="button-row"><a class="btn" href="/api/encounters/${e.id}/export">${icon('down')}Export JSON</a>${button('New attempt','start',e.patient.id,'btn-primary','plus')}</div>`)+
 notice('<strong>Sample assessment mode.</strong> Checkpoints and language observations use transparent matching rules. They do not establish clinical quality. Official 1–4 ratings are entered by a faculty reviewer.')+
 (r.review_required?notice(`<strong>Review required:</strong> ${esc(r.review_trigger_domains.join('; '))} received a score of 1. This flag applies regardless of the total.`,'error'):'')+
 `<div class="feedback-overview"><section class="score-panel"><div class="eyebrow">FACULTY RUBRIC TOTAL</div><div class="score-number">${r.total??'—'}${r.total!==null?`<span>/ ${r.available_points}</span>`:''}</div><p>${r.total===null?(r.unrated_domains?'Awaiting faculty ratings':'No applicable rated domains'):r.unrated_domains?'Partial assessment':'Discussion aid · not a pass/fail grade'}</p><small>${r.rated_domains} rated · ${r.na_domains} N/A · ${r.unrated_domains} unreviewed<br>Full rubric maximum: 28</small></section><section class="feedback-summary"><h2>${r.status==='reviewed'?'Faculty review saved':'Evidence first. Reflection next.'}</h2><p>${observed} of ${r.checkpoints.length} case checkpoints have matching question-and-response evidence. This measures recorded disclosure, not understanding or competence.</p><p>${r.reviewer?'Reviewed by '+esc(r.reviewer)+' · Review v'+r.review_version:'Your observations are saved. A faculty reviewer can apply the official rubric using the transcript.'}</p><div class="button-row">${button('Read transcript','evidence','all','btn-small','eye')}${button('Open encounter','navigate','encounter/'+e.id,'btn-small','history')}</div></section></div>
 <div class="section-heading"><h2>Case learning checkpoints</h2><span class="small muted">Rule-based observations</span></div><div class="checkpoint-list">${r.checkpoints.map(c=>`<article class="checkpoint"><div class="checkpoint-top">${icon(c.status==='observed'?'check':'dot')}<h3>${esc(c.label)}</h3></div><p>${c.status==='observed'?'Relevant question and patient disclosure recorded.':c.status==='partial'?'Some relevant information was elicited.':esc(c.suggestion)}</p>${c.evidence_ids.length?button('Inspect evidence','evidence',c.evidence_ids.join(','),'btn-small btn-ghost','eye'):badge(c.status==='manual_review'?'Manual review':'Not observed','neutral')}</article>`).join('')}</div>
 <form id="review-form" class="panel"><div class="panel-header"><div><h2>Patient Encounter Performance Rubric</h2><p class="small muted">Official organizer rubric · seven domains · scores 1–4 or N/A</p></div>${badge(r.status.replaceAll('_',' '),r.status==='reviewed'?'':'warning')}</div>${r.domains.map(d=>domainView(d)).join('')}${S.role==='faculty'?`<div class="review-footer">${field('Reviewer name','reviewer-name',r.reviewer||'')}<button class="btn btn-primary" type="submit">${icon('check')}Save faculty review</button></div>`:`<div class="panel-content"><p class="small muted">Faculty ratings remain unreviewed until a reviewer saves them. Switch to the Faculty demo workspace to review this encounter.</p></div>`}</form>`;
}
function domainView(d){const scoreLabel=d.score===null?'Unreviewed':d.score==='N/A'?'N/A':d.score+' / 4';
 return `<section class="rubric-domain" data-domain="${esc(d.key)}"><div class="rubric-top"><span class="domain-number">${d.id}</span><h3>${esc(d.name)}</h3>${badge(scoreLabel,d.score===null?'neutral':d.score===1?'warning':'')}</div><p>${d.triggers_review_if_score_1?'A rating of 1 triggers faculty review. ':''}${d.review_note?esc(d.review_note):'Apply the published anchors to the complete encounter. Phrase matches below are suggestions to inspect, not scores.'}</p><details class="rubric-descriptors"><summary>View the official rating anchors</summary>${[4,3,2,1].map(n=>`<div class="descriptor-row"><strong>${n} · ${['','Unsafe / absent','Developing','Competent','Strong'][n]}</strong><span>${esc(d.descriptors[String(n)])}</span></div>`).join('')}<div class="descriptor-row"><strong>N/A</strong><span>Not appropriate or observable in this scenario. Record the reason.</span></div></details><div class="observations">${d.observations.length?d.observations.map(o=>`<button type="button" class="evidence-chip" data-action="evidence" data-id="${esc(o.turn_id)}">${esc(o.turn_id)} · ${esc(o.label)}</button>`).join(''):'<span class="small muted">No predefined language marker found. Inspect the transcript before rating.</span>'}</div>${S.role==='faculty'?`<div class="rating-editor"><div class="field"><label>Faculty rating<select data-key="score">${[['','Unreviewed'],['4','4 — Strong'],['3','3 — Competent'],['2','2 — Developing'],['1','1 — Unsafe / absent'],['N/A','N/A']].map(([v,l])=>`<option value="${v}" ${String(d.score??'')===v?'selected':''}>${l}</option>`).join('')}</select></label></div><div class="field"><label>Evidence-based explanation<textarea data-key="review_note" placeholder="Describe the observed strength, gap, concern, or reason for N/A.">${esc(d.review_note)}</textarea></label></div><div class="field full"><label>Supporting turn IDs — optional, separated by commas<input data-key="evidence_ids" placeholder="e.g. t1, t3" value="${esc(d.evidence_ids.join(', '))}"></label></div></div>`:d.evidence_ids.length?`<div class="observations">${button('View reviewer evidence','evidence',d.evidence_ids.join(','),'btn-small btn-ghost','eye')}</div>`:''}</section>`;
}
function rubricView(){return heading('ASSESSMENT REFERENCE','What a thoughtful encounter looks like','The official sample rubric supports discussion and reflection, not pass/fail decisions.')+notice(esc(S.rubric.instructions))+`<div class="panel">${S.rubric.domains.map(d=>`<section class="rubric-domain"><div class="rubric-top"><span class="domain-number">${d.id}</span><h3>${esc(d.name)}</h3>${d.triggers_review_if_score_1?badge('Review if rated 1','warning'):''}</div>${[4,3,2,1].map(n=>`<div class="descriptor-row"><strong>${n} · ${['','Unsafe / absent','Developing','Competent','Strong'][n]}</strong><span class="small muted">${esc(d.descriptors[n])}</span></div>`).join('')}</section>`).join('')}</div><div class="spacer-top">${notice('N/A is for domains not appropriate to the scenario. Unreviewed is a separate state. Totals show only rated domains, with N/A and unreviewed counts visible.')}</div>`;}
function resourcesView(files){return heading('FACULTY / REFERENCES','The source behind the simulation','Original challenge materials are included with the code package and available here.')+notice('Patient dialogue and checkpoint rules were adapted for this prototype. Original source files are preserved. The pediatric rubric and course syllabus are references, not automatically applied to these adult cases.')+`<div class="resource-grid">${files.map(f=>`<article class="resource-card">${icon('file')}<div><h3>${esc(f.name)}</h3><p>Organizer-provided material · ${(f.size/1024).toFixed(0)} KB</p><a class="btn btn-small" href="/api/resources/${f.id}">${icon('down')}Download source</a></div></article>`).join('')}</div>`;}
function dialog(html){$('#confirm-content').innerHTML=html;$('#confirm-dialog').showModal();}
function evidence(ids){const e=S.encounter;const selected=ids==='all'?new Set(e.messages.map(m=>m.id)):new Set(ids.split(','));const relevant=ids==='all'?e.messages:e.messages.filter((m,i)=>selected.has(m.id)||selected.has(e.messages[i-1]?.id)||selected.has(e.messages[i+1]?.id));dialog(`<h2>Encounter evidence</h2><p>${esc(e.patient.name)} · Original transcript, with surrounding context.</p><div class="evidence-view">${relevant.map(m=>`<div class="evidence-turn ${selected.has(m.id)?'selected':''}"><strong>${esc(m.id)} · ${m.role==='student'?'Student':esc(e.patient.name)}</strong>${esc(m.text)}</div>`).join('')}</div><div class="dialog-actions">${button('Close','close-dialog','','btn-primary')}</div>`);}

document.addEventListener('click',async event=>{
 const el=event.target.closest('[data-action]');if(!el||el.disabled)return;const action=el.dataset.action,id=el.dataset.id;event.preventDefault();
 try{
  if(action==='navigate'){location.hash=id;return;}
  if(action==='close-dialog'){$('#confirm-dialog').close();$('#transcript-dialog')?.close();return;}
  if(action==='toggle-transcript'){$('#transcript-dialog')?.showModal();return;}
  if(action==='role'){
   if(S.dirty&&!confirm('Switch workspaces and discard unsaved case edits?'))return;
   S.dirty=false;await api('/session','POST',{role:id});S.role=id;
   if(S.route.startsWith('report/')||S.route.startsWith('encounter/'))await route();else location.hash=id==='faculty'?'studio':'cases';navigation();return;
  }
  if(action==='filter'){S.filter=id;$$('.chip').forEach(b=>{b.classList.toggle('active',b.dataset.id===id);b.setAttribute('aria-pressed',b.dataset.id===id);});$('#patient-grid').innerHTML=patientCards();return;}
  if(action==='start'){el.disabled=true;const e=await api('/encounters','POST',{patient_id:id});S.chartTab='findings';location.hash='encounter/'+e.id;return;}
  if(action==='starter'){$('#question').value=el.dataset.text;$('#question').focus();return;}
  if(action==='chart-tab'){S.chartTab=id;$$('.chart-tabs button').forEach(b=>{b.classList.toggle('active',b.dataset.id===id);b.setAttribute('aria-selected',b.dataset.id===id);});$('#chart-body').innerHTML=chartView();return;}
  if(action==='finish'){dialog(`<h2>Ready to reflect?</h2><p>Finishing saves this conversation and generates evidence-based observations. You can review the transcript or start a fresh attempt afterward.</p><div class="dialog-actions">${button('Keep practicing','close-dialog','','btn')}${button('Finish & review','confirm-finish',id,'btn-primary','check')}</div>`);return;}
  if(action==='confirm-finish'){el.disabled=true;S.encounter=await api('/encounters/'+id+'/finish','POST',{});$('#confirm-dialog').close();location.hash='report/'+id;return;}
  if(action==='evidence'){evidence(id);return;}
  if(action==='open-artifact'){const eId=S.encounter.id;const response=await fetch('/api/encounters/'+eId+'/artifacts/'+id);if(!response.ok)throw new Error((await response.json()).error);const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=S.encounter.artifacts.find(x=>x.id===id).name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);S.encounter=await api('/encounters/'+eId);$('#chart-body').innerHTML=chartView();return;}
  if(action==='save-case'||action==='publish-case'){el.disabled=true;await saveCase(action==='publish-case');return;}
  if(action==='validate-case'){S.editor=collectEditor();S.validation=await api('/validate','POST',{profile:S.editor});$('#validation-result').innerHTML=validationView();toast(S.validation.errors.length?'Resolve the highlighted issues.':'Structural checks complete. Clinical review is still required.',!!S.validation.errors.length);return;}
  if(['add-fact','remove-fact','add-objective','remove-objective'].includes(action)){
   S.editor=collectEditor();S.dirty=true;
   if(action==='add-fact')S.editor.facts.push({id:'f'+crypto.randomUUID().slice(0,6),label:'',record:'',patient_text:'',keywords:[],release:'question',source:'Faculty-authored local sample'});
   if(action==='remove-fact'){S.editor.facts=S.editor.facts.filter(f=>f.id!==id);S.editor.objectives=S.editor.objectives.filter(o=>!o.fact_ids.includes(id));}
   if(action==='add-objective')S.editor.objectives.push({id:'o'+crypto.randomUUID().slice(0,6),label:'',fact_ids:[],suggestion:''});
   if(action==='remove-objective')S.editor.objectives=S.editor.objectives.filter(o=>o.id!==id);
   const scroll=window.scrollY;main.innerHTML=editorView();window.scrollTo(0,scroll);return;
  }
 }catch(err){toast(err.message,true);}finally{if(el.isConnected)el.disabled=false;}
});
main.addEventListener('input',event=>{
 if(event.target.id==='patient-search'){S.query=event.target.value;$('#patient-grid').innerHTML=patientCards();}
 if(event.target.closest('#case-form'))S.dirty=true;
});
main.addEventListener('change',event=>{
  if(event.target.id==='speak-toggle'){S.speak=event.target.checked;if(!S.speak&&'speechSynthesis'in window)speechSynthesis.cancel();}
  if(event.target.id==='avatar-toggle'){
    S.avatarEnabled=event.target.checked;
    if(!S.avatarEnabled && S.avatar){
      S.avatar.stop();
    }
    initializeAvatar();
  }
  if(event.target.closest('#case-form'))S.dirty=true;
});
main.addEventListener('keydown',event=>{if(event.target.id==='question'&&event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendQuestion();}});
main.addEventListener('submit',async event=>{
 event.preventDefault();const form=event.target;const submit=$('button[type=submit]',form);
 if(form.id==='chat-form'){sendQuestion();return;}
 if(form.id==='case-form'){try{await saveCase();}catch(err){toast(err.message,true);}return;}
 try{
  if(submit)submit.disabled=true;
  if(form.id==='upload-form'){
   if(S.dirty)throw new Error('Save your case edits before attaching a file.');
   const file=$('#upload-file').files[0];if(!file)throw new Error('Choose a file first.');if(file.size>5*1024*1024)throw new Error('Maximum file size is 5 MB.');
   const content=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file);});
   const data=await api('/patients/'+S.editor.id+'/attachments','POST',{name:file.name,content,kind:$('#upload-kind').value,release:$('#upload-release').value,keywords:$('#upload-keywords').value.split(',').map(x=>x.trim()).filter(Boolean)});
   S.attachments.push(data);main.innerHTML=editorView();toast('File attached. Publish the case to include it in new encounters.');
  }
  if(form.id==='review-form'){
   const ratings=$$('[data-domain]',form).map(el=>{const score=$('[data-key=score]',el).value;return {key:el.dataset.domain,score:score===''?null:score==='N/A'?'N/A':Number(score),review_note:$('[data-key=review_note]',el).value,evidence_ids:$('[data-key=evidence_ids]',el).value.split(',').map(x=>x.trim()).filter(Boolean)};});
   S.encounter=await api('/encounters/'+S.encounter.id+'/review','POST',{ratings,reviewer:$('#reviewer-name').value,review_version:S.encounter.feedback.review_version});main.innerHTML=reportView();toast('Faculty review saved with a versioned audit record.');
  }
 }catch(err){toast(err.message,true);}finally{if(submit?.isConnected)submit.disabled=false;}
});
window.addEventListener('hashchange',route);
window.addEventListener('beforeunload',event=>{if(S.dirty){event.preventDefault();event.returnValue='';}});
async function boot(){try{const session=await api('/session');S.role=session.role;S.rubric=await api('/rubric');await route();}catch(err){main.innerHTML=notice('Cannot reach the local backend. Start it with <code>python3 run.py</code> and open <code>http://127.0.0.1:8000</code>. '+esc(err.message),'error');}}
boot();
