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
from backend.server import RUBRIC,brief,public_encounter
from backend.engine import assess,reply
p=seed_profiles()[4]
e={'id':'test','profile':p,'status':'completed','started_at':'2026-10-10T12:00:00Z','ended_at':'2026-10-10T12:05:00Z','messages':[{'id':'t0','role':'patient','text':'Hello.','timestamp':'2026-10-10T12:00:00Z','kind':'opening','fact_ids':[]},{'id':'t1','role':'student','text':'What are your cholesterol results?','timestamp':'2026-10-10T12:01:00Z'},{'id':'t2','role':'patient','text':reply(p,'What are your cholesterol results?')['text'],'fact_ids':reply(p,'What are your cholesterol results?')['fact_ids'],'reply_to':'t1','kind':'profile','timestamp':'2026-10-10T12:01:00Z'}],'events':[],'disclosed':['f1','f3'],'attachments':[],'released_artifacts':[]}
e['feedback']=assess(e,RUBRIC)
print(json.dumps({'profiles':seed_profiles(),'patients':[{**brief(p),'has_published_version':True,'published_card':brief(p)} for p in seed_profiles()],'rubric':RUBRIC,'encounter':public_encounter(e)}))
`],{cwd:root,encoding:'utf8'}));
const node={innerHTML:'',addEventListener(){},classList:{},hidden:false};
const context=vm.createContext({fixture,document:{querySelector:()=>node,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},location:{hash:'#cases'},setInterval(){},setTimeout(){},clearTimeout(){},console,structuredClone,Date,Set,JSON});
const source=fs.readFileSync(path.join(root,'frontend/app.js'),'utf8').replace(/\nboot\(\);\s*$/,'');
vm.runInContext(source,context);
vm.runInContext('S.patients=fixture.patients;S.rubric=fixture.rubric;S.encounter=fixture.encounter;',context);
const run=code=>vm.runInContext(code,context);
let count=0;
function check(name,fn){fn();count++;console.log('PASS',name);}
check('Eight patient cards render',()=>assert.equal((run('patientCards()').match(/class="patient-card"/g)||[]).length,8));
check('Library contains patient actions',()=>assert.ok(run('casesView()').includes('data-action="start"')));
check('Studio table renders',()=>assert.ok(run('studioView()').includes('Omar Sinclair')));
check('New patient editor renders',()=>{run("S.editor=newProfile();S.attachments=[];S.validation=null;");assert.ok(run('editorView()').includes('Approve &amp; publish'));});
check('Existing patient editor renders facts',()=>{run('S.editor=fixture.profiles[4];');assert.ok(run('editorView()').includes('Lipid values'));});
check('Split-screen encounter renders',()=>{const html=run('encounterView()');assert.ok(html.includes('Medical record'));assert.ok(html.includes('patient-banner'));});
check('Student feedback contains no rating editor',()=>{run("S.role='student';");assert.ok(!run('reportView()').includes('class="rating-editor"'));});
check('Faculty feedback renders seven rating editors',()=>{run("S.role='faculty';");assert.equal((run('reportView()').match(/class="rating-editor"/g)||[]).length,7);});
check('Official rubric renders all seven domains',()=>assert.equal((run('rubricView()').match(/class="rubric-domain"/g)||[]).length,7));
check('All-N/A review is not shown as awaiting ratings',()=>{run("S.encounter.feedback.unrated_domains=0;S.encounter.feedback.na_domains=7;");assert.ok(run('reportView()').includes('No applicable rated domains'));});
check('Untrusted strings are HTML escaped',()=>{assert.equal(run(`esc('<img src=x onerror="attack()">')`),'&lt;img src=x onerror=&quot;attack()&quot;&gt;');});
check('Search filters patient cards',()=>{run("S.query='Nisha';");assert.equal((run('patientCards()').match(/class="patient-card"/g)||[]).length,1);});
console.log(`${count} frontend render checks passed.`);
