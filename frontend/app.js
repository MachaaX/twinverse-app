// Import avatar components - using TalkingHead.js version
import { Avatar3D } from './components/Avatar3D-TalkingHead.js';
import { ttsService } from './components/TTSService.js';
import { voiceInput } from './components/VoiceInput.js';
import { emotionDetector } from './components/EmotionDetector.js';
import { vitalsPanel } from './components/VitalsPanel.js';

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
 trash:'M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7',
 down:'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',info:'M12 11v6 M12 7v1 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
 dot:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 8v4l3 2',
 sound:'M11 5L6 9H3v6h3l5 4z M15 8a6 6 0 0 1 0 8 M18 5a10 10 0 0 1 0 14',
 mic:'M12 1a4 4 0 0 0-4 4v7a4 4 0 0 0 8 0V5a4 4 0 0 0-4-4z M19 10v2a7 7 0 0 1-14 0v-2 M12 19v4 M8 23h8',
 eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
 flag:'M5 21V4 M5 4h11l-2 4 2 4H5',code:'M8 6l-6 6 6 6 M16 6l6 6-6 6 M14 4l-4 16',star:'M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z',
 heart:'M20.8 5.6a5.5 5.5 0 0 0-7.8 0l-1 1-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1 7.8 7.8 7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8z',
 activity:'M22 12h-4l-3 9L9 3l-3 9H2',
 thermometer:'M14 15V5a2 2 0 1 0-4 0v10a4 4 0 1 0 4 0z',
 wind:'M9.6 10H4 M14 18H4 M20 6H4 M17 10a3 3 0 1 1 0 6',
 droplet:'M12 2.7c-1.8 2.3-5 6.5-5 9.3a5 5 0 1 0 10 0c0-2.8-3.2-7-5-9.3z',
 scale:'M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5',
 lock:'M19 11h-1V7a6 6 0 0 0-12 0v4H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z M8 11V7a4 4 0 0 1 8 0v4'
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.file}"/></svg>`;
const S = {developer:false,stars:{},role:'student', patients:[], encounters:[], rubric:null, route:'', filter:'all', query:'', editor:null, attachments:[], validation:null, dirty:false, encounter:null, chartTab:'findings', sending:false, speak:false, avatarEnabled:true, avatar:null, voiceMode:false, isListening:false, measuredVitals:[], epoch:0};
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
function generationTime(value){
 const timestamp=value?new Date(value):null;
 if(!timestamp||Number.isNaN(timestamp.getTime()))return '<span class="muted">—</span>';
 const iso=timestamp.toISOString();
 return `<time datetime="${esc(iso)}" title="${esc(iso)}">${esc(timestamp.toLocaleString(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'}))}</time>`;
}
const initials=(s)=>s.split(' ').map(x=>x[0]).slice(0,2).join('');
function portrait(p,cls=''){return p.image?`<img class="${cls}" src="${esc(p.image)}" alt="Organizer-provided synthetic portrait of ${esc(p.name)}" loading="lazy">`:`<div class="placeholder-portrait ${cls}">${esc(initials(p.name || 'New Patient'))}</div>`;}

// Create tear effect overlay
function createTearEffect(){
  const tearContainer = document.createElement('div');
  tearContainer.style.cssText = 'position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;z-index:999;overflow:hidden;';

  // Create realistic tear drops - single tears from each eye
  const tears = [
    { left: '43%', delay: 0 },     // Left eye tear
    { left: '57%', delay: 0.3 },   // Right eye tear
    { left: '44%', delay: 1.0 },   // Second left tear
    { left: '56%', delay: 1.3 }    // Second right tear
  ];

  tears.forEach((tearPos, i) => {
    const tear = document.createElement('div');
    tear.style.cssText = `
      position:absolute;
      top:40%;
      left:${tearPos.left};
      width:8px;
      height:12px;
      background:linear-gradient(to bottom, rgba(200,220,255,0.9), rgba(150,180,220,0.95));
      border-radius:50% 50% 50% 50% / 30% 30% 70% 70%;
      animation:tearDrop 2.5s ease-out ${tearPos.delay}s forwards;
      box-shadow:inset 0 1px 2px rgba(255,255,255,0.5), 0 2px 6px rgba(0,0,0,0.3);
      transform:translateY(0) scaleY(1);
      filter:blur(0.3px);
    `;
    tearContainer.appendChild(tear);
  });

  // Red watery eyes effect
  const redEyes = document.createElement('div');
  redEyes.style.cssText = `
    position:absolute;
    top:38%;
    left:40%;
    width:20%;
    height:5%;
    background:radial-gradient(ellipse, rgba(255,100,100,0.4), transparent);
    filter:blur(3px);
    animation:fadeInOut 3s ease-in-out;
  `;
  tearContainer.appendChild(redEyes);

  // Add CSS animations
  if(!document.getElementById('tear-animation-style')){
    const style = document.createElement('style');
    style.id = 'tear-animation-style';
    style.textContent = `
      @keyframes tearDrop {
        0% {
          transform: translateY(0) scaleY(1);
          opacity: 0;
        }
        5% {
          opacity: 0.95;
          transform: translateY(0) scaleY(1.1);
        }
        15% {
          transform: translateY(10px) scaleY(1.2);
        }
        100% {
          transform: translateY(200px) scaleY(1.8);
          opacity: 0;
        }
      }
      @keyframes fadeInOut {
        0% { opacity: 0; }
        20% { opacity: 1; }
        80% { opacity: 1; }
        100% { opacity: 0; }
      }
    `;
    document.head.appendChild(style);
  }

  return tearContainer;
}

// Vitals Panel UI
function vitalsUI(){
  const vitals = ['heartRate', 'bloodPressure', 'temperature', 'respiratoryRate', 'oxygenSaturation', 'weight'];

  return `
    <div class="vitals-panel">
      <div class="vitals-header">
        ${icon('activity')}
        <span>Vitals</span>
      </div>
      <div class="vitals-list">
        ${vitals.map(key => {
          const status = vitalsPanel.getVitalStatus(key);
          const vital = vitalsPanel.vitals[key];
          const isLocked = !status.unlocked;
          const isMeasured = status.measured;

          return `
            <button
              type="button"
              class="vital-item ${isLocked ? 'locked' : ''} ${isMeasured ? 'measured' : ''}"
              data-action="measure-vital"
              data-vital="${key}"
              ${isLocked ? 'disabled' : ''}
              title="${isLocked ? 'Ask about ' + vital.fullName.toLowerCase() + ' to unlock' : vital.fullName}"
            >
              <div class="vital-left">
                ${icon(vital.icon)}
                <span class="vital-label">${vital.name}</span>
              </div>
              ${isLocked ? `<span class="vital-lock">${icon('lock')}</span>` : ''}
              ${isMeasured ? `<span class="vital-value">${status.value}<small>${status.unit}</small></span>` : `<span class="vital-measure">${icon('plus')}</span>`}
            </button>
          `;
        }).join('')}
      </div>
    </div>
  `;
}

// Input mode UI (chat vs voice)
function inputModeUI(){
  if(!voiceInput.isAvailable()){
    // Voice not supported, show only chat
    return `
      <form class="avatar-input-section" id="chat-form" style="display:flex">
        <textarea id="question" maxlength="4000" placeholder="Ask your patient a question…" aria-label="Your question" rows="2" required></textarea>
        <button type="submit" class="avatar-send-btn" aria-label="Send question">${icon('send')} Send</button>
      </form>
    `;
  }

  return `
    <div class="input-mode-toggle" style="display:flex;gap:8px;margin-bottom:12px;padding:4px;background:#f5f7f2;border-radius:8px;position:relative;z-index:10;">
      <button type="button" class="mode-btn ${!S.voiceMode?'active':''}" data-action="toggle-input-mode" data-mode="chat" style="flex:1;padding:8px;border:none;border-radius:6px;background:${!S.voiceMode?'white':'transparent'};cursor:pointer;font-size:12px;font-weight:${!S.voiceMode?'600':'400'};pointer-events:auto;">
        ${icon('send')} Chat Mode
      </button>
      <button type="button" class="mode-btn ${S.voiceMode?'active':''}" data-action="toggle-input-mode" data-mode="voice" style="flex:1;padding:8px;border:none;border-radius:6px;background:${S.voiceMode?'white':'transparent'};cursor:pointer;font-size:12px;font-weight:${S.voiceMode?'600':'400'};pointer-events:auto;">
        ${icon('mic')} Voice Mode
      </button>
    </div>
    <form class="avatar-input-section" id="chat-form" style="display:${!S.voiceMode?'flex':'none'}">
      <textarea id="question" maxlength="4000" placeholder="Ask your patient a question…" aria-label="Your question" rows="2" required></textarea>
      <button type="submit" class="avatar-send-btn" aria-label="Send question">${icon('send')} Send</button>
    </form>
    <div class="voice-input-section" style="display:${S.voiceMode?'flex':'none'};flex-direction:column;gap:12px;align-items:center;position:relative;z-index:10;">
      <button type="button" class="voice-btn ${S.isListening?'listening':''}" data-action="toggle-voice" style="padding:24px;border:3px solid ${S.isListening?'#e74c3c':'#1e584b'};border-radius:50%;background:${S.isListening?'#e74c3c':'#1e584b'};color:white;cursor:pointer;width:80px;height:80px;display:flex;align-items:center;justify-content:center;flex-direction:column;transition:all 0.3s;box-shadow:0 4px 12px rgba(0,0,0,0.15);pointer-events:auto;">
        ${icon('mic')}
        <span style="font-size:10px;margin-top:4px;">${S.isListening?'Listening':'Speak'}</span>
      </button>
      <div id="voice-transcript" style="width:100%;min-height:60px;padding:16px;background:#f9faf7;border-radius:8px;font-size:14px;color:#333;text-align:center;">
        ${S.isListening?'<span style="color:#666;">🎤 Speak now...</span>':'<span style="color:#999;">Tap the button and speak your question</span>'}
      </div>
    </div>
  `;
}

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
 const r=S.route.split('/')[0];const links=[['cases','library','Practice library'],...(S.role==='faculty'?[['studio','studio','Patient Studio'],['generate','send','Generate patients']]:[]),['reviews','history','Encounter history'],['rubric','file','Assessment rubric'],...(S.role==='faculty'?[['feedback','star','Feedback & reports'],['resources','file','Source materials']]:[]),['developer','code','Developer']];
 $('#navigation').innerHTML=links.map(([key,ic,label])=>`<a class="nav-link ${r===key || key==='reviews'&&r==='report'?'active':''}" href="#${key}" aria-label="${label}">${icon(ic)}<span>${label}</span>${r===key?'<i class="nav-dot"></i>':''}</a>`).join('');
 $('#role-switch').innerHTML=['student','faculty'].map(role=>`<button class="${S.role===role?'active':''}" data-action="role" data-id="${role}" aria-pressed="${S.role===role}" title="${role==='faculty'?'Faculty view · password required':'Student view'}">${role==='student'?'Student':'Faculty'}</button>`).join('');
 const labels={cases:'Practice library',studio:'Patient Studio',generate:'Generate patients',feedback:'Feedback & reports',developer:'Developer',reviews:'Encounter history',report:'Encounter feedback',encounter:'Patient encounter',rubric:'Assessment rubric',resources:'Source materials'};
 $('#page-label').textContent=labels[r] || 'Workspace';
 $('#report-slot').innerHTML=reportButton();
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
     S.storageStatus=await api('/storage/status');
     if(id==='new'){S.editor=newProfile();S.attachments=[];S.validation=null;}
     else {const r=await api('/patients/'+encodeURIComponent(id));S.editor=r.profile;S.attachments=r.attachments;S.validation=r.validation;}
     view=editorView();
   }else if(page==='generate'){
     if(S.role!=='faculty')throw new Error('Sign in to the Faculty view to generate patients.');
     S.genStatus=await api('/generator/status');view=generatorView();
   }else if(page==='developer'){
     view=S.developer?developerView(await api('/developer/data')):developerLoginView();
   }else if(page==='feedback'){
     if(S.role!=='faculty')throw new Error('Sign in to the Faculty view to see ratings and reports.');
     const [rep,sum]=await Promise.all([api('/reports'),api('/ratings/summary')]);view=feedbackView(rep.reports,sum);
   }else if(page==='encounter'||page==='report'){
     S.stars={};S.encounter=await api('/encounters/'+encodeURIComponent(id));
     // Reset vitals panel for new encounter
     vitalsPanel.reset();
     S.measuredVitals = [];
     view=page==='report'?reportView():encounterView();
   }else if(page==='reviews'){S.encounters=(await api('/encounters')).encounters;view=historyView();}
   else if(page==='rubric'){view=rubricView();}
   else if(page==='resources'){const r=await api('/resources');view=resourcesView(r.resources);}
   else {location.hash='cases';return;}
   if(epoch!==S.epoch)return;main.innerHTML=view;
   if(page==='encounter'){scrollChat();updateClock();setTimeout(()=>initializeAvatar(),100);}
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
 return heading('FACULTY WORKSPACE','Patient Studio','Shape the case. Set the learning goals. Publish when you’re ready.',`<div class="button-row">${button('Generate patient with AI','navigate','generate','btn','send')}${button('Create patient','navigate','studio/new','btn-primary','plus')}</div>`)+
 notice('The faculty view is protected by a shared demo password. Use synthetic content only; this is still not a production login system.')+
 `<div class="panel"><div class="panel-header"><h2>Your case collection</h2>${badge(S.patients.length+' patients')}</div><div class="table-scroll"><table class="data-table"><thead><tr><th>PATIENT</th><th>CASE</th><th>STATUS</th><th>VERSION</th><th>GENERATED AT</th><th></th></tr></thead><tbody>${S.patients.map(p=>`<tr><td><div class="table-person">${portrait(p)}<div><strong>${esc(p.name)}</strong><div class="muted small">${p.age} years · ${esc(p.gender)}</div></div></div></td><td>${esc(p.summary)}</td><td>${badge(p.status==='published'?'Published':'Draft',p.status==='draft'?'warning':'')}</td><td class="muted">v${p.version}</td><td class="small generation-time">${generationTime(p.generated_at)}</td><td>${button('Edit case','navigate','studio/'+p.id,'btn-small','studio')}</td></tr>`).join('')}</tbody></table></div></div>`;
}
function newProfile(){return {name:'',age:30,gender:'Not specified',summary:'',background:'',persona:'Conversational and thoughtful',source_notes:'',version:0,status:'draft',facts:[{id:'f1',label:'Presenting case',record:'',patient_text:'',topic:'concern',keywords:['what brings','main concern','symptoms','medical history'],release:'initial',source:'Faculty-authored local sample'},{id:'f2',label:'Personal background',record:'',patient_text:'',topic:'background',keywords:['work','home','background','family','live'],release:'question',source:'Faculty-authored local sample'}],objectives:[{id:'o1',label:'Explore personal background',fact_ids:['f2'],suggestion:'Ask about the patient’s circumstances and clarify their response.'}],validation_notes:[]};}
const field=(label,name,value,type='text',hint='')=>`<div class="field"><label for="${name}">${esc(label)}</label>${type==='textarea'?`<textarea id="${name}" name="${name}">${esc(value)}</textarea>`:`<input id="${name}" name="${name}" type="${type}" value="${esc(value)}" ${type==='number'?'min="0" max="120"':''}>`}${hint?`<small>${esc(hint)}</small>`:''}</div>`;
function editorView(){const p=S.editor;const generated=/AI-generated|Static example of the plain-language generator/.test(p.provenance||'');
 return heading('FACULTY / CASE AUTHORING',p.id?p.name:'Create a new patient','Clinical facts stay under your control. Published encounters use a frozen case version.',`<div class="button-row">${p.id?button('Delete patient profile','delete-case',p.id,'btn-danger','trash'):''}${button('Back to cases','navigate','studio','btn','back')}</div>`)+
 approvalStorageView(p)+(generated?notice(`<strong>Generated draft.</strong> ${esc(p.provenance)} Check every fact, especially those marked “AI-added detail” in Source, and the review flags below. Then check structure, approve and publish.`,'warning'):'')+
 `<div class="editor-layout"><form class="editor-main" id="case-form">
 <section class="panel"><div class="panel-header"><h2>Patient identity</h2>${badge(p.status==='published'?'Published v'+p.version:'Working draft',p.status==='draft'?'warning':'')}</div><div class="panel-content">${p.image?`<div class="editor-portrait">${portrait(p)}</div>`:''}<div class="form-grid">${field('Full name','name',p.name)}${field('Age','age',p.age,'number')}${field('Gender','gender',p.gender)}${field('Conversational style','persona',p.persona)}<div class="field full"><label for="summary">Case summary</label><textarea id="summary" name="summary">${esc(p.summary)}</textarea><small>Visible in the practice library. Avoid hidden learning answers.</small></div><div class="field full"><label for="background">Background</label><textarea id="background" name="background">${esc(p.background)}</textarea></div></div></div></section>
 <section class="panel"><div class="panel-header"><h2>Behavior & conversation</h2>${badge(p.dialogue_mode==='scripted'?'Scripted conversation':'AI conversation','neutral')}</div><div class="panel-content"><div class="slider-grid">${sliderField('temperament','Temperament','Friendly','Hostile',(p.difficulty||{}).temperament||2,TEMPERAMENT)}${sliderField('openness','Openness','Open','Closed off',(p.difficulty||{}).openness||2,OPENNESS)}</div><p class="small muted" id="difficulty-preview">${esc(gradingPreview((p.difficulty||{}).temperament||2,(p.difficulty||{}).openness||2))}</p><div class="form-grid spacer-top"><div class="field"><label for="dialogue_mode">Conversation</label><select id="dialogue_mode" name="dialogue_mode"><option value="scripted" ${p.dialogue_mode==='scripted'?'selected':''}>Scripted: approved wording only</option><option value="generative" ${p.dialogue_mode!=='scripted'?'selected':''}>AI with guardrails: grounded in these facts</option></select><small>AI replies may only use the facts below; anything else is blocked and replaced with the approved wording.</small></div><div class="field"><label for="behavior">How the personality shows</label><textarea id="behavior" name="behavior">${esc(p.behavior||'')}</textarea></div></div></div></section>
 <section class="panel"><div class="panel-header"><h2>Facts & progressive disclosure</h2>${button('Add fact','add-fact','','btn-small','plus')}</div><div class="panel-content" id="facts-editor">${p.facts.map(f=>factEditor(f)).join('')}</div></section>
 <section class="panel"><div class="panel-header"><h2>Learning checkpoints</h2>${button('Add checkpoint','add-objective','','btn-small','plus')}</div><div class="panel-content"><p class="source-description">App-authored checkpoints track elicited facts. The official seven-domain rubric remains a separate faculty assessment.</p>${p.objectives.map(o=>`<div class="objective-card" data-objective="${esc(o.id)}"><div class="fact-top"><strong>${esc(o.id)}</strong><button type="button" class="icon-button" data-action="remove-objective" data-id="${esc(o.id)}" aria-label="Remove checkpoint">${icon('close')}</button></div><div class="field"><label>Learning objective<input data-key="label" value="${esc(o.label)}"></label></div><div class="field"><label>Required fact IDs, separated by commas<input data-key="fact_ids" value="${esc(o.fact_ids.join(', '))}"></label></div><div class="field"><label>Next-attempt suggestion<textarea data-key="suggestion">${esc(o.suggestion)}</textarea></label></div></div>`).join('')}</div></section>
 ${scoringCriteriaView(p)}<section class="panel"><div class="panel-header"><h2>Source notes & review flags</h2>${icon('file')}</div><div class="panel-content">${field('Original notes / provenance','source_notes',p.source_notes,'textarea','Faculty-only context. Facts must be entered explicitly above to enter the encounter.')}${field('Flags for faculty review — one per line','validation_notes',(p.validation_notes||[]).join('\n'),'textarea')}</div></section>
 </form><aside class="editor-aside"><section class="panel"><div class="panel-content"><div class="eyebrow">REVIEW & PUBLISH</div><h3 class="spacer-top">Ready for an encounter?</h3><p>Save your edits, check the structure, and confirm clinical review. Publishing never changes an encounter already in progress.</p><div id="validation-result">${validationView()}</div><label class="check-line"><input type="checkbox" id="approve-case"><span>I reviewed the clinical content, source limitations, disclosure rules, and learning checkpoints.</span></label>${button('Save draft','save-case','','btn','studio')}${button('Check structure','validate-case','','btn','shield')}${button('Approve & publish','publish-case','','btn-primary','check')}</div></section></aside></div>
 <section class="panel spacer-top"><div class="panel-header"><h2>Knowledge sources & clinical artifacts</h2>${badge(S.attachments.filter(a=>a.kind!=='portrait').length+' files','neutral')}</div><div class="panel-content"><p class="source-description">Sources remain faculty-only. Artifacts are released by their rule. Files are saved locally while drafting${S.storageStatus?.enabled?' and copied to AWS when approved':''}; document text is not automatically extracted. Publish again to include new attachments in future encounters.</p><div class="attachment-list">${S.attachments.filter(a=>a.kind!=='portrait').map(a=>`<div class="attachment-row">${icon('file')}<div><strong>${esc(a.name)}</strong><small>${a.kind==='source'?'Faculty knowledge source':a.release==='initial'?'Artifact · available at start':'Artifact · released on request'} · ${(a.size/1024).toFixed(0)} KB</small></div><a class="btn btn-small" href="/api/attachments/${a.id}">${icon('down')} Download</a></div>`).join('')}</div>${p.id?`<form id="upload-form" class="file-upload"><div class="form-grid"><div class="field"><label for="upload-file">Choose file — up to 5 MB</label><input id="upload-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,.md,.json" required></div><div class="field"><label for="upload-kind">File purpose</label><select id="upload-kind"><option value="artifact">Clinical artifact</option><option value="source">Faculty knowledge source</option></select></div><div class="field"><label for="upload-release">Release rule</label><select id="upload-release"><option value="question">On a relevant question</option><option value="initial">At encounter start</option></select></div><div class="field"><label for="upload-keywords">Trigger phrases, separated by commas</label><input id="upload-keywords" value="lab results, blood test, show records"></div></div><div class="button-row spacer-top"><button class="btn" type="submit">${icon('plus')}Attach file</button><span class="small muted">${S.storageStatus?.enabled?'Files are copied to AWS when this patient is approved.':'Files are stored on this computer.'}</span></div></form>`:notice('Save this new patient once to enable file attachments.')}</div></section>`;
}
function approvalStorageView(p){
 const storage=S.storageStatus||{enabled:false};
 if(!storage.enabled)return notice('AWS storage is off. Patient approvals and files are saved on this computer.');
 if(!storage.configured)return notice('Cloud storage setup is incomplete. Approval is blocked until the connection settings are ready. Drafts can still be saved.','warning');
 if(p.status==='published'&&p.cloud_storage?.version===p.version)return notice(`<strong>Saved to AWS.</strong> Patient profile and ${esc(p.cloud_storage.file_count)} ${p.cloud_storage.file_count===1?'file':'files'} saved when this version was approved.`);
 return notice('Approval will save the patient profile and attached files to AWS before making this version available for encounters.');
}

function factEditor(f){return `<div class="fact-card" data-fact="${esc(f.id)}"><div class="fact-top"><strong>FACT ${esc(f.id)}</strong><button type="button" class="icon-button" data-action="remove-fact" data-id="${esc(f.id)}" aria-label="Remove fact">${icon('close')}</button></div><div class="fact-grid"><div class="field"><label>Record label<input data-key="label" value="${esc(f.label)}"></label></div><div class="field"><label>Release rule<select data-key="release">${[['initial','At encounter start'],['question','When asked'],['faculty_only','Faculty only']].map(([k,v])=>`<option value="${k}" ${f.release===k?'selected':''}>${v}</option>`).join('')}</select></label></div><div class="field"><label>Clinical record text<textarea data-key="record">${esc(f.record)}</textarea></label></div><div class="field"><label>Approved patient wording<textarea data-key="patient_text">${esc(f.patient_text)}</textarea></label></div><div class="field full"><label>Trigger words and phrases<input data-key="keywords" value="${esc((f.keywords||[]).join(', '))}"></label><small>Deterministic matching supports these phrases. Broader semantic understanding needs an LLM adapter.</small></div><div class="field full"><label>Source / provenance<input data-key="source" value="${esc(f.source)}"></label></div></div></div>`;}
function validationView(){const v=S.validation;if(!v)return '<p>Run structural checks before publishing.</p>';return `<ul class="validation-list">${v.errors.length?v.errors.map(x=>`<li>${esc(x)}</li>`).join(''):'<li>Required structure and references are valid.</li>'}${v.warnings.map(x=>`<li>${esc(x)}</li>`).join('')}<li>Clinical accuracy requires faculty review.</li></ul>`;}
function collectEditor(){const form=$('#case-form');if(!form)return S.editor;const p=structuredClone(S.editor);
 ['name','gender','summary','background','persona','source_notes','behavior','dialogue_mode'].forEach(k=>p[k]=form.elements.namedItem(k).value.trim());p.difficulty={temperament:Number(form.elements.namedItem('temperament').value),openness:Number(form.elements.namedItem('openness').value)};p.age=Number(form.elements.namedItem('age').value);p.validation_notes=form.elements.namedItem('validation_notes').value.split('\n').map(x=>x.trim()).filter(Boolean);
 p.facts=$$('[data-fact]',form).map(el=>{const original=p.facts.find(f=>f.id===el.dataset.fact)||{};const f={...original,id:el.dataset.fact};$$('[data-key]',el).forEach(i=>f[i.dataset.key]=i.dataset.key==='keywords'?i.value.split(',').map(x=>x.trim()).filter(Boolean):i.value.trim());return f;});
 if(!p.id){const a=p.facts.find(f=>f.id==='f1'),b=p.facts.find(f=>f.id==='f2');if(a){a.record ||=p.summary;a.patient_text ||=p.summary;}if(b){b.record ||=p.background;b.patient_text ||=p.background;}}
 p.objectives=$$('[data-objective]',form).map(el=>{const o={id:el.dataset.objective};$$('[data-key]',el).forEach(i=>o[i.dataset.key]=i.dataset.key==='fact_ids'?i.value.split(',').map(x=>x.trim()).filter(Boolean):i.value.trim());return o;});return p;
}
async function saveCase(publish=false){
 if(S.caseSaving)throw new Error('A patient save is in progress. Wait for it to finish.');
 const p=collectEditor();if(publish&&!$('#approve-case').checked)throw new Error('Confirm faculty review before publishing.');
 const epoch=S.epoch,controls=$$('input,textarea,select,button',main).map(el=>({el,disabled:el.disabled}));
 const publishButton=$('[data-action="publish-case"]'),originalLabel=publishButton?.innerHTML;
 let result={profile:structuredClone(S.editor),attachments:S.attachments,validation:S.validation},saved=false;
 S.caseSaving=true;controls.forEach(({el})=>el.disabled=true);
 try{
  if(!publish||S.dirty||!p.id){result=await api(p.id?'/patients/'+p.id:'/patients',p.id?'PUT':'POST',{profile:p});saved=true;}
  if(publish){if(epoch===S.epoch&&publishButton)publishButton.textContent=S.storageStatus?.enabled?'Saving to AWS…':'Publishing…';result=await api('/patients/'+result.profile.id+'/publish','POST',{approved:true,draft_version:result.profile.version});saved=true;}
 }finally{
  S.caseSaving=false;
  if(epoch===S.epoch){
   if(saved){S.editor=result.profile;S.attachments=result.attachments;S.validation=result.validation;if(result.storage)S.storageStatus=result.storage;S.dirty=false;const newRoute='studio/'+result.profile.id;S.route=newRoute;history.replaceState(null,'','#'+newRoute);navigation();main.innerHTML=editorView();}
   else{controls.forEach(({el,disabled})=>{if(el.isConnected)el.disabled=disabled;});if(publishButton?.isConnected)publishButton.innerHTML=originalLabel;}
  }
 }
 toast(publish?(result.profile.cloud_storage?'Patient published and saved to AWS.':'Patient published. Ready for a new encounter.'):'Draft saved.');
}
function encounterView(){const e=S.encounter;const p=e.patient;
 return `<div class="encounter-top"><div class="encounter-heading"><a class="back-button" href="#cases" aria-label="Save and leave encounter">${icon('back')}</a><div><h1>Patient encounter</h1><p class="muted">Your conversation is saved automatically.</p></div></div><div class="button-row">${badge(e.status==='active'?'In progress':'Completed',e.status==='active'?'':'neutral')}${e.status==='active'?button('Finish encounter','finish',e.id,'btn-primary','check'):button('View feedback','navigate','report/'+e.id,'btn-primary','arrow')}<button class="btn btn-small" data-action="toggle-transcript" id="transcript-toggle">${icon('history')} View transcript</button></div></div>
 <div class="encounter-layout-3d"><section class="avatar-main-panel"><div class="avatar-display-area"><div id="avatar-container" style="width:100%;height:100%">${S.avatarEnabled?'<div class="avatar-loading-3d"><span class="spinner"></span><span>Initializing 3D avatar...</span></div>':portrait(p)}</div></div><div class="avatar-controls-bar"><div class="avatar-patient-info"><div><h3>${esc(p.name)}</h3><p>${p.age} years · ${esc(p.gender)} · Case v${p.version} · ${badge('Synthetic','neutral')}</p></div><span class="session-clock" id="session-clock" style="margin-left:auto;font-size:11px;color:var(--muted)"></span></div></div>${e.status==='active'?`<div style="padding:18px 24px;border-top:1px solid var(--line);background:#fff"><div class="starters" style="margin-bottom:12px"><button class="starter" data-action="starter" data-text="Hello, my name is Alex. I'm a student clinician. What brings you in today?">Open the conversation</button><button class="starter" data-action="starter" data-text="Could you tell me about your work and home life?">Explore context</button><button class="starter" data-action="starter" data-text="What questions or concerns do you have?">Ask about concerns</button></div>${inputModeUI()}<div style="margin-top:10px;font-size:9px;color:var(--muted);display:flex;gap:12px;justify-content:space-between"><span>Enter to send · Shift + Enter for new line</span>${ttsService.isAvailable()?`<label class="avatar-toggle"><input type="checkbox" id="avatar-toggle" ${S.avatarEnabled?'checked':''}> 3D Avatar with voice</label>`:''}</div></div>`:`<div class="completed-composer">This encounter is complete. Your transcript is preserved.<br>${button('Review your encounter','navigate','report/'+e.id,'btn-primary','arrow')}</div>`}</section>
 ${vitalsUI()}
 <aside class="panel compact-chart-panel"><div class="panel-header"><div class="chart-title">${icon('file')}<div><h2>Medical record</h2><small>Updates as information becomes available</small></div></div>${icon('shield')}</div><div class="chart-tabs" role="tablist" aria-label="Medical record sections">${[['findings','Findings'],['documents','Documents'],['timeline','Timeline']].map(([k,label])=>`<button type="button" role="tab" aria-selected="${S.chartTab===k}" aria-controls="chart-body" class="${S.chartTab===k?'active':''}" data-action="chart-tab" data-id="${k}">${label}</button>`).join('')}</div><div class="compact-chart-body" id="chart-body" role="tabpanel">${chartView()}</div></aside></div>
 <dialog id="transcript-dialog"><div style="max-width:800px"><h2>Conversation transcript</h2><p style="color:var(--muted);margin-bottom:20px">${esc(p.name)} · Full conversation history</p><div class="transcript" id="transcript-view" style="max-height:60vh;overflow:auto;padding:20px;background:#fafcf6;border-radius:10px;margin-bottom:20px">${messagesView()}</div><div class="dialog-actions">${button('Close','close-dialog','','btn-primary')}</div></div></dialog>`;
}
function messagesView(){if(!S.encounter.messages.length)return `<div class="transcript-start">${icon('send')}<div><strong>You start the conversation.</strong><p>Introduce yourself and your role, then ask what brings ${esc(S.encounter.patient.name.split(' ')[0])} in today. The timer starts with your first message.</p></div></div>`;return S.encounter.messages.map(m=>`<article class="message ${m.role}" id="message-${esc(m.id)}"><div class="message-meta"><strong>${m.role==='student'?'You':esc(S.encounter.patient.name.split(' ')[0])}</strong><span>${esc(m.id)} · ${new Date(m.timestamp).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span></div><div class="message-bubble">${esc(m.text).replace(/\n/g,'<br>')}</div>${m.role==='patient'?`<div class="message-label">${icon(m.kind==='not_provided'?'info':'shield')}${m.kind==='generative'?'AI reply · checked against approved facts'+(m.cached?' · consistent answer':''):m.kind==='scripted_fallback'?'Approved wording (AI reply not used)':m.kind==='profile'?'Approved sample wording':m.kind==='not_provided'?'Not provided in sample':'Scripted sample response'}</div>`:''}</article>`).join('');}
function chartView(){const e=S.encounter;
 if(S.chartTab==='findings'){
   const list=e.findings||[];
   const measured = vitalsPanel.getMeasuredVitals();
   let html = '';

   // Show measured vitals
   if(measured.length > 0){
     html += `<div class="vitals-measured-section"><h4 style="font-size:11px;font-weight:600;text-transform:uppercase;color:var(--muted);margin:0 0 10px 0;letter-spacing:0.5px">Measured Vitals</h4><ul class="vitals-measured-list">${measured.map(v => `<li class="vital-measured-item">${icon(v.icon)}<div class="vital-info"><span class="vital-label">${v.fullName}</span><strong class="vital-measured-value">${v.value} ${v.unit}</strong></div></li>`).join('')}</ul></div>`;
   }

   // Show clinical findings
   if(list.length > 0){
     html += `<div style="margin-top:${measured.length > 0 ? '20px' : '0'}"><h4 style="font-size:11px;font-weight:600;text-transform:uppercase;color:var(--muted);margin:0 0 10px 0;letter-spacing:0.5px">Clinical Findings</h4><ul class="findings-list">${list.map(f=>`<li class="finding">${icon('info')}<div><strong>${esc(f.text)}</strong><p>Added ${date(f.at)}${f.source?` · Source: ${esc(f.source)}`:''}</p></div></li>`).join('')}</ul></div>`;
   }

   // Show baseline patient records (always)
   const hasContent = measured.length > 0 || list.length > 0;
   html += `<div style="margin-top:${hasContent ? '20px' : '0'}"><h4 style="font-size:11px;font-weight:600;text-transform:uppercase;color:var(--muted);margin:0 0 10px 0;letter-spacing:0.5px">Patient Information</h4>${e.records.map(f=>`<article class="record-card" style="padding:12px 0;border-bottom:1px solid var(--line)"><h3 style="font-size:12px;font-weight:600;margin-bottom:6px">${esc(f.label)}</h3><p style="font-size:11px;color:#637360;line-height:1.7;white-space:pre-line">${esc(f.record)}</p><div style="font-size:9px;color:#899681;margin-top:7px;display:flex;align-items:center;gap:5px">${icon('shield')} ${f.release==='initial'?'Baseline case information':'Disclosed during this encounter'}</div></article>`).join('')}</div>`;

   return html;
 }
 if(S.chartTab==='documents')return e.artifacts.length?e.artifacts.map(a=>`<div class="attachment-row">${icon('file')}<div><strong>${esc(a.name)}</strong><small>Released clinical artifact · ${(a.size/1024).toFixed(0)} KB</small></div><button class="btn btn-small" data-action="open-artifact" data-id="${a.id}">${icon('down')}Open</button></div>`).join('')+`<p class="chart-note">Opening a document is logged separately from its release.</p>`:`<div class="empty-state">${icon('file')}<h3>No documents available yet</h3><p>Attached clinical artifacts appear when their release rules are met. The original sample includes narrative notes, not individual patient lab PDFs.</p></div>`;
 if(S.chartTab==='timeline')return e.events.map(v=>{const f=e.records.find(f=>f.id===v.fact_id);const labels={encounter_started:'Encounter started',fact_available:'Baseline information available',student_turn:'Question recorded',fact_disclosed:'Clinical information disclosed',artifact_released:'Document released',artifact_opened:'Document opened',encounter_finished:'Encounter completed',assessment_created:'Observations generated',faculty_review_saved:'Faculty review saved',guardrail_blocked:'Approved wording used instead of an AI reply',rating_saved:'Rating saved',feedback_released:'Score released to student'};return `<div class="timeline-item"><div><strong>${esc(labels[v.type]||v.type)}</strong>${f?`<div>${esc(f.label)}</div>`:''}<small>${date(v.timestamp)}${v.turn_id?' · '+esc(v.turn_id):''}</small></div></div>`;}).join('');

 // Default view - show baseline patient records AND measured vitals
 const measured = vitalsPanel.getMeasuredVitals();
 let html = `<div class="chart-basics"><div><span>PATIENT</span><strong>${esc(e.patient.name.split(' ')[0])}</strong></div><div><span>AGE</span><strong>${e.patient.age} years</strong></div><div><span>CASE VERSION</span><strong>v${e.patient.version}</strong></div></div>`;

 // Show measured vitals in default view
 if(measured.length > 0){
   html += `<div class="vitals-measured-section" style="margin-bottom:20px"><h4 style="font-size:11px;font-weight:600;text-transform:uppercase;color:var(--muted);margin:0 0 10px 0;letter-spacing:0.5px">Measured Vitals</h4><ul class="vitals-measured-list">${measured.map(v => `<li class="vital-measured-item">${icon(v.icon)}<div class="vital-info"><span class="vital-label">${v.fullName}</span><strong class="vital-measured-value">${v.value} ${v.unit}</strong></div></li>`).join('')}</ul></div>`;
 }

 // Show baseline medical records
 html += `${e.records.map(f=>`<article class="record-card"><h3>${esc(f.label)}</h3><p>${esc(f.record)}</p><div class="record-meta">${icon('shield')}${f.release==='initial'?'Baseline case information':'Disclosed during this encounter'}</div></article>`).join('')}<p class="chart-note">Only released information is displayed. Missing values are not normal or negative findings. Source: supplied case data or faculty-authored facts.</p>`;

 return html;
}
function scrollChat(){const el=$('#transcript-view')||$('#transcript');if(el)el.scrollTop=el.scrollHeight;}
function updateClock(){const el=$('#session-clock');const e=S.encounter;if(!el||!e)return;if(!e.clock_started_at){el.textContent='00:00';el.title='The timer starts with your first message';return;}const seconds=Math.max(0,Math.floor(((e.ended_at?new Date(e.ended_at):new Date())-new Date(e.clock_started_at))/1000));el.textContent=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
setInterval(updateClock,1000);

// Voice input functions
function startVoiceInput(){
  if(!voiceInput.isAvailable()){
    toast('Voice input not supported in this browser', true);
    return;
  }

  S.isListening = true;
  updateVoiceUI();

  let interimTranscript = '';

  voiceInput.startListening({
    onStart: () => {
      console.log('[Voice] Started listening');
      S.isListening = true;
      updateVoiceUI();
    },
    onResult: (transcript, isFinal) => {
      const transcriptEl = $('#voice-transcript');
      if(transcriptEl){
        if(isFinal){
          console.log('[Voice] Final transcript:', transcript);
          transcriptEl.textContent = transcript;
          // Send the question
          setTimeout(() => sendVoiceQuestion(transcript), 500);
        }else{
          interimTranscript = transcript;
          transcriptEl.innerHTML = `<span style="color:#666;">${esc(transcript)}</span>`;
        }
      }
    },
    onEnd: () => {
      console.log('[Voice] Stopped listening');
      S.isListening = false;
      updateVoiceUI();
    },
    onError: (error) => {
      console.error('[Voice] Error:', error);
      S.isListening = false;
      updateVoiceUI();
      toast('Voice input error: ' + (error.error || error.message), true);
    }
  });
}

function stopVoiceInput(){
  voiceInput.stopListening();
  S.isListening = false;
  updateVoiceUI();
}

function toggleVoiceInput(){
  if(S.isListening){
    stopVoiceInput();
  }else{
    startVoiceInput();
  }
}

function updateVoiceUI(){
  const voiceBtn = $('[data-action="toggle-voice"]');
  const transcriptEl = $('#voice-transcript');

  if(voiceBtn){
    voiceBtn.className = `voice-btn ${S.isListening?'listening':''}`;
    voiceBtn.style.borderColor = S.isListening?'#e74c3c':'#1e584b';
    voiceBtn.style.background = S.isListening?'#e74c3c':'#1e584b';
    voiceBtn.innerHTML = `${icon('mic')} ${S.isListening?'Listening...':'Speak'}`;
  }

  if(transcriptEl && !S.isListening){
    transcriptEl.innerHTML = '<span style="color:#999;">Tap the button and speak your question</span>';
  }
}

async function sendVoiceQuestion(text){
  if(!text || !text.trim()) return;

  // Use the same sendQuestion logic
  const input = $('#question');
  if(input){
    input.value = text;
    await sendQuestion();
    input.value = '';
  }
}

async function sendQuestion(){
 if(S.sending)return;const input=$('#question');const text=input.value.trim();if(!text)return;S.sending=true;const submit=$('#chat-form button[type=submit]');submit.disabled=true;input.disabled=true;const activeId=S.encounter.id;
 try{
   // Check if any vitals should be unlocked based on conversation
   const conversationText = (S.encounter.messages || []).map(m => m.text).join(' ') + ' ' + text;
   const unlocked = vitalsPanel.checkForUnlocks(conversationText);
   if(unlocked.length > 0){
     console.log('[Vitals] Unlocked:', unlocked.join(', '));
     // Update vitals UI
     setTimeout(() => {
       const vitalsContainer = $('.vitals-panel');
       if(vitalsContainer){
         vitalsContainer.outerHTML = vitalsUI();
       }
     }, 500);
   }

   // Detect emotion in student's question BEFORE sending
   const reaction = emotionDetector.getAvatarReaction(text);
   console.log('[Emotion] Detected:', reaction.emotion, 'Mood:', reaction.mood);

   // Show avatar reaction to student's tone
   if(S.avatarEnabled && S.avatar && S.avatar.head && reaction.detected && reaction.mood !== 'neutral'){
     console.log('[Emotion] Setting avatar mood to:', reaction.mood);
     try {
       S.avatar.head.setMood(reaction.mood);
       // Brief pause to show the emotional reaction
       await new Promise(resolve => setTimeout(resolve, 800));
     } catch(err) {
       console.warn('[Emotion] Failed to set mood:', err);
     }
   }

   const r=await api('/encounters/'+activeId+'/turns','POST',{text,request_id:crypto.randomUUID()});
   if(S.route!=='encounter/'+activeId)return;
   S.encounter=r;
   const transcript=$('#transcript-view')||$('#transcript');
   if(transcript)transcript.innerHTML=messagesView();
   const chart=$('#chart-body');if(chart)chart.innerHTML=chartView();
   input.value='';scrollChat();

   // Reset to neutral before speaking
   if(S.avatarEnabled && S.avatar && S.avatar.head){
     setTimeout(() => {
       try {
         S.avatar.head.setMood('neutral');
       } catch(err) { }
     }, 500);
   }

   const last=r.messages.at(-1);
   if(last&&last.role==='patient'){
     if(S.avatar&&S.avatarEnabled){
       try{await S.avatar.speak(last.text,last.emotion||'neutral');}
       catch(avatarErr){console.error('Avatar speech error:',avatarErr);if(ttsService.isAvailable())await ttsService.speak(last.text,{},last.emotion||'neutral');}
     }else if(ttsService.isAvailable()){
       await ttsService.speak(last.text,{},last.emotion||'neutral');
     }
   }
 }catch(err){toast(err.message,true);}finally{S.sending=false;submit.disabled=false;input.disabled=false;if(input.isConnected)input.focus();}
}
function historyStatus(e){
 if(e.status==='active')return ['In progress','neutral'];
 if(S.role!=='faculty')return e.released?['Score released','']:['Awaiting faculty review','warning'];
 if(e.released&&!e.release_pending)return ['Released to student',''];
 if(e.released)return ['Edits not released','warning'];
 return e.feedback_status==='reviewed'?['Reviewed · not released','warning']:['Needs review','warning'];
}
function historyView(){const all=S.encounters;const completed=all.filter(e=>e.status==='completed');
 return heading('REFLECT & RETURN','Your encounter history','Pick up a conversation or revisit the evidence behind your feedback.')+`<div class="stats-row"><div class="stat"><strong>${all.length}</strong><span>Saved encounters</span></div><div class="stat"><strong>${completed.length}</strong><span>Completed encounters</span></div><div class="stat"><strong>${all.filter(e=>e.released).length}</strong><span>Scores released</span></div></div>`+(all.length?`<div class="panel"><div class="table-scroll"><table class="data-table"><thead><tr><th>PATIENT</th><th>STARTED</th><th>QUESTIONS</th><th>STATUS</th><th></th></tr></thead><tbody>${all.map(e=>`<tr><td><div class="table-person">${portrait(e.patient)}<div><strong>${esc(e.patient.name)}</strong><div class="small muted">Case v${e.patient.version}</div></div></div></td><td>${date(e.started_at)}</td><td>${e.turns}</td><td>${badge(...historyStatus(e))}</td><td>${button(e.status==='active'?'Continue':'View feedback','navigate',(e.status==='active'?'encounter/':'report/')+e.id,'btn-small','arrow')}</td></tr>`).join('')}</tbody></table></div></div>`:`<div class="empty-state">${icon('history')}<h3>Your first encounter starts here</h3><p>Choose a patient from the practice library. Each conversation is saved automatically.</p>${button('Meet your patients','navigate','cases','btn-primary','arrow')}</div>`);
}
const lines=list=>(list||[]).join('\n');
const splitLines=value=>value.split('\n').map(x=>x.trim()).filter(Boolean);
const turnChip=(id,label)=>/^t\d+$/.test(id||'')?`<button type="button" class="evidence-chip" data-action="evidence" data-id="${esc(id)}">${esc(label||id)}</button>`:'';
function criteriaView(d){const c=d.criteria||[];if(!c.length)return '';
 return `<details class="criteria-block" ${S.role==='faculty'?'open':''}><summary>${c.filter(x=>x.met).length} of ${c.length} scoring criteria met</summary><ul class="criteria-list">${c.map(x=>`<li class="criterion ${x.met?'met':x.forgiven?'forgiven':'missed'}">${icon(x.met?'check':'dot')}<div><strong>${esc(x.criterion)}</strong> ${badge(x.tier,x.tier==='critical'?'warning':'neutral')} ${x.forgiven&&!x.met?badge(x.forgiven==='dropped'?'not counted':'half weight','neutral'):''} ${x.met?(x.evidence||[]).slice(0,3).map(ev=>turnChip(ev.turn_id,ev.quote&&ev.quote.length<60?ev.turn_id+' · '+ev.quote:ev.turn_id)).join(''):`<p>${esc(x.feedback)}</p>`}</div></li>`).join('')}</ul></details>`;}
function releaseNotice(r){
 if(r.released)return notice(`<strong>Released to the student</strong> by ${esc(r.released_by)} · ${date(r.released_at)} · review v${r.released_review_version}. Saving new edits keeps this version visible to the student until you release again.`);
 if(r.released_at)return notice('<strong>Edits not yet released.</strong> The student still sees the previously released version. Use <strong>Save &amp; release</strong> to send the update.','warning');
 return notice('<strong>Not released yet.</strong> The student sees “awaiting faculty review” and no scores. Check the auto-suggested scores and feedback below, change anything you disagree with, then <strong>Save &amp; release to student</strong>.','warning');
}
function autoScoreView(r){const a=r.auto_score;if(!a)return '';const v=a.vitals||{};
 const flagged=r.domains.filter(d=>d.triggers_review_if_score_1&&d.suggested_score===1).map(d=>d.name);
 const reasons=[...flagged.map(n=>esc(n)+' was suggested as 1 (official review trigger)'),...((a.unsafe_actions||[]).length?['possible unsafe statement detected']:[])];
 return `<section class="panel auto-panel"><div class="panel-header"><div><h2>Auto-suggested score</h2><p class="small muted">Draft from clinical scoring criteria v${esc(a.criteria_version)}. Ratings below are pre-filled with these suggestions; you set the final score.</p></div><div class="score-number">${a.total}<span>/ ${a.available_points}</span></div></div><div class="panel-content">${reasons.length?notice('<strong>Check before releasing:</strong> '+reasons.join('; ')+'. Review the evidence and adjust the rating if needed.','error'):''}${(a.unsafe_actions||[]).length?`<p class="small"><strong>Possible unsafe statements:</strong></p><div class="observations">${a.unsafe_actions.map(x=>turnChip(x.turn_id,x.id+' · '+x.turn_id)||badge(x.id+' · '+x.quote,'warning')).join('')}</div>`:''}${v.news2?`<p class="small">NEWS2 ${v.news2.score} · abnormal vitals: ${esc((v.abnormalities||[]).join(', '))}</p>`:''}${a.gathering&&a.gathering.note?`<p class="small"><strong>Information gathering:</strong> ${esc(a.gathering.note)}</p>`:''}${a.difficulty?`<p class="small"><strong>Difficulty adjustments</strong> (temperament ${a.difficulty.temperament}/5, openness ${a.difficulty.openness}/5):</p><ul class="small">${a.difficulty.changes.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}${(()=>{const g=(S.encounter.events||[]).filter(v=>v.type==='guardrail_blocked'),off=g.filter(v=>/^AI unavailable/.test(v.reason||'')),blocked=g.filter(v=>!/^AI unavailable/.test(v.reason||''));return (blocked.length?`<p class="small"><strong>Guardrails:</strong> ${blocked.length} AI ${blocked.length===1?'reply was':'replies were'} blocked and replaced with approved wording: ${blocked.map(v=>`${esc(v.turn_id)} (${esc((v.reason||'').replace(/^AI reply blocked: /,''))})`).join('; ')}.</p>`:'')+(off.length?`<p class="small muted">Live AI was unavailable for ${off.length} ${off.length===1?'reply':'replies'}; approved wording was used (${off.map(v=>esc(v.turn_id)).join(', ')}).</p>`:'');})()}<div class="rating-split"><div>${starsWidget('auto_score',(S.encounter.ratings||{}).auto_score,'How accurate was this automatic score?')}</div><div><p class="small"><strong>Student's rating of the conversation</strong></p><p class="small">${readOnlyStars((S.encounter.ratings||{}).student)}</p></div></div>${(a.profile_gaps_to_acknowledge||[]).length?`<p class="small muted">Not in this case profile (students should not invent these): ${esc(a.profile_gaps_to_acknowledge.join('; '))}</p>`:''}</div></section>`;}
function summaryEditor(s){return `<section class="panel-content summary-editor"><h2>Feedback to the student</h2><p class="small muted">Pre-filled from the automatic criteria. Edit, delete, or add lines (one item per line).</p><div class="form-grid">${field('Overall comments','summary-comments',s.comments||'','textarea')}${field('Strengths','summary-strengths',lines(s.strengths),'textarea')}${field('Areas to improve','summary-improvements',lines(s.improvements),'textarea')}${field('Next-attempt suggestions','summary-next',lines(s.next_steps),'textarea')}</div></section>`;}
function summaryView(s){if(!s)return '';const list=(t,items)=>items&&items.length?`<div><h3>${t}</h3><ul>${items.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:'';
 return `<section class="panel summary-view"><div class="panel-content"><div class="eyebrow">FROM YOUR FACULTY REVIEWER</div>${s.comments?`<p class="spacer-top">${esc(s.comments).replace(/\n/g,'<br>')}</p>`:''}<div class="summary-columns">${list('What went well',s.strengths)}${list('What to work on',s.improvements)}${list('For your next attempt',s.next_steps)}</div></div></section>`;}
function qualityView(q){if(!q||!q.turns)return '';const s=q.student,p=q.patient;const mins=q.duration_seconds!=null?`${Math.floor(q.duration_seconds/60)}m ${q.duration_seconds%60}s`:'—';
 const stat=(n,l)=>`<div class="stat"><strong>${n}</strong><span>${l}</span></div>`;
 return `<section class="panel quality-panel"><div class="panel-header"><div><h2>Conversation quality</h2><p class="small muted">Tone, questions and patient response, from the transcript. Click a message to see it.</p></div></div><div class="panel-content">
 <div class="stats-row">${stat(mins,'Conversation time')}${stat(`${s.warm}/${s.turns}`,'Warm messages')}${stat(s.empathy_statements,'Empathy statements')}${stat(s.questions?`${s.open_questions}:${s.closed_questions}`:'—','Open : closed questions')}</div>
 <div class="tone-row">${q.turns.map(t=>`<button type="button" class="tone-chip tone-${t.tone}" data-action="evidence" data-id="${esc(t.turn_id)}" title="${esc(t.tone+(t.warm.length?' · '+t.warm.join(', '):'')+(t.cold.length?' · '+t.cold.join(', '):''))}">${esc(t.turn_id)}</button>`).join('')}<span class="small muted">warm · neutral · cold</span></div>
 <ul class="small">${q.summary.map(x=>`<li>${esc(x)}</li>`).join('')}${p.guarded_replies.length?`<li>Guarded patient replies: ${p.guarded_replies.map(id=>turnChip(id)).join('')}</li>`:''}</ul></div></section>`;}
function checkpointsView(r){return `<div class="section-heading"><h2>Case learning checkpoints</h2><span class="small muted">Rule-based observations</span></div><div class="checkpoint-list">${r.checkpoints.map(c=>`<article class="checkpoint"><div class="checkpoint-top">${icon(c.status==='observed'?'check':'dot')}<h3>${esc(c.label)}</h3></div><p>${c.status==='observed'?'Relevant question and patient disclosure recorded.':c.status==='partial'?'Some relevant information was elicited.':esc(c.suggestion)}</p>${c.evidence_ids.length?button('Inspect evidence','evidence',c.evidence_ids.join(','),'btn-small btn-ghost','eye'):badge(c.status==='manual_review'?'Manual review':'Not observed','neutral')}</article>`).join('')}</div>`;}
function scoreHistogram(r, faculty){
  const scores=(r.domains||[]).map(d=>{
    const value=d.score!==null&&d.score!==undefined
      ? d.score
      : (faculty ? d.suggested_score : null);
    return {
      name:d.name,
      value:Number.isInteger(value)&&value>=0&&value<=4 ? value : null,
      na:value==='N/A'
    };
  });
  const hasScores=scores.some(d=>d.value!==null);

  return `<section class="panel score-histogram" aria-labelledby="score-histogram-title">
    <div class="panel-header">
      <div>
        <h2 id="score-histogram-title">Candidate rubric scores</h2>
        <p class="small muted">${faculty
          ? 'Saved ratings, or suggested ratings while reviewing'
          : 'Released faculty ratings'} - one bar per rubric category</p>
      </div>
      <span class="badge neutral">Scale: 0 to 4</span>
    </div>
    ${hasScores
      ? `<div class="histogram-wrap">
          <div class="histogram-axis" aria-hidden="true">
            <span>4</span><span>3</span><span>2</span><span>1</span><span>0</span>
          </div>
          <div class="histogram-columns">
            ${scores.map(d=>`<div class="histogram-column">
              <div class="histogram-plot" role="img"
                aria-label="${esc(d.name)}: ${d.value===null
                  ? (d.na ? 'N/A' : 'unreviewed')
                  : d.value+' out of 4'}">
                <div class="histogram-bar ${d.value===null?'empty':''}"
                  style="--score-height:${d.value===null?0:d.value*25}%"></div>
              </div>
              <div class="histogram-label" title="${esc(d.name)}">${esc(d.name)}</div>
              <div class="histogram-value">${d.value===null
                ? (d.na?'N/A':'Not rated')
                : d.value+'/4'}</div>
            </div>`).join('')}
          </div>
        </div>`
      : `<p class="histogram-empty">${faculty
          ? 'No category ratings are available yet.'
          : 'Category scores will appear here after faculty releases the review.'}</p>`}
  </section>`;
}
function reportView(){const e=S.encounter,r=e.feedback;if(!r)return notice('This encounter is still in progress. Finish it to generate observations.')+button('Continue encounter','navigate','encounter/'+e.id,'btn-primary','arrow');
 const faculty=S.role==='faculty';
 const top=heading('ENCOUNTER / REFLECTION','A closer look at your conversation',`${e.patient.name} · ${date(e.started_at)} · Case v${e.patient.version}`,`<div class="button-row"><a class="btn" href="/api/encounters/${e.id}/export">${icon('down')}Export JSON</a>${button('New attempt','start',e.patient.id,'btn-primary','plus')}</div>`);
 if(!faculty&&!r.released)return top+notice('<strong>Submitted for faculty review.</strong> Your score and feedback will appear here once your faculty reviewer releases them.')+studentRatingPanel(e)+`<div class="button-row pending-actions">${button('Read transcript','evidence','all','btn-small','eye')}${button('Open encounter','navigate','encounter/'+e.id,'btn-small','history')}</div>`+checkpointsView(r);
 const observed=r.checkpoints.filter(c=>c.status==='observed').length;
 return top+(faculty?releaseNotice(r):notice(`<strong>Final feedback</strong> released by ${esc(r.released_by)} · ${date(r.released_at)}.${r.update_pending?' Your reviewer is updating this feedback.':''} Scores are a discussion aid, not a pass/fail grade.`))+
 (r.review_required?notice(`<strong>Review required:</strong> ${esc(r.review_trigger_domains.join('; '))} received a score of 1. This flag applies regardless of the total.`,'error'):'')+
 (faculty?autoScoreView(r):'')+
 `<div class="feedback-overview"><section class="score-panel"><div class="eyebrow">${faculty?'FACULTY RUBRIC TOTAL':'YOUR SCORE'}</div><div class="score-number">${r.total??'—'}${r.total!==null?`<span>/ ${r.available_points}</span>`:''}</div><p>${r.total===null?(r.unrated_domains?'Awaiting faculty ratings':'No applicable rated domains'):r.unrated_domains?'Partial assessment':'Discussion aid · not a pass/fail grade'}</p><small>${r.rated_domains} rated · ${r.na_domains} N/A · ${r.unrated_domains} unreviewed<br>Full rubric maximum: 28</small></section><section class="feedback-summary"><h2>${r.status==='reviewed'?'Faculty review saved':'Evidence first. Reflection next.'}</h2><p>${observed} of ${r.checkpoints.length} case checkpoints have matching question-and-response evidence. This measures recorded disclosure, not understanding or competence.</p><p>${r.reviewer?'Reviewed by '+esc(r.reviewer)+' · Review v'+r.review_version:'Scores below are auto-suggested drafts until a faculty reviewer saves them.'}</p><div class="button-row">${button('Read transcript','evidence','all','btn-small','eye')}${button('Open encounter','navigate','encounter/'+e.id,'btn-small','history')}</div></section></div>`+
 (faculty?'':summaryView(r.summary)+studentRatingPanel(e))+qualityView(r.sentiment)+checkpointsView(r)+
 `<form id="review-form" class="panel"><div class="panel-header"><div><h2>Patient Encounter Performance Rubric</h2><p class="small muted">Official organizer rubric · seven domains · scores 1–4 or N/A</p></div>${badge(r.status.replaceAll('_',' '),r.status==='reviewed'?'':'warning')}</div>${r.domains.map(d=>domainView(d)).join('')}${faculty?summaryEditor(r.summary||{})+`<div class="review-footer">${field('Reviewer name','reviewer-name',r.reviewer||'')}<div class="button-row"><button class="btn" type="submit" data-release="0">${icon('check')}Save review</button><button class="btn btn-primary" type="submit" data-release="1">${icon('send')}Save &amp; release to student</button></div></div>`:''}</form>`;
}
function domainView(d){const faculty=S.role==='faculty';const scoreLabel=d.score===null?'Unreviewed':d.score==='N/A'?'N/A':d.score+' / 4';
 const prefill=faculty&&d.score===null&&!d.review_note;const score=prefill?(d.suggested_score??''):(d.score??'');
 const note=prefill?(d.suggested_note||''):d.review_note;const ev=prefill?(d.suggested_evidence_ids||[]):d.evidence_ids;
 const suggested=faculty&&d.suggested_score!=null?badge('Suggested '+(d.suggested_score==='N/A'?'N/A':d.suggested_score+'/4'),'neutral'):'';
 return `<section class="rubric-domain" data-domain="${esc(d.key)}"><div class="rubric-top"><span class="domain-number">${d.id}</span><h3>${esc(d.name)}</h3>${badge(scoreLabel,d.score===null?'neutral':d.score===1?'warning':'')}${suggested}</div><p>${d.triggers_review_if_score_1&&faculty?'A rating of 1 triggers faculty review. ':''}${d.review_note?esc(d.review_note):faculty?'Apply the published anchors to the complete encounter. The rating is pre-filled with the automatic suggestion; change it if you disagree.':''}</p><details class="rubric-descriptors"><summary>View the official rating anchors</summary>${[4,3,2,1].map(n=>`<div class="descriptor-row"><strong>${n} · ${['','Unsafe / absent','Developing','Competent','Strong'][n]}</strong><span>${esc(d.descriptors[String(n)])}</span></div>`).join('')}<div class="descriptor-row"><strong>N/A</strong><span>Not appropriate or observable in this scenario. Record the reason.</span></div></details>${criteriaView(d)}${faculty?`<div class="observations">${d.observations.length?d.observations.map(o=>`<button type="button" class="evidence-chip" data-action="evidence" data-id="${esc(o.turn_id)}">${esc(o.turn_id)} · ${esc(o.label)}</button>`).join(''):'<span class="small muted">No predefined language marker found. Inspect the transcript before rating.</span>'}</div><div class="rating-editor"><div class="field"><label>Faculty rating<select data-key="score">${[['','Unreviewed'],['4','4 — Strong'],['3','3 — Competent'],['2','2 — Developing'],['1','1 — Unsafe / absent'],['N/A','N/A']].map(([v,l])=>`<option value="${v}" ${String(score)===v?'selected':''}>${l}</option>`).join('')}</select></label></div><div class="field"><label>Feedback for this domain (shown to the student)<textarea data-key="review_note" placeholder="Describe the observed strength, gap, concern, or reason for N/A.">${esc(note)}</textarea></label></div><div class="field full"><label>Supporting turn IDs — optional, separated by commas<input data-key="evidence_ids" placeholder="e.g. t1, t3" value="${esc(ev.join(', '))}"></label></div></div>`:d.evidence_ids.length?`<div class="observations">${button('View reviewer evidence','evidence',d.evidence_ids.join(','),'btn-small btn-ghost','eye')}</div>`:''}</section>`;
}
const TEMPERAMENT=['Warm and cooperative','Polite but reserved','Impatient or skeptical','Irritable, pushes back','Hostile, challenges the student'];
const OPENNESS=['Open, volunteers information','Answers what is asked','Brief answers, needs follow-up','Guarded: sensitive topics only after rapport','Closed off: deflects until trust is built'];
function sliderField(name,label,left,right,value,labels){return `<div class="field slider-field"><label for="${name}">${label}</label><input id="${name}" name="${name}" type="range" min="1" max="5" step="1" value="${value}" data-labels="${esc(JSON.stringify(labels))}"><div class="slider-scale"><span>${left}</span><strong id="${name}-label">${esc(labels[value-1])}</strong><span>${right}</span></div></div>`;}
function gradingPreview(t,o){const level=Math.max(t,o),turns=5+(o-1)+Math.floor((t-1)/2),shift=Math.min(10,5*Math.max(0,level-3));return `Grading for this patient: about ${turns} questions expected, or fewer if the key information or a correct assessment is reached${level>=3?'; adds a patience / de-escalation criterion':''}${level>=4?'; weights empathy as critical':''}${shift?`; lowers score cut-offs by ${shift} points`:''}.`;}
function generatorView(){const st=S.genStatus||{},r=S.genRequest||{text:'',temperament:2,openness:2};
 return heading('FACULTY / GENERATE PATIENTS','Describe a patient. Review the draft.','Write it the way you would brief a standardized patient. You get a patient profile, portrait, clinical reports, and a case rubric, all as a draft you review in Patient Studio before publishing.',button('Build one manually instead','navigate','studio/new','btn','studio'))+
 `<form id="gen-form" class="panel"><div class="panel-content">
  <div class="field"><label for="gen-text">Describe the patient</label><textarea id="gen-text" rows="9" placeholder="Include age, sex, the situation and main concern, history and findings (vitals, labs, imaging), personality, and what the student should learn.">${esc(r.text)}</textarea></div>
  <div class="field spacer-top"><label for="gen-files">Files <span class="muted">optional: labs, X-ray reports, prior notes, guidelines (PDF, PNG, JPG, TXT, MD · up to 4 · 5 MB each)</span></label><input id="gen-files" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.txt,.md"></div>
  <div class="slider-grid spacer-top">${sliderField('gen-temperament','Temperament','Friendly','Hostile',r.temperament,TEMPERAMENT)}${sliderField('gen-openness','Openness','Open','Closed off',r.openness,OPENNESS)}</div>
  <p class="small muted" id="gen-preview">${esc(gradingPreview(r.temperament,r.openness))}</p>
  <div id="gen-check">${genCheckView()}</div>
  <div class="button-row spacer-top"><button class="btn btn-primary" type="submit" ${st.live_available?'':'disabled'}>${icon('send')}Generate patient</button>${button('Load static example','gen-example','','btn','file')}${st.live_available?button('Test connection','gen-test','','btn btn-ghost','shield'):''}</div>
  <p class="small muted spacer-top">${badge(st.live_available?'Live AI ready':'Live AI off',st.live_available?'':'warning')} ${esc(st.reason||'')}${st.model?` · ${esc(st.model)} + ${esc(st.image_model)} · ${esc(st.region)}`:''}</p>
 </div></form>`;
}
function genCheckView(){const c=S.genCheck;if(!c)return '';
 return `<ul class="validation-list">${c.errors.map(x=>`<li class="gen-error">${esc(x)}</li>`).join('')}${c.warnings.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;}
async function collectRequest(){const files=[...($('#gen-files').files||[])];if(files.length>4)throw new Error('Attach at most 4 files.');
 const read=f=>new Promise((resolve,reject)=>{if(f.size>5*1024*1024)return reject(new Error(f.name+' is over 5 MB.'));const r=new FileReader();r.onload=()=>resolve({name:f.name,content:r.result.split(',')[1]});r.onerror=reject;r.readAsDataURL(f);});
 return {text:$('#gen-text').value,temperament:Number($('#gen-temperament').value),openness:Number($('#gen-openness').value),files:await Promise.all(files.map(read))};}
async function openGeneratedDraft(r,message){S.editor=r.profile;S.attachments=r.attachments;S.validation=r.validation;S.storageStatus=await api('/storage/status');S.dirty=false;S.route='studio/'+r.profile.id;history.replaceState(null,'','#'+S.route);navigation();main.innerHTML=editorView();window.scrollTo(0,0);toast(message);}
function scoringCriteriaView(p){const c=p.scoring_criteria||[];if(!c.length)return '';
 return `<section class="panel"><div class="panel-header"><h2>Case rubric</h2>${badge(c.length+' criteria','neutral')}</div><div class="panel-content"><p class="source-description">Scored with the organizer's seven-domain rubric and the universal communication criteria. Each criterion names the source it is built on. Temperament and openness adjust grading automatically.</p><ul class="criteria-list">${c.map(x=>`<li class="criterion">${icon('check')}<div><strong>${esc(x.criterion)}</strong> ${badge('Domain '+x.domain,'neutral')} ${badge(x.tier,x.tier==='critical'?'warning':'neutral')}<p>Source: ${esc(x.source||'Faculty')} · Listens for: ${esc((x.cues||[]).join(', '))}</p></div></li>`).join('')}</ul></div></section>`;}
function reportButton(){return `<button type="button" class="btn btn-small btn-ghost report-btn" data-action="report-problem" title="Report a problem with this page">${icon('flag')}<span>Report a problem</span></button>`;}
function reportProblem(){const e=S.encounter&&S.route.includes(S.encounter.id)?S.encounter:null;const last=e&&e.messages.length?e.messages.at(-1).id:'';
 const cats=[['patient_answer','Patient said something wrong or made something up'],['scoring','Score or feedback looks wrong'],['bug','Something broke or did not load'],['content','Clinical content looks inaccurate'],['other','Other']];
 dialog(`<form id="report-form"><h2>Report a problem</h2><p>Tell us what went wrong. We attach the page${e?`, this encounter (${esc(e.patient.name)}) and the latest message (${esc(last)})`:''} and your role. No patient data leaves this computer.</p>
 <div class="field"><label for="report-category">What kind of problem?</label><select id="report-category">${cats.map(([k,l])=>`<option value="${k}" ${e&&k==='patient_answer'&&S.route.startsWith('encounter')?'selected':''}>${esc(l)}</option>`).join('')}</select></div>
 <div class="field spacer-top"><label for="report-message">What happened?</label><textarea id="report-message" rows="4" placeholder="e.g. At t5 the patient said he takes metformin, but no medication is in his case." required></textarea></div>
 <p class="login-error" id="report-error" role="alert" hidden></p><div class="dialog-actions">${button('Cancel','close-dialog','','btn')}<button type="submit" class="btn btn-primary">${icon('flag')}Send report</button></div></form>`);$('#report-message').focus();}
function starsWidget(kind,saved,prompt){const current=S.stars[kind]??saved?.stars??0;
 return `<div class="rating-widget" data-kind="${kind}"><p class="small"><strong>${esc(prompt)}</strong></p><div class="stars" role="radiogroup" aria-label="${esc(prompt)}">${[1,2,3,4,5].map(n=>`<button type="button" class="star ${n<=current?'on':''}" data-action="star" data-id="${kind}:${n}" role="radio" aria-checked="${n===current}" aria-label="${n} star${n>1?'s':''}">★</button>`).join('')}</div>
 <textarea id="${kind}-comment" rows="2" placeholder="Optional comment">${esc(saved?.comment||'')}</textarea><div class="button-row">${button(saved?'Update rating':'Save rating','save-rating',kind,'btn btn-small','check')}${saved?`<span class="small muted">Saved ${date(saved.at)}</span>`:''}</div></div>`;}
function studentRatingPanel(e){return `<section class="panel rating-panel"><div class="panel-content">${starsWidget('student',(e.ratings||{}).student,'How realistic and useful was this conversation?')}</div></section>`;}
function readOnlyStars(r){return r?`${'★'.repeat(r.stars)}${'☆'.repeat(5-r.stars)}${r.comment?` · “${esc(r.comment)}”`:''}`:'Not rated yet';}
function feedbackView(reports,summary){const avg=x=>x.average==null?'—':`${x.average.toFixed(1)} ★`;const stat=(n,l)=>`<div class="stat"><strong>${n}</strong><span>${l}</span></div>`;
 const comments=(list,label)=>list.length?`<ul class="comment-list">${list.map(c=>`<li><span class="small muted">${'★'.repeat(c.stars)} · ${esc(c.patient)} · ${date(c.at)}</span><p>${esc(c.comment)}</p></li>`).join('')}</ul>`:`<p class="small muted">No ${label} comments yet.</p>`;
 const open=reports.filter(r=>r.status==='open').length;
 return heading('FACULTY / FEEDBACK','Ratings and problem reports','What students think of the conversations, how faculty rate the automatic scoring, and problems reported from any screen.')+
 `<div class="stats-row">${stat(avg(summary.conversation),`Conversation rating · ${summary.conversation.count} ratings`)}${stat(avg(summary.auto_score),`Automatic score accuracy · ${summary.auto_score.count} ratings`)}${stat(open,'Open problem reports')}</div>
 <section class="panel"><div class="panel-header"><h2>Problem reports</h2>${badge(reports.length+' total','neutral')}</div><div class="panel-content">${reports.length?`<div class="table-scroll"><table class="data-table"><thead><tr><th>WHEN</th><th>TYPE</th><th>WHAT HAPPENED</th><th>WHERE</th><th>STATUS</th></tr></thead><tbody>${reports.map(r=>`<tr><td class="small">${date(r.created_at)}<div class="muted">${esc(r.role)}</div></td><td>${esc(r.category_label)}</td><td>${esc(r.message)}</td><td class="small">${r.context.encounter_id?`<a href="#report/${esc(r.context.encounter_id)}">${esc(r.context.patient||'Encounter')}${r.context.turn_id?' · '+esc(r.context.turn_id):''}</a>`:esc(r.context.route||'')}</td><td>${button(r.status==='open'?'Mark resolved':'Reopen','report-status',r.id+':'+(r.status==='open'?'resolved':'open'),'btn btn-small',r.status==='open'?'check':'history')} ${badge(r.status,r.status==='open'?'warning':'')}</td></tr>`).join('')}</tbody></table></div>`:'<p class="small muted">No problems reported yet.</p>'}</div></section>
 <div class="feedback-grid spacer-top"><section class="panel"><div class="panel-header"><h2>Student conversation ratings</h2></div><div class="panel-content">${summary.by_patient.length?`<ul class="small">${summary.by_patient.map(p=>`<li>${esc(p.patient)}: ${p.average.toFixed(1)} ★ (${p.count})</li>`).join('')}</ul>`:''}${comments(summary.conversation.recent_comments,'student')}</div></section>
 <section class="panel"><div class="panel-header"><h2>Faculty ratings of automatic scoring</h2></div><div class="panel-content">${comments(summary.auto_score.recent_comments,'faculty')}</div></section></div>`;}
function developerLoginView(){return heading('DEVELOPER','Developer data','Raw ratings and problem-report data for the team. Separate password from the faculty view.')+
 `<form id="dev-login" class="panel dev-login"><div class="panel-content"><div class="field"><label for="dev-password">Developer password</label><input id="dev-password" type="password" autocomplete="current-password" required></div><p class="small muted spacer-top">Shown in the Terminal when the app starts. Access ends when you lock it or the server restarts.</p><p class="login-error" id="dev-error" role="alert" hidden></p><div class="button-row spacer-top"><button type="submit" class="btn btn-primary">${icon('shield')}Unlock</button></div></div></form>`;}
function developerView(d){const s=d.summary;const stat=(n,l)=>`<div class="stat"><strong>${n}</strong><span>${l}</span></div>`;const avg=x=>x.average==null?'—':x.average.toFixed(2)+' ★';
 const dist=x=>`<tr>${[1,2,3,4,5].map(n=>`<td>${x.distribution[n]}</td>`).join('')}</tr>`;
 const counts=(o)=>Object.keys(o).length?`<ul class="small">${Object.entries(o).map(([k,v])=>`<li>${esc(k)}: <strong>${v}</strong></li>`).join('')}</ul>`:'<p class="small muted">None yet.</p>';
 return heading('DEVELOPER','Developer data',`Ratings and problem reports across all encounters · generated ${date(d.generated_at)}`,`<div class="button-row"><a class="btn btn-small" href="/api/developer/export/ratings.csv">${icon('down')}Ratings CSV</a><a class="btn btn-small" href="/api/developer/export/reports.csv">${icon('down')}Reports CSV</a><a class="btn btn-small" href="/api/developer/export/data.json">${icon('down')}All JSON</a>${button('Lock','dev-lock','','btn btn-small','shield')}</div>`)+
 `<div class="stats-row">${stat(avg(s.conversation),`Conversation rating · ${s.conversation.count}`)}${stat(avg(s.auto_score),`Auto-score accuracy · ${s.auto_score.count}`)}${stat(d.reports.length,'Problem reports')}${stat(s.encounters,'Encounters')}</div>
 <div class="feedback-grid"><section class="panel"><div class="panel-header"><h2>Star counts</h2></div><div class="panel-content"><div class="table-scroll"><table class="data-table"><thead><tr><th colspan="5">Conversation (students)</th></tr><tr>${[1,2,3,4,5].map(n=>`<th>${n}★</th>`).join('')}</tr></thead><tbody>${dist(s.conversation)}</tbody></table><table class="data-table spacer-top"><thead><tr><th colspan="5">Automatic score (faculty)</th></tr><tr>${[1,2,3,4,5].map(n=>`<th>${n}★</th>`).join('')}</tr></thead><tbody>${dist(s.auto_score)}</tbody></table></div></div></section>
 <section class="panel"><div class="panel-header"><h2>Reports</h2></div><div class="panel-content"><p class="small"><strong>By type</strong></p>${counts(s.reports_by_category)}<p class="small"><strong>By status</strong></p>${counts(s.reports_by_status)}<p class="small"><strong>By role</strong></p>${counts(s.reports_by_role)}</div></section></div>
 <section class="panel spacer-top"><div class="panel-header"><h2>All ratings</h2>${badge(d.ratings.length+' rows','neutral')}</div><div class="panel-content"><div class="table-scroll"><table class="data-table"><thead><tr><th>WHEN</th><th>TYPE</th><th>STARS</th><th>COMMENT</th><th>PATIENT</th><th>AUTO / FINAL</th><th>QUESTIONS</th></tr></thead><tbody>${d.ratings.map(r=>`<tr><td class="small">${date(r.at)}</td><td>${r.kind==='student'?'Conversation':'Auto score'}${r.by?`<div class="small muted">${esc(r.by)}</div>`:''}</td><td>${'★'.repeat(r.stars)}</td><td>${esc(r.comment)}</td><td><a href="#report/${esc(r.encounter_id)}">${esc(r.patient)}</a></td><td>${r.auto_total??'—'} / ${r.final_total??'—'}</td><td>${r.turns}</td></tr>`).join('')||'<tr><td colspan="7" class="muted">No ratings yet.</td></tr>'}</tbody></table></div></div></section>
 <section class="panel spacer-top"><div class="panel-header"><h2>All problem reports</h2>${badge(d.reports.length+' rows','neutral')}</div><div class="panel-content"><div class="table-scroll"><table class="data-table"><thead><tr><th>WHEN</th><th>STATUS</th><th>ROLE</th><th>TYPE</th><th>MESSAGE</th><th>CONTEXT</th></tr></thead><tbody>${d.reports.map(r=>`<tr><td class="small">${date(r.created_at)}</td><td>${badge(r.status,r.status==='open'?'warning':'')}</td><td>${esc(r.role)}</td><td>${esc(r.category_label)}</td><td>${esc(r.message)}</td><td class="small">${esc([r.context.route,r.context.patient,r.context.turn_id].filter(Boolean).join(' · '))}${r.context.user_agent?`<div class="muted">${esc(r.context.user_agent.slice(0,60))}</div>`:''}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">No reports yet.</td></tr>'}</tbody></table></div></div></section>`;}
function rubricView(){return heading('ASSESSMENT REFERENCE','What a thoughtful encounter looks like','The official sample rubric supports discussion and reflection, not pass/fail decisions.')+notice(esc(S.rubric.instructions))+`<div class="panel">${S.rubric.domains.map(d=>`<section class="rubric-domain"><div class="rubric-top"><span class="domain-number">${d.id}</span><h3>${esc(d.name)}</h3>${d.triggers_review_if_score_1?badge('Review if rated 1','warning'):''}</div>${[4,3,2,1].map(n=>`<div class="descriptor-row"><strong>${n} · ${['','Unsafe / absent','Developing','Competent','Strong'][n]}</strong><span class="small muted">${esc(d.descriptors[n])}</span></div>`).join('')}</section>`).join('')}</div><div class="spacer-top">${notice('N/A is for domains not appropriate to the scenario. Unreviewed is a separate state. Totals show only rated domains, with N/A and unreviewed counts visible.')}</div>`;}
function resourcesView(files){return heading('FACULTY / REFERENCES','The source behind the simulation','Original challenge materials are included with the code package and available here.')+notice('Patient dialogue and checkpoint rules were adapted for this prototype. Original source files are preserved. The pediatric rubric and course syllabus are references, not automatically applied to these adult cases.')+`<div class="resource-grid">${files.map(f=>`<article class="resource-card">${icon('file')}<div><h3>${esc(f.name)}</h3><p>Organizer-provided material · ${(f.size/1024).toFixed(0)} KB</p><a class="btn btn-small" href="/api/resources/${f.id}">${icon('down')}Download source</a></div></article>`).join('')}</div>`;}
async function roleChanged(role){S.role=role;if(S.route.startsWith('report/')||S.route.startsWith('encounter/'))await route();else location.hash=role==='faculty'?'studio':'cases';navigation();}
function facultyLogin(){dialog(`<form id="faculty-login"><h2>Faculty sign-in</h2><p>Enter the faculty password. It is also shown in the Terminal window where the app was started.</p><div class="field"><label for="faculty-token">Faculty password</label><input id="faculty-token" type="password" autocomplete="current-password" required></div><p class="login-error" id="login-error" role="alert" hidden></p><div class="dialog-actions">${button('Cancel','close-dialog','','btn')}<button type="submit" class="btn btn-primary">${icon('shield')}Sign in</button></div></form>`);$('#faculty-token').focus();}
document.addEventListener('submit',async event=>{
 if(event.target.id!=='dev-login')return;event.preventDefault();const err=$('#dev-error');
 try{await api('/developer/login','POST',{password:$('#dev-password').value});S.developer=true;await route();toast('Developer data unlocked.');}
 catch(e){err.textContent=e.message;err.hidden=false;$('#dev-password').select();}
});
document.addEventListener('submit',async event=>{
 if(event.target.id!=='report-form')return;event.preventDefault();const err=$('#report-error'),submit=$('#report-form button[type=submit]');submit.disabled=true;
 try{const e=S.encounter&&S.route.includes(S.encounter.id)?S.encounter:null;
  await api('/reports','POST',{category:$('#report-category').value,message:$('#report-message').value,context:{route:S.route,encounter_id:e?.id,patient:e?.patient.name,turn_id:e&&e.messages.length?e.messages.at(-1).id:'',user_agent:navigator.userAgent}});
  $('#confirm-dialog').close();toast('Thanks, your report was sent to faculty.');}
 catch(e){err.textContent=e.message;err.hidden=false;}finally{if(submit.isConnected)submit.disabled=false;}
});
document.addEventListener('submit',async event=>{
 if(event.target.id!=='faculty-login')return;
 event.preventDefault();const submit=$('#faculty-login button[type=submit]');const err=$('#login-error');submit.disabled=true;
 try{
  await api('/session','POST',{role:'faculty',password:$('#faculty-token').value});
  S.dirty=false;$('#confirm-dialog').close();await roleChanged('faculty');toast('Signed in to the faculty view.');
 }catch(e){err.textContent=e.message;err.hidden=false;$('#faculty-token').select();}
 finally{if(submit.isConnected)submit.disabled=false;}
});
function dialog(html){$('#confirm-content').innerHTML=html;$('#confirm-dialog').showModal();}
function evidence(ids){const e=S.encounter;const selected=ids==='all'?new Set(e.messages.map(m=>m.id)):new Set(ids.split(','));const relevant=ids==='all'?e.messages:e.messages.filter((m,i)=>selected.has(m.id)||selected.has(e.messages[i-1]?.id)||selected.has(e.messages[i+1]?.id));dialog(`<h2>Encounter evidence</h2><p>${esc(e.patient.name)} · Original transcript, with surrounding context.</p><div class="evidence-view">${relevant.map(m=>`<div class="evidence-turn ${selected.has(m.id)?'selected':''}"><strong>${esc(m.id)} · ${m.role==='student'?'Student':esc(e.patient.name)}</strong>${esc(m.text)}</div>`).join('')}</div><div class="dialog-actions">${button('Close','close-dialog','','btn-primary')}</div>`);}

document.addEventListener('click',async event=>{
 const el=event.target.closest('[data-action]');if(!el||el.disabled)return;const action=el.dataset.action,id=el.dataset.id;event.preventDefault();
 try{
  if(action==='navigate'){location.hash=id;return;}
  if(action==='close-dialog'){$('#confirm-dialog').close();$('#transcript-dialog')?.close();return;}
  if(action==='toggle-transcript'){$('#transcript-dialog')?.showModal();return;}
  if(action==='toggle-input-mode'){
    console.log('[toggle-input-mode] Clicked, mode:', el.dataset.mode);
    const mode = el.dataset.mode;
    S.voiceMode = (mode === 'voice');

    // Resume audio context on first user interaction
    if(S.avatar && S.avatar.head && S.avatar.head.audioCtx){
      if(S.avatar.head.audioCtx.state === 'suspended'){
        console.log('[Audio] Resuming AudioContext');
        S.avatar.head.audioCtx.resume().catch(e => console.warn('[Audio] Resume failed:', e));
      }
    }

    if(!S.voiceMode && S.isListening){
      stopVoiceInput();
    }

    // Re-render the input UI
    const inputSection = $('#chat-form')?.parentElement;
    if(inputSection){
      const newHTML = inputModeUI();
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = newHTML;
      inputSection.innerHTML = tempDiv.innerHTML;
    }
    return;
  }
  if(action==='toggle-voice'){
    console.log('[toggle-voice] Clicked');

    // Resume audio context on first user interaction
    if(S.avatar && S.avatar.head && S.avatar.head.audioCtx){
      if(S.avatar.head.audioCtx.state === 'suspended'){
        console.log('[Audio] Resuming AudioContext');
        S.avatar.head.audioCtx.resume().catch(e => console.warn('[Audio] Resume failed:', e));
      }
    }

    toggleVoiceInput();
    return;
  }
  if(action==='role'){
   if(S.dirty&&!confirm('Switch workspaces and discard unsaved case edits?'))return;
   if(id===S.role)return;
   if(id==='faculty'){facultyLogin();return;}
   S.dirty=false;await api('/session','POST',{role:id});await roleChanged(id);toast('Signed out of the faculty view.');return;
  }
  if(action==='filter'){S.filter=id;$$('.chip').forEach(b=>{b.classList.toggle('active',b.dataset.id===id);b.setAttribute('aria-pressed',b.dataset.id===id);});$('#patient-grid').innerHTML=patientCards();return;}
  if(action==='start'){el.disabled=true;const e=await api('/encounters','POST',{patient_id:id});S.chartTab='findings';location.hash='encounter/'+e.id;return;}
  if(action==='starter'){$('#question').value=el.dataset.text;$('#question').focus();return;}
  if(action==='chart-tab'){S.chartTab=id;$$('.chart-tabs button').forEach(b=>{b.classList.toggle('active',b.dataset.id===id);b.setAttribute('aria-selected',b.dataset.id===id);});$('#chart-body').innerHTML=chartView();return;}
  if(action==='measure-vital'){
    const vitalKey = el.dataset.vital;
    console.log('[Vitals] Measuring:', vitalKey);

    // Build patient context from actual case data
    const patient = S.encounter.patient;
    const records = S.encounter.records || [];
    const allText = records.map(r => (r.label + ' ' + r.record).toLowerCase()).join(' ');
    const messages = S.encounter.messages || [];
    const conversationText = messages.map(m => m.text.toLowerCase()).join(' ');
    const fullText = allText + ' ' + conversationText;

    // Parse patient conditions from case data and conversation
    const patientContext = {
      id: patient.id,
      age: patient.age,
      gender: patient.gender,
      // Detect conditions from chief complaint and medical history
      chestPain: /chest pain|chest discomfort|cardiac|angina/i.test(fullText),
      cardiac: /heart|cardiac|coronary|myocardial/i.test(fullText),
      anxious: /anxious|anxiety|panic|worried|nervous/i.test(fullText),
      panic: /panic attack|panic disorder/i.test(fullText),
      fever: /fever|febrile|temperature|hot|chills/i.test(fullText),
      infection: /infection|infected|sepsis/i.test(fullText),
      pain: /pain|ache|hurt|discomfort/i.test(fullText),
      shortnessOfBreath: /shortness of breath|dyspnea|difficulty breathing|can't breathe|short of breath/i.test(fullText),
      respiratory: /respiratory|lung|pulmonary|breathing/i.test(fullText),
      asthma: /asthma|wheezing|wheeze/i.test(fullText),
      copd: /copd|emphysema|chronic bronchitis/i.test(fullText),
      hypertension: /hypertension|high blood pressure|htn/i.test(fullText),
      headache: /headache|head pain|migraine/i.test(fullText)
    };

    console.log('[Vitals] Patient context:', patientContext);

    const result = vitalsPanel.measureVital(vitalKey, patientContext);
    if(result){
      S.measuredVitals.push(result);
      el.classList.add('measuring');
      setTimeout(() => {
        el.classList.remove('measuring');
        el.classList.add('measured');
        const vitalsContainer = $('.vitals-panel');
        if(vitalsContainer) vitalsContainer.outerHTML = vitalsUI();
        const chartBody = $('#chart-body');
        if(chartBody) chartBody.innerHTML = chartView();
        toast(`${result.fullName} measured: ${result.value} ${result.unit}`);
      }, 1500);
    }
    return;
  }
  if(action==='finish'){dialog(`<h2>Ready to reflect?</h2><p>Finishing saves this conversation and generates evidence-based observations. You can review the transcript or start a fresh attempt afterward.</p><div class="dialog-actions">${button('Keep practicing','close-dialog','','btn')}${button('Finish & review','confirm-finish',id,'btn-primary','check')}</div>`);return;}
  if(action==='confirm-finish'){el.disabled=true;S.encounter=await api('/encounters/'+id+'/finish','POST',{});$('#confirm-dialog').close();location.hash='report/'+id;return;}
  if(action==='evidence'){evidence(id);return;}
  if(action==='open-artifact'){const eId=S.encounter.id;const response=await fetch('/api/encounters/'+eId+'/artifacts/'+id);if(!response.ok)throw new Error((await response.json()).error);const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=S.encounter.artifacts.find(x=>x.id===id).name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);S.encounter=await api('/encounters/'+eId);$('#chart-body').innerHTML=chartView();return;}
  if(action==='gen-test'){el.disabled=true;const box=$('#gen-check');box.innerHTML='<div class="loading-state"><span class="spinner"></span>Testing Claude models on Bedrock…</div>';
   try{const r=await api('/generator/test','POST',{});box.innerHTML=`<ul class="validation-list">${r.results.map(x=>`<li class="${x.ok?'':'gen-error'}">${x.ok?'Working':'Not available'}: ${esc(x.model)}${x.error?' · '+esc(x.error):''}</li>`).join('')}</ul>`;toast(`Bedrock connected. Using ${r.model}.`);S.genStatus=await api('/generator/status');}
   catch(err){box.innerHTML=`<ul class="validation-list"><li class="gen-error">${esc(err.message)}</li></ul>`;throw err;}
   return;}
  if(action==='gen-example'){el.disabled=true;const r=await api('/generator/example','POST',{});S.genRequest={...r.request,files:[]};await openGeneratedDraft(r,'Static example loaded as a draft. Review it, then approve and publish.');return;}
  if(action==='report-problem'){reportProblem();return;}
  if(action==='dev-lock'){await api('/developer/logout','POST',{});S.developer=false;await route();toast('Developer data locked.');return;}
  if(action==='star'){const [kind,n]=id.split(':');S.stars[kind]=Number(n);$$(`.rating-widget[data-kind="${kind}"] .star`).forEach((b,i)=>{b.classList.toggle('on',i<Number(n));b.setAttribute('aria-checked',i+1===Number(n));});return;}
  if(action==='save-rating'){const saved=(S.encounter.ratings||{})[id];const stars=S.stars[id]??saved?.stars;if(!stars)throw new Error('Choose 1 to 5 stars first.');el.disabled=true;
   S.encounter=await api('/encounters/'+S.encounter.id+'/rating','POST',{kind:id,stars,comment:$('#'+id+'-comment').value,reviewer:$('#reviewer-name')?.value});delete S.stars[id];const y=window.scrollY;main.innerHTML=reportView();window.scrollTo(0,y);toast('Thanks, your rating was saved.');return;}
  if(action==='report-status'){const [rid,status]=id.split(':');await api('/reports/'+rid,'PUT',{status});await route();toast(status==='resolved'?'Report marked resolved.':'Report reopened.');return;}
  if(action==='save-case'||action==='publish-case'){el.disabled=true;await saveCase(action==='publish-case');return;}
  if(action==='delete-case'){dialog(`<h2>Delete patient profile?</h2><p>Delete <strong>${esc(S.editor.name)}</strong> from Patient Studio and the practice library? This cannot be undone. Existing encounters and their records will remain available.</p><div class="dialog-actions">${button('Cancel','close-dialog','','btn')}${button('Delete patient profile','confirm-delete-case',id,'btn-danger','trash')}</div>`);return;}
  if(action==='confirm-delete-case'){
   el.disabled=true;await api('/patients/'+encodeURIComponent(id),'DELETE');
   $('#confirm-dialog').close();S.dirty=false;S.editor=null;S.attachments=[];S.validation=null;
   location.hash='studio';toast('Patient profile deleted.');return;
  }
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
 if(event.target.type==='range'&&event.target.dataset.labels){const labels=JSON.parse(event.target.dataset.labels);$('#'+event.target.id+'-label').textContent=labels[event.target.value-1];const t=$('#gen-temperament')||$('#temperament'),o=$('#gen-openness')||$('#openness');const preview=$('#gen-preview')||$('#difficulty-preview');if(t&&o&&preview)preview.textContent=gradingPreview(Number(t.value),Number(o.value));}
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
  if(form.id==='gen-form'){
   const req=await collectRequest();S.genRequest={...req,files:[]};
   S.genCheck=await api('/generator/check','POST',{request:req});$('#gen-check').innerHTML=genCheckView();
   if(S.genCheck.errors.length)throw new Error('Fix the highlighted items before generating.');
   $('#gen-check').innerHTML='<div class="loading-state"><span class="spinner"></span>Generating the profile, rubric, reports and portrait on Amazon Bedrock. This usually takes 1–2 minutes…</div>';
   try{const r=await api('/generator/generate','POST',{request:req});S.genCheck=null;await openGeneratedDraft(r,'Draft generated. Review it, then approve and publish.');}
   catch(err){$('#gen-check').innerHTML=genCheckView();throw err;}
   return;
  }
  if(form.id==='upload-form'){
   if(S.dirty)throw new Error('Save your case edits before attaching a file.');
   const file=$('#upload-file').files[0];if(!file)throw new Error('Choose a file first.');if(file.size>5*1024*1024)throw new Error('Maximum file size is 5 MB.');
   const content=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file);});
   const data=await api('/patients/'+S.editor.id+'/attachments','POST',{name:file.name,content,kind:$('#upload-kind').value,release:$('#upload-release').value,keywords:$('#upload-keywords').value.split(',').map(x=>x.trim()).filter(Boolean)});
   S.attachments.push(data);main.innerHTML=editorView();toast('File attached. Publish the case to include it in new encounters.');
  }
  if(form.id==='review-form'){
   const ratings=$$('[data-domain]',form).map(el=>{const score=$('[data-key=score]',el).value;return {key:el.dataset.domain,score:score===''?null:score==='N/A'?'N/A':Number(score),review_note:$('[data-key=review_note]',el).value,evidence_ids:$('[data-key=evidence_ids]',el).value.split(',').map(x=>x.trim()).filter(Boolean)};});
   const summary={comments:$('#summary-comments').value,strengths:splitLines($('#summary-strengths').value),improvements:splitLines($('#summary-improvements').value),next_steps:splitLines($('#summary-next').value)};
   const reviewer=$('#reviewer-name').value,id=S.encounter.id,release=event.submitter?.dataset.release==='1';
   S.encounter=await api('/encounters/'+id+'/review','POST',{ratings,reviewer,summary,review_version:S.encounter.feedback.review_version});main.innerHTML=reportView();
   if(release){S.encounter=await api('/encounters/'+id+'/release','POST',{reviewer,review_version:S.encounter.feedback.review_version});main.innerHTML=reportView();toast('Score and feedback released to the student.');}
   else toast('Review saved. The student will not see it until you release it.');
  }
 }catch(err){toast(err.message,true);}finally{if(submit?.isConnected)submit.disabled=false;}
});
window.addEventListener('hashchange',route);
window.addEventListener('beforeunload',event=>{if(S.dirty){event.preventDefault();event.returnValue='';}});
async function boot(){try{const session=await api('/session');S.role=session.role;S.developer=!!session.developer;S.rubric=await api('/rubric');await route();}catch(err){main.innerHTML=notice('Cannot reach the local backend. Start it with <code>python3 run.py</code> and open <code>http://127.0.0.1:8000</code>. '+esc(err.message),'error');}}
boot();
