/* Dependency-free render checks. Optional: node tests/test_frontend.cjs
 * These check HTML generation and escaping, not browser layout or interactions.
 */
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const py=process.env.PYTHON || (process.platform==='win32'?'python':'python3');
const fixture=JSON.parse(execFileSync(py,['-c',`
import json
from backend.seed import seed_profiles
import copy
from backend.server import RUBRIC,brief,public_encounter,student_feedback
from backend.engine import assess,reply,apply_review,release_feedback
p=seed_profiles()[4]
e={'id':'test','profile':p,'status':'completed','started_at':'2026-10-10T12:00:00Z','ended_at':'2026-10-10T12:05:00Z','messages':[{'id':'t0','role':'patient','text':'Hello.','timestamp':'2026-10-10T12:00:00Z','kind':'opening','fact_ids':[]},{'id':'t1','role':'student','text':'What are your cholesterol results?','timestamp':'2026-10-10T12:01:00Z'},{'id':'t2','role':'patient','text':reply(p,'What are your cholesterol results?')['text'],'fact_ids':reply(p,'What are your cholesterol results?')['fact_ids'],'reply_to':'t1','kind':'profile','timestamp':'2026-10-10T12:01:00Z'}],'events':[],'disclosed':['f1','f3'],'attachments':[],'released_artifacts':[]}
e['feedback']=assess(e,RUBRIC)
r=copy.deepcopy(e)
r['feedback']=release_feedback(apply_review(r['feedback'],[{'key':d['key'],'score':3,'review_note':'Clear and respectful throughout.','evidence_ids':['t1']} for d in r['feedback']['domains']],{'t0','t1','t2'},'Dr Test',{'comments':'Nice work <b>today</b>.','strengths':['Asked about labs'],'improvements':[],'next_steps':['Use teach-back']}),'Dr Test')
r['released_feedback']=student_feedback(r['feedback'])
print(json.dumps({'profiles':seed_profiles(),'patients':[{**brief(p),'has_published_version':True,'published_card':brief(p)} for p in seed_profiles()],'rubric':RUBRIC,'encounter':public_encounter(e,'faculty'),'student_pending':public_encounter(e,'student'),'student_released':public_encounter(r,'student')}))
`],{cwd:root,encoding:'utf8'}));
const node={innerHTML:'',addEventListener(){},classList:{},hidden:false};
const vitalsPanel=vm.runInNewContext(fs.readFileSync(path.join(root,'frontend/components/VitalsPanel.js'),'utf8').replace(/^export /gm,'')+'\nvitalsPanel;', {console});
const emotionDetector={getAvatarReaction:()=>({emotion:'neutral',mood:'neutral',detected:false})};
const avatarMocks={vitalsPanel,emotionDetector,Avatar3D:class{speak(){}stop(){}destroy(){}},ttsService:{isAvailable:()=>false,speak:async()=>{}},voiceInput:{isAvailable:()=>false,startListening(){},stopListening(){}}};
avatarMocks.voiceRecorder={isAvailable:()=>false,cancel(){},active:false};
const context=vm.createContext({...avatarMocks,fixture,document:{querySelector:()=>node,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},location:{hash:'#cases'},setInterval(){},setTimeout(){},clearTimeout(){},console,structuredClone,Date,Set,JSON,URLSearchParams});
const source=fs.readFileSync(path.join(root,'frontend/app.js'),'utf8').replace(/^import .*;\s*$/gm,'').replace(/\nboot\(\);\s*$/,'');
vm.runInContext(source,context);
vm.runInContext("S.user={id:'faculty-1',name:'Test Faculty',email:'faculty@example.test',role:'faculty'};S.patients=fixture.patients;S.rubric=fixture.rubric;S.encounter=fixture.encounter;",context);
const run=code=>vm.runInContext(code,context);
require('./test_voice_recorder.cjs');
let count=0;
function check(name,fn){fn();count++;console.log('PASS',name);}
check('Eight patient cards render',()=>assert.equal((run('patientCards()').match(/class="patient-card"/g)||[]).length,8));
check('Library contains patient actions',()=>assert.ok(run('casesView()').includes('data-action="start"')));
check('Studio table renders with generation timestamps and AI generation before Create patient',()=>{
 run("S.patients=[{...fixture.patients[0],generated_at:'2026-10-10T18:45:26Z'},...fixture.patients.slice(1)];");
 const html=run('studioView()');
 assert.ok(html.includes('Omar Sinclair'));
 assert.ok(html.includes('data-action="navigate" data-id="generate"'));
 assert.ok(html.indexOf('Generate patient with AI')<html.indexOf('Create patient'));
 assert.ok(html.includes('<th>GENERATED AT</th>'));
 assert.ok(html.includes('datetime="2026-10-10T18:45:26.000Z"'));
 assert.ok(html.includes('2026'));
 assert.ok(!html.includes('Invalid Date'));
 assert.ok(html.includes('<span class="muted">—</span>'));
 run('S.patients=fixture.patients;');
});
check('New patient editor renders without a delete action',()=>{run("S.editor=newProfile();S.attachments=[];S.validation=null;");const html=run('editorView()');assert.ok(html.includes('Approve &amp; publish'));assert.ok(!html.includes('data-action="delete-case"'));});
check('Existing patient editor renders delete before Back to cases',()=>{run('S.editor=fixture.profiles[4];');const html=run('editorView()');assert.ok(html.includes('Lipid values'));assert.ok(html.includes('data-action="delete-case"'));assert.ok(html.indexOf('Delete patient profile')<html.indexOf('Back to cases'));});
check('Approval storage status distinguishes local, configured, incomplete, and saved',()=>{run("S.storageStatus={enabled:false};");assert.ok(run('editorView()').includes('AWS storage is off'));run("S.storageStatus={enabled:true,configured:false};");assert.ok(run('editorView()').includes('Approval is blocked'));run("S.storageStatus={enabled:true,configured:true};S.editor={...fixture.profiles[4],status:'draft'};");assert.ok(run('editorView()').includes('Approval will save'));assert.ok(!run('editorView()').includes('No uploads are sent to an external service'));run("S.editor={...fixture.profiles[4],status:'published',cloud_storage:{version:fixture.profiles[4].version,file_count:2}};");assert.ok(run('editorView()').includes('Saved to AWS'));run('S.storageStatus=null;S.editor=fixture.profiles[4];');});
check('Avatar encounter and medical record render',()=>{run("S.encounter={...fixture.encounter,status:'active'};");const html=run('encounterView()');assert.ok(html.includes('Medical record'));assert.ok(html.includes('avatar-container'));assert.ok(html.includes('id="chat-form"'));assert.ok(html.includes('vitals-panel'));run('S.encounter=fixture.encounter;');});
check('Student feedback contains no rating editor',()=>{run("S.role='student';");assert.ok(!run('reportView()').includes('class="rating-editor"'));});
check('Faculty feedback renders seven rating editors',()=>{run("S.role='faculty';");assert.equal((run('reportView()').match(/class="rating-editor"/g)||[]).length,7);});
check('Faculty sees auto-suggested score and pre-filled ratings',()=>{run("S.role='faculty';S.encounter=fixture.encounter;");const html=run('reportView()');assert.ok(html.includes('Auto-suggested score'));assert.ok(html.includes('scoring criteria met'));assert.ok(html.includes('Save &amp; release to student'));const d=fixture.encounter.feedback.domains[0];assert.ok(html.includes(`<option value="${d.suggested_score}" selected>`));});
check('Student sees no score before release',()=>{run("S.role='student';S.encounter=fixture.student_pending;");const html=run('reportView()');assert.ok(html.includes('Submitted for faculty review'));assert.ok(!html.includes('score-number'));assert.ok(!html.includes('Suggested'));});
check('Student sees released score and faculty feedback',()=>{run("S.role='student';S.encounter=fixture.student_released;");const html=run('reportView()');assert.ok(html.includes('YOUR SCORE'));assert.ok(html.includes('Clear and respectful throughout.'));assert.ok(html.includes('Nice work &lt;b&gt;today&lt;/b&gt;.'));assert.ok(!html.includes('class="rating-editor"'));run("S.role='faculty';S.encounter=fixture.encounter;");});
check('Faculty-only navigation includes patient generation and student metrics',()=>{const navHtml=role=>run(`(()=>{const q=document.querySelector,nav={innerHTML:''};document.querySelector=s=>s==='#navigation'?nav:{innerHTML:'',textContent:''};S.role='${role}';S.route='cases';navigation();document.querySelector=q;return nav.innerHTML;})()`);assert.ok(navHtml('faculty').includes('Generate patients'));assert.ok(navHtml('faculty').includes('Student metrics'));assert.ok(!navHtml('student').includes('Generate patients'));assert.ok(!navHtml('student').includes('Student metrics'));run("S.role='faculty';");});
check('Student metrics keeps empty folders and orders charts newest first',()=>{
 const students=[{id:'student-1',name:'Student One',encounters:[
  {id:'new',patient_name:'Recent case',started_at:'2026-10-11T12:00:00Z',released:true,status:'reviewed',total:21,available_points:28,domains:[{name:'Communication',score:3}]},
  {id:'old',patient_name:'Earlier case',started_at:'2026-10-10T12:00:00Z',released:false,status:'awaiting_release',total:null,available_points:0,domains:[{name:'Communication',score:null,suggested_score:2}]}
 ]},{id:'student-2',name:'Student Two',encounters:[]}];
 run(`S.metricFixture=${JSON.stringify(students)};`);
 const index=run('studentMetricsView(S.metricFixture)');
 assert.ok(index.includes('Student One'));assert.ok(index.includes('Student Two'));assert.ok(index.includes('No scored encounters'));
 const folder=run('studentMetricsFolderView(S.metricFixture[0])');
 assert.ok(folder.indexOf('Recent case')<folder.indexOf('Earlier case'));
 assert.equal((folder.match(/class="panel score-histogram"/g)||[]).length,2);
 run('delete S.metricFixture;');
});
check('Generator page renders brief form and static example',()=>{run("S.genStatus={live_available:false,reason:'No key',model:'m',region:'r'};S.genBrief=null;S.genCheck=null;");const html=run('generatorView()');assert.ok(html.includes('id="gen-form"'));assert.ok(html.includes('Load static example'));assert.ok(html.includes('Live AI off'));assert.ok(/type="submit" disabled/.test(html));});
check('Conversation quality panel renders for faculty and after release',()=>{run("S.role='faculty';S.encounter=fixture.encounter;");assert.ok(run('reportView()').includes('Conversation quality'));run("S.role='student';S.encounter=fixture.student_released;");assert.ok(run('reportView()').includes('Conversation quality'));run("S.encounter=fixture.student_pending;");assert.ok(!run('reportView()').includes('Conversation quality'));run("S.role='faculty';S.encounter=fixture.encounter;");});
check('Empty encounter asks the student to start',()=>{run("S.encounter={...fixture.encounter,messages:[]};");assert.ok(run('messagesView()').includes('You start the conversation'));run("S.encounter=fixture.encounter;");});
check('Report a problem button is on every screen for both roles',()=>{for(const role of ['student','faculty']){const html=run(`(()=>{const q=document.querySelector,slot={innerHTML:''};document.querySelector=s=>s==='#report-slot'?slot:{innerHTML:'',textContent:''};S.role='${role}';S.route='cases';navigation();document.querySelector=q;return slot.innerHTML;})()`);assert.ok(html.includes('data-action="report-problem"'));}run("S.role='faculty';");});
check('Students can rate the conversation; faculty rate the automatic score',()=>{run("S.role='student';S.encounter=fixture.student_pending;");assert.ok(run('reportView()').includes('How realistic and useful was this conversation?'));run("S.role='faculty';S.encounter=fixture.encounter;");const html=run('reportView()');assert.ok(html.includes('How accurate was this automatic score?'));assert.ok(html.includes("Student's rating of the conversation"));});
check('Feedback page renders reports and ratings',()=>{const html=run(`feedbackView([{id:'r1',category_label:'Other',message:'<b>x</b>',role:'student',context:{route:'cases'},status:'open',created_at:'2026-10-10T12:00:00Z'}],{conversation:{average:4.5,count:2,recent_comments:[]},auto_score:{average:null,count:0,recent_comments:[]},by_patient:[{patient:'Omar Sinclair',average:4.5,count:2}]})`);assert.ok(html.includes('4.5 ★'));assert.ok(html.includes('&lt;b&gt;x&lt;/b&gt;'));assert.ok(html.includes('Mark resolved'));});
check('Developer tab is faculty-only and locked by default',()=>{for(const role of ['student','faculty']){const html=run(`(()=>{const q=document.querySelector,nav={innerHTML:''};document.querySelector=s=>s==='#navigation'?nav:{innerHTML:'',textContent:''};S.role='${role}';S.route='cases';navigation();document.querySelector=q;return nav.innerHTML;})()`);assert.equal(html.includes('Developer'),role==='faculty');}run("S.role='faculty';");assert.ok(run('developerLoginView()').includes('id="dev-login"'));});
check('Developer data view renders tables, counts and exports',()=>{const html=run(`developerView({generated_at:'2026-10-10T12:00:00Z',ratings:[{encounter_id:'e1',patient:'Omar Sinclair',kind:'student',stars:4,comment:'<i>ok</i>',at:'2026-10-10T12:00:00Z',by:'',auto_total:18,final_total:null,released:false,turns:6}],reports:[],summary:{conversation:{count:1,average:4,distribution:{'1':0,'2':0,'3':0,'4':1,'5':0}},auto_score:{count:0,average:null,distribution:{'1':0,'2':0,'3':0,'4':0,'5':0}},reports_by_category:{},reports_by_status:{},reports_by_role:{},encounters:3}})`);assert.ok(html.includes('ratings.csv'));assert.ok(html.includes('&lt;i&gt;ok&lt;/i&gt;'));assert.ok(html.includes('4.00 ★'));assert.ok(html.includes('No reports yet.'));});
check('Official rubric renders all seven domains',()=>assert.equal((run('rubricView()').match(/class="rubric-domain"/g)||[]).length,7));
check('All-N/A review is not shown as awaiting ratings',()=>{run("S.encounter.feedback.unrated_domains=0;S.encounter.feedback.na_domains=7;");assert.ok(run('reportView()').includes('No applicable rated domains'));});
check('Untrusted strings are HTML escaped',()=>{assert.equal(run(`esc('<img src=x onerror="attack()">')`),'&lt;img src=x onerror=&quot;attack()&quot;&gt;');});
check('Search filters patient cards',()=>{run("S.query='Nisha';");assert.equal((run('patientCards()').match(/class="patient-card"/g)||[]).length,1);});

check('Signup offers name, email/password and both roles with Google',()=>{
 run('S.googleAvailable=true;');const html=run('authView(true)');
 for(const text of ['auth-name','type="email"','type="password"','value="medical-student"','value="faculty"','Continue with Google'])assert.ok(html.includes(text));
 assert.ok(!run('authView(false)').includes('auth-role'));
});
check('Account circle and sidebar show escaped name, role and logout',()=>{
 const result=run(`(()=>{const q=document.querySelector,top={innerHTML:''},side={innerHTML:''};document.querySelector=s=>s==='#account-slot'?top:s==='#sidebar-account'?side:null;S.user={name:'Dr <Test>',email:'test@example.test'};S.role='faculty';accountControls();document.querySelector=q;return [top.innerHTML,side.innerHTML];})()`);
 for(const html of result){assert.ok(html.includes('Dr &lt;Test&gt;'));assert.ok(html.includes('Faculty'));assert.ok(html.includes('data-action="logout"'));}
 assert.ok(result[0].includes('aria-expanded="false"'));assert.ok(result[0].includes('id="account-menu"'));assert.ok(result[0].includes('hidden'));
});
check('Anonymous users have no workspace navigation or report button',()=>{
 const result=run(`(()=>{const q=document.querySelector,nav={innerHTML:''},report={innerHTML:''};document.querySelector=s=>s==='#navigation'?nav:s==='#report-slot'?report:{innerHTML:'',textContent:''};S.user=null;navigation();document.querySelector=q;return [nav.innerHTML,report.innerHTML];})()`);
 assert.equal(result[0],'');assert.equal(result[1],'');
 run("S.user={id:'faculty-1',name:'Test Faculty',email:'faculty@example.test'};");
});

check('Optional audio feedback stays separate from the rubric and escapes evidence',()=>{
 run(`S.speechMayDelete=true;S.speech=[{id:'clip',turn_id:'t1',status:'ready',audio_available:true,audio_deleted:false,expires_at:4102444800,measurements:{duration_seconds:6,estimated_words_per_minute:144,quiet_gaps:[{start_seconds:2.5,duration_seconds:1}],patient_playback_overlap_seconds:0,word_count:12,speech_span_seconds:5,peak_dbfs:-12,clipped_sample_percent:0,observations:['<img src=x onerror=alert(1)>'],limitations:'Approximate measurements only.'}}];`);
 let html=run('speechPanel()');assert.ok(html.includes('144 words/min'));assert.ok(html.includes('preload="none"'));
 assert.ok(html.includes('/api/encounters/test/speech/clip/audio'));assert.ok(html.includes('data-action="delete-speech"'));
 assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('<img src=x'));
 run("S.role='student';S.encounter=fixture.student_pending;");
 html=run('reportView()');assert.ok(html.includes('Speech delivery coaching'));assert.ok(html.includes('Submitted for faculty review'));
 assert.ok(!html.includes('score-number'));assert.ok(!html.includes('data-key="score"'));
 run("S.speechMayDelete=false;");assert.ok(!run('speechPanel()').includes('data-action="delete-speech"'));
 run("S.speech=[];S.role='faculty';S.encounter=fixture.encounter;");
});
check('Recording requires a separate unchecked opt-in',()=>{
 avatarMocks.voiceInput.isAvailable=()=>true;avatarMocks.voiceRecorder.isAvailable=()=>true;
 run("S.speechMayDelete=true;S.speechOptIn=false;");
 const html=run('inputModeUI()');assert.ok(html.includes('id="speech-consent"'));
 assert.ok(!/id="speech-consent"[^>]*checked/.test(html));assert.ok(html.includes('7 days'));
 avatarMocks.voiceInput.isAvailable=()=>false;avatarMocks.voiceRecorder.isAvailable=()=>false;
});
console.log(`${count} frontend render checks passed.`);

(async()=>{
 const requests=[],nodes=new Map();
 const get=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',hidden:true,style:{},close(){},setAttribute(){},addEventListener(){}});return nodes.get(s);};
 let session={authenticated:true,user:{id:'s1',name:'Student',email:'s@example.test',role:'medical-student'},role:'student',csrf_token:'csrf-before',google_available:true};
 const sandbox=vm.createContext({...avatarMocks,document:{querySelector:get,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},location:{hash:'#generate'},
  history:{replaceState(_a,_b,hash){sandbox.location.hash=hash;}},setInterval(){},setTimeout(){},clearTimeout(){},console,structuredClone,Date,Set,JSON,URLSearchParams,
  fetch:async(url,options)=>{requests.push({url,options});if(url.endsWith('/logout'))session={authenticated:false,user:null,csrf_token:'csrf-after'};return {ok:true,json:async()=>session};}
 });
 vm.runInContext(source,sandbox);vm.runInContext('applySession('+JSON.stringify(session)+');',sandbox);
 await vm.runInContext('route()',sandbox);
 assert.equal(requests.length,0);assert.ok(get('#main').innerHTML.includes('requires a faculty account'));
 console.log('PASS Direct student navigation to faculty pages makes no protected request');
 vm.runInContext("S.encounter={};S.patients=[{}];S.editor={};S.genBrief='private draft';S.dirty=false;S.measuredVitals=[{value:80}];vitalsPanel.vitals.heartRate.measured=true;vitalsPanel.vitals.heartRate.value=80;",sandbox);
 await vm.runInContext('logout()',sandbox);
 assert.equal(requests[0].url,'/api/auth/logout');assert.equal(requests[0].options.headers['X-CSRF-Token'],'csrf-before');
 assert.equal(vm.runInContext('S.user',sandbox),null);assert.equal(vm.runInContext('S.encounter',sandbox),null);
 assert.equal(vm.runInContext('S.editor',sandbox),null);assert.equal(vm.runInContext('S.genBrief',sandbox),null);
 assert.equal(vm.runInContext('S.patients.length',sandbox),0);assert.equal(vm.runInContext('S.measuredVitals.length',sandbox),0);assert.equal(vm.runInContext('vitalsPanel.vitals.heartRate.measured',sandbox),false);assert.equal(vm.runInContext('vitalsPanel.vitals.heartRate.value',sandbox),null);assert.equal(vm.runInContext('S.csrf',sandbox),'csrf-after');
 assert.ok(get('#main').innerHTML.includes('Welcome back'));
 await vm.runInContext('route()',sandbox);assert.ok(get('#main').innerHTML.includes('Welcome back'));
 console.log('PASS Logout sends CSRF token, clears account data, and keeps subsequent routes signed out');
})().catch(error=>{console.error(error);process.exitCode=1;});

// Exercise the approval request sequence, including a failed cloud save and retry.
(async()=>{
 let release;
 const pending=new Promise(resolve=>release=resolve);
 const sandbox=vm.createContext({...avatarMocks,document:{querySelector:()=>node,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},location:{hash:'#cases'},setInterval(){},setTimeout(){},clearTimeout(){},console,structuredClone,Date,Set,JSON,URLSearchParams,
  fetch:async()=>{await pending;return {ok:false,status:401,json:async()=>({error:'Old session expired'})};}
 });
 vm.runInContext(source,sandbox);vm.runInContext("S.user={id:'old-faculty'};S.csrf='old-session';",sandbox);
 const request=vm.runInContext("api('/patients')",sandbox);
 vm.runInContext("S.user={id:'new-student'};S.csrf='new-session';S.role='student';",sandbox);
 release();await assert.rejects(request,/account changed/);
 assert.equal(vm.runInContext('S.user.id',sandbox),'new-student');assert.equal(vm.runInContext('S.role',sandbox),'student');
 console.log('PASS A stale request cannot restore old account data or log out the new account');
})().catch(error=>{console.error(error);process.exitCode=1;});

(async()=>{
 const requests=[];
 let fail=true;
 let pending=null;
 const stateNode={innerHTML:'',textContent:'',hidden:false,isConnected:true,addEventListener(){},querySelectorAll:()=>[],classList:{}};
 const sandbox=vm.createContext({...avatarMocks,fixture,
  document:{querySelector:s=>s==='#case-form'?null:s==='#approve-case'?{checked:true}:stateNode,querySelectorAll:()=>[],addEventListener(){}},
  window:{addEventListener(){}},location:{hash:'#studio/patient'},history:{replaceState(){}},
  setInterval(){},setTimeout(){},clearTimeout(){},console,structuredClone,Date,Set,JSON,URLSearchParams,
  fetch:async(url,options)=>{
   const body=JSON.parse(options.body);requests.push({url,method:options.method,body});
   if(options.method==='PUT')return {ok:true,json:async()=>({profile:{...body.profile,version:1,status:'draft'},attachments:[],validation:null})};
   if(pending)await pending;
   if(fail)return {ok:false,json:async()=>({error:'Approval could not finish. Your draft is preserved.'})};
   return {ok:true,json:async()=>({profile:{...fixture.profiles[4],id:'patient',version:2,status:'published',cloud_storage:{version:2,file_count:0}},attachments:[],validation:null,storage:{enabled:true,configured:true}})};
  }
 });
 vm.runInContext(source,sandbox);
 vm.runInContext("S.editor={...fixture.profiles[4],id:'patient',version:0,status:'draft'};S.attachments=[];S.validation=null;S.dirty=true;S.storageStatus={enabled:true,configured:true};",sandbox);
 await assert.rejects(vm.runInContext('saveCase(true)',sandbox),/draft is preserved/);
 assert.deepEqual(requests.map(r=>r.method),['PUT','POST']);
 assert.equal(vm.runInContext('S.editor.version',sandbox),1);
 assert.equal(vm.runInContext('S.dirty',sandbox),false);
 assert.ok(stateNode.innerHTML.includes('Working draft'));
 console.log('PASS Failed cloud approval keeps the saved draft visible');
 fail=false;
 await vm.runInContext('saveCase(true)',sandbox);
 assert.deepEqual(requests.map(r=>r.method),['PUT','POST','POST']);
 assert.equal(requests[2].body.draft_version,1);
 assert.equal(vm.runInContext('S.editor.version',sandbox),2);
 console.log('PASS Retrying approval reuses the saved draft version');
 let release;
 pending=new Promise(resolve=>release=resolve);
 const approval=vm.runInContext('saveCase(true)',sandbox);
 vm.runInContext("S.epoch++;S.editor={...fixture.profiles[4],id:'another-patient'};S.route='studio/another-patient';",sandbox);
 stateNode.innerHTML='another editor';
 release();await approval;
 assert.equal(vm.runInContext('S.editor.id',sandbox),'another-patient');
 assert.equal(stateNode.innerHTML,'another editor');
 console.log('PASS A slow approval preserves navigation to another patient');
})().catch(error=>{console.error(error);process.exitCode=1;});
