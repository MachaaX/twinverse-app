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
const avatarMocks={Avatar3D:class{speak(){}stop(){}destroy(){}},ttsService:{isAvailable:()=>false,speak:async()=>{}},voiceInput:{isAvailable:()=>false}};
const context=vm.createContext({...avatarMocks,fixture,document:{querySelector:()=>node,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},location:{hash:'#cases'},setInterval(){},setTimeout(){},clearTimeout(){},console,structuredClone,Date,Set,JSON});
const source=fs.readFileSync(path.join(root,'frontend/app.js'),'utf8').replace(/^import .*;\s*$/gm,'').replace(/\nboot\(\);\s*$/,'');
vm.runInContext(source,context);
vm.runInContext('S.patients=fixture.patients;S.rubric=fixture.rubric;S.encounter=fixture.encounter;',context);
const run=code=>vm.runInContext(code,context);
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
check('Avatar encounter and medical record render',()=>{run("S.encounter={...fixture.encounter,status:'active'};");const html=run('encounterView()');assert.ok(html.includes('Medical record'));assert.ok(html.includes('avatar-container'));assert.ok(html.includes('id="chat-form"'));run('S.encounter=fixture.encounter;');});
check('Student feedback contains no rating editor',()=>{run("S.role='student';");assert.ok(!run('reportView()').includes('class="rating-editor"'));});
check('Faculty feedback renders seven rating editors',()=>{run("S.role='faculty';");assert.equal((run('reportView()').match(/class="rating-editor"/g)||[]).length,7);});
check('Faculty sees auto-suggested score and pre-filled ratings',()=>{run("S.role='faculty';S.encounter=fixture.encounter;");const html=run('reportView()');assert.ok(html.includes('Auto-suggested score'));assert.ok(html.includes('scoring criteria met'));assert.ok(html.includes('Save &amp; release to student'));const d=fixture.encounter.feedback.domains[0];assert.ok(html.includes(`<option value="${d.suggested_score}" selected>`));});
check('Student sees no score before release',()=>{run("S.role='student';S.encounter=fixture.student_pending;");const html=run('reportView()');assert.ok(html.includes('Submitted for faculty review'));assert.ok(!html.includes('score-number'));assert.ok(!html.includes('Suggested'));});
check('Student sees released score and faculty feedback',()=>{run("S.role='student';S.encounter=fixture.student_released;");const html=run('reportView()');assert.ok(html.includes('YOUR SCORE'));assert.ok(html.includes('Clear and respectful throughout.'));assert.ok(html.includes('Nice work &lt;b&gt;today&lt;/b&gt;.'));assert.ok(!html.includes('class="rating-editor"'));run("S.role='faculty';S.encounter=fixture.encounter;");});
check('Generate patients tab is faculty-only',()=>{const navHtml=role=>run(`(()=>{const q=document.querySelector,nav={innerHTML:''};document.querySelector=s=>s==='#navigation'?nav:{innerHTML:'',textContent:''};S.role='${role}';S.route='cases';navigation();document.querySelector=q;return nav.innerHTML;})()`);assert.ok(navHtml('faculty').includes('Generate patients'));assert.ok(!navHtml('student').includes('Generate patients'));run("S.role='faculty';");});
check('Generator page renders brief form and static example',()=>{run("S.genStatus={live_available:false,reason:'No key',model:'m',region:'r'};S.genBrief=null;S.genCheck=null;");const html=run('generatorView()');assert.ok(html.includes('id="gen-form"'));assert.ok(html.includes('Load static example'));assert.ok(html.includes('Live AI off'));assert.ok(/type="submit" disabled/.test(html));});
check('Conversation quality panel renders for faculty and after release',()=>{run("S.role='faculty';S.encounter=fixture.encounter;");assert.ok(run('reportView()').includes('Conversation quality'));run("S.role='student';S.encounter=fixture.student_released;");assert.ok(run('reportView()').includes('Conversation quality'));run("S.encounter=fixture.student_pending;");assert.ok(!run('reportView()').includes('Conversation quality'));run("S.role='faculty';S.encounter=fixture.encounter;");});
check('Empty encounter asks the student to start',()=>{run("S.encounter={...fixture.encounter,messages:[]};");assert.ok(run('messagesView()').includes('You start the conversation'));run("S.encounter=fixture.encounter;");});
check('Report a problem button is on every screen for both roles',()=>{for(const role of ['student','faculty']){const html=run(`(()=>{const q=document.querySelector,slot={innerHTML:''};document.querySelector=s=>s==='#report-slot'?slot:{innerHTML:'',textContent:''};S.role='${role}';S.route='cases';navigation();document.querySelector=q;return slot.innerHTML;})()`);assert.ok(html.includes('data-action="report-problem"'));}run("S.role='faculty';");});
check('Students can rate the conversation; faculty rate the automatic score',()=>{run("S.role='student';S.encounter=fixture.student_pending;");assert.ok(run('reportView()').includes('How realistic and useful was this conversation?'));run("S.role='faculty';S.encounter=fixture.encounter;");const html=run('reportView()');assert.ok(html.includes('How accurate was this automatic score?'));assert.ok(html.includes("Student's rating of the conversation"));});
check('Feedback page renders reports and ratings',()=>{const html=run(`feedbackView([{id:'r1',category_label:'Other',message:'<b>x</b>',role:'student',context:{route:'cases'},status:'open',created_at:'2026-10-10T12:00:00Z'}],{conversation:{average:4.5,count:2,recent_comments:[]},auto_score:{average:null,count:0,recent_comments:[]},by_patient:[{patient:'Omar Sinclair',average:4.5,count:2}]})`);assert.ok(html.includes('4.5 ★'));assert.ok(html.includes('&lt;b&gt;x&lt;/b&gt;'));assert.ok(html.includes('Mark resolved'));});
check('Developer tab is shown to both roles and locked by default',()=>{for(const role of ['student','faculty']){const html=run(`(()=>{const q=document.querySelector,nav={innerHTML:''};document.querySelector=s=>s==='#navigation'?nav:{innerHTML:'',textContent:''};S.role='${role}';S.route='cases';navigation();document.querySelector=q;return nav.innerHTML;})()`);assert.ok(html.includes('Developer'));}run("S.role='faculty';");assert.ok(run('developerLoginView()').includes('id="dev-login"'));});
check('Developer data view renders tables, counts and exports',()=>{const html=run(`developerView({generated_at:'2026-10-10T12:00:00Z',ratings:[{encounter_id:'e1',patient:'Omar Sinclair',kind:'student',stars:4,comment:'<i>ok</i>',at:'2026-10-10T12:00:00Z',by:'',auto_total:18,final_total:null,released:false,turns:6}],reports:[],summary:{conversation:{count:1,average:4,distribution:{'1':0,'2':0,'3':0,'4':1,'5':0}},auto_score:{count:0,average:null,distribution:{'1':0,'2':0,'3':0,'4':0,'5':0}},reports_by_category:{},reports_by_status:{},reports_by_role:{},encounters:3}})`);assert.ok(html.includes('ratings.csv'));assert.ok(html.includes('&lt;i&gt;ok&lt;/i&gt;'));assert.ok(html.includes('4.00 ★'));assert.ok(html.includes('No reports yet.'));});
check('Official rubric renders all seven domains',()=>assert.equal((run('rubricView()').match(/class="rubric-domain"/g)||[]).length,7));
check('All-N/A review is not shown as awaiting ratings',()=>{run("S.encounter.feedback.unrated_domains=0;S.encounter.feedback.na_domains=7;");assert.ok(run('reportView()').includes('No applicable rated domains'));});
check('Untrusted strings are HTML escaped',()=>{assert.equal(run(`esc('<img src=x onerror="attack()">')`),'&lt;img src=x onerror=&quot;attack()&quot;&gt;');});
check('Search filters patient cards',()=>{run("S.query='Nisha';");assert.equal((run('patientCards()').match(/class="patient-card"/g)||[]).length,1);});
console.log(`${count} frontend render checks passed.`);

// Exercise the approval request sequence, including a failed cloud save and retry.
(async()=>{
 const requests=[];
 let fail=true;
 let pending=null;
 const stateNode={innerHTML:'',textContent:'',hidden:false,isConnected:true,addEventListener(){},querySelectorAll:()=>[],classList:{}};
 const sandbox=vm.createContext({...avatarMocks,fixture,
  document:{querySelector:s=>s==='#case-form'?null:s==='#approve-case'?{checked:true}:stateNode,querySelectorAll:()=>[],addEventListener(){}},
  window:{addEventListener(){}},location:{hash:'#studio/patient'},history:{replaceState(){}},
  setInterval(){},setTimeout(){},clearTimeout(){},console,structuredClone,Date,Set,JSON,
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
