"""Local-only HTTP API and static frontend; Python standard library only."""
import base64
import copy
import hashlib
import json
import mimetypes
import secrets
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from .store import Store
from .seed import ROOT
from .engine import reply, assess, apply_review, includes, is_inquiry, ENGINE_VERSION

RUBRIC=json.loads((ROOT/'data/rubric.json').read_text())
FRONTEND=ROOT/'frontend'
MAX_BODY=8*1024*1024

def now():return datetime.now(timezone.utc).isoformat()
def uid():return str(uuid.uuid4())

class APIError(Exception):
    def __init__(self,status,message):self.status=status;self.message=message

def validate_profile(p):
    errors=[];warnings=[]
    if not isinstance(p,dict):return {'errors':['Profile must be an object.'],'warnings':[]}
    for key in ['name','summary','background','persona']:
        if not isinstance(p.get(key),str) or not p[key].strip():errors.append(f'{key.capitalize()} is required.')
        elif len(p[key])>10000:errors.append(f'{key.capitalize()} is too long.')
    if type(p.get('age'))!=int or not 0<=p['age']<=120:errors.append('Age must be an integer between 0 and 120.')
    facts=p.get('facts',[]);objectives=p.get('objectives',[])
    if not isinstance(facts,list) or not 1<=len(facts)<=40:return {'errors':errors+['Add 1–40 structured facts.'],'warnings':warnings}
    ids=[]
    for f in facts:
        if not isinstance(f,dict):errors.append('Each fact must be an object.');continue
        for key in ['id','label','record','patient_text']:
            if not isinstance(f.get(key),str) or not f[key].strip():errors.append(f'Each fact needs {key}.')
        ids.append(f.get('id'))
        if f.get('release') not in ['initial','question','faculty_only']:errors.append('Choose a valid release mode for each fact.')
        keywords=f.get('keywords')
        if not isinstance(keywords,list) or any(not isinstance(k,str) or not k.strip() or len(k)>100 for k in keywords):errors.append('Keywords must be a list of short nonempty phrases.')
        elif f.get('release')=='question' and not keywords:errors.append(f"Add trigger phrases for {f.get('label','this fact')}.")
        if not f.get('source'):warnings.append(f"{f.get('label','Fact')}: provenance is missing.")
    if len(set(str(x) for x in ids))!=len(ids):errors.append('Fact IDs must be unique.')
    if not isinstance(objectives,list) or not objectives:errors.append('Add at least one learning checkpoint.')
    else:
        objective_ids=[]
        for o in objectives:
            if not isinstance(o,dict):errors.append('Each checkpoint must be an object.');continue
            objective_ids.append(o.get('id'))
            if not o.get('id') or not o.get('label'):errors.append('Each checkpoint needs an ID and label.')
            refs=o.get('fact_ids',[])
            if not isinstance(refs,list):errors.append('Checkpoint fact references must be a list.');continue
            if any(x not in ids for x in refs):errors.append('A checkpoint references a missing fact.')
            if any(f.get('id') in refs and f.get('release')=='faculty_only' for f in facts if isinstance(f,dict)):errors.append('A checkpoint cannot require a faculty-only fact.')
        if len(set(str(x) for x in objective_ids))!=len(objective_ids):errors.append('Checkpoint IDs must be unique.')
    warnings.extend(p.get('validation_notes',[]) if isinstance(p.get('validation_notes',[]),list) else [])
    return {'errors':list(dict.fromkeys(errors)),'warnings':list(dict.fromkeys(warnings)),'note':'Structural checks only. Clinical correctness requires faculty review.'}

def brief(p):
    return {k:p.get(k) for k in ['id','name','age','gender','summary','image','version','status','provenance']}

def event(e,kind,**fields):
    v={'id':uid(),'sequence':len(e['events'])+1,'type':kind,'timestamp':now(),**fields}
    e['events'].append(v);return v

def public_encounter(e):
    return {'id':e['id'],'patient':brief(e['profile']),'status':e['status'],'started_at':e['started_at'],'ended_at':e.get('ended_at'),'messages':e['messages'],'events':e['events'],'records':[f for f in e['profile']['facts'] if f['id'] in e['disclosed'] and f.get('release')!='faculty_only'],'artifacts':[a for a in e.get('attachments',[]) if a['id'] in e['released_artifacts'] and a['kind']=='artifact'],'feedback':e.get('feedback'),'engine_version':ENGINE_VERSION}

class Handler(BaseHTTPRequestHandler):
    server_version='TwinVerseLocal/1.0'
    def log_message(self,format,*args):
        if self.server.verbose:super().log_message(format,*args)

    def send(self,data,status=200,content_type='application/json; charset=utf-8',headers=None):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        if getattr(self,'new_token',None):self.send_header('Set-Cookie',f'twinverse_session={self.new_token}; Path=/; HttpOnly; SameSite=Strict')
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(data)

    def do_GET(self):self.handle_request('GET')
    def do_POST(self):self.handle_request('POST')
    def do_PUT(self):self.handle_request('PUT')

    def handle_request(self,method):
        try:
            self.new_token=None
            # Loopback-only server; browser role switching is an explicit demo feature.
            host=self.headers.get('Host','')
            if host.split(':')[0] not in ['127.0.0.1','localhost']:raise APIError(403,'Use localhost or 127.0.0.1 to open this local demo.')
            origin=self.headers.get('Origin')
            if origin and origin!=f'http://{host}':raise APIError(403,'Cross-origin requests are not allowed.')
            self.path_only=unquote(urlparse(self.path).path)
            if not self.path_only.startswith('/api/'):
                if method!='GET':raise APIError(405,'Method not allowed.')
                return self.static()
            body={}
            if method in ['POST','PUT']:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise APIError(415,'Send JSON content.')
                try:length=int(self.headers.get('Content-Length','0'))
                except ValueError:raise APIError(400,'Invalid content length.')
                if length<0 or length>MAX_BODY:raise APIError(413,'Request too large. Maximum upload size is 5 MB.')
                try:body=json.loads(self.rfile.read(length) or b'{}')
                except (ValueError,UnicodeDecodeError):raise APIError(400,'Invalid JSON.')
                if not isinstance(body,dict):raise APIError(400,'JSON body must be an object.')
            with self.server.store.lock:
                self.session()
                self.route(method,body)
        except APIError as e:self.send({'error':e.message},e.status)
        except (ValueError,TypeError,KeyError) as e:self.send({'error':str(e)},400)
        except Exception:
            import traceback;traceback.print_exc()
            self.send({'error':'Unexpected local server error. Check the terminal for details.'},500)

    @property
    def store(self):return self.server.store

    def session(self):
        c=SimpleCookie();c.load(self.headers.get('Cookie',''))
        token=c['twinverse_session'].value if 'twinverse_session' in c else ''
        row=self.store.db.execute('SELECT role FROM sessions WHERE token=?',(token,)).fetchone()
        if not row:
            token=secrets.token_urlsafe(32);self.new_token=token
            self.store.db.execute('INSERT INTO sessions VALUES(?,?)',(token,'student'));self.store.db.commit()
            self.role='student'
        else:self.role=row['role']
        self.token=token

    def faculty(self):
        if self.role!='faculty':raise APIError(403,'Switch to the Faculty demo workspace for this action.')

    def case(self,id):
        c=self.store.get('cases',id)
        if not c:raise APIError(404,'Patient not found.')
        return c

    def encounter(self,id):
        e=self.store.get('encounters',id)
        if not e:raise APIError(404,'Encounter not found.')
        if e['owner']!=self.token and self.role!='faculty':raise APIError(403,'This encounter belongs to another browser session.')
        return e

    def attachments(self,case_id):
        return [json.loads(r['metadata']) for r in self.store.db.execute('SELECT metadata FROM attachments WHERE case_id=?',(case_id,))]

    def save_encounter(self,e):self.store.put('encounters',e['id'],e,e['owner'])

    def route(self,method,b):
        parts=self.path_only.strip('/').split('/')[1:]
        if parts==['health'] and method=='GET':return self.send({'status':'ok','engine':ENGINE_VERSION,'llm_connected':False})
        if parts==['session']:
            if method=='POST':
                if b.get('role') not in ['student','faculty']:raise APIError(400,'Choose Student or Faculty.')
                self.role=b['role'];self.store.db.execute('UPDATE sessions SET role=? WHERE token=?',(self.role,self.token));self.store.db.commit()
            return self.send({'role':self.role,'mode':'local-demo','authentication':'Demo role switch; not production authentication.'})
        if parts==['rubric'] and method=='GET':return self.send(RUBRIC)
        if parts==['validate'] and method=='POST':
            self.faculty();return self.send(validate_profile(b.get('profile',{})))
        if parts==['patients'] and method=='GET':
            patients=[]
            for c in self.store.all('cases'):
                p=c['draft'] if self.role=='faculty' else c.get('published')
                if p:patients.append({**brief(p),'has_published_version':bool(c.get('published')),'published_card':brief(c['published']) if c.get('published') else None})
            return self.send({'patients':patients})
        if parts==['patients'] and method=='POST':
            self.faculty();p=b.get('profile',{})
            v=validate_profile(p)
            if v['errors']:raise APIError(422,' '.join(v['errors']))
            p.update(id=uid(),version=0,status='draft',image='',provenance='Faculty-created local demo case',source_refs=[])
            self.store.put('cases',p['id'],{'draft':p,'published':None,'history':[]})
            return self.send({'profile':p,'attachments':[],'validation':v},201)
        if len(parts)>=2 and parts[0]=='patients':
            self.faculty();c=self.case(parts[1])
            if len(parts)==2 and method=='GET':return self.send({'profile':c['draft'],'attachments':self.attachments(parts[1]),'validation':validate_profile(c['draft'])})
            if len(parts)==2 and method=='PUT':
                p=b.get('profile',{});v=validate_profile(p)
                if v['errors']:raise APIError(422,' '.join(v['errors']))
                if p.get('version')!=c['draft']['version']:raise APIError(409,'This case changed. Reload it before saving.')
                p.update(id=parts[1],status='draft',version=c['draft']['version']+1,image=c['draft'].get('image',''))
                c['draft']=p;self.store.put('cases',parts[1],c)
                return self.send({'profile':p,'attachments':self.attachments(parts[1]),'validation':v})
            if parts[2:]==['validate'] and method=='POST':return self.send(validate_profile(b.get('profile',c['draft'])))
            if parts[2:]==['publish'] and method=='POST':
                if b.get('approved') is not True:raise APIError(422,'Confirm faculty review before publishing.')
                v=validate_profile(c['draft'])
                if v['errors']:raise APIError(422,' '.join(v['errors']))
                if c.get('published'):c['history'].append(c['published'])
                p=copy.deepcopy(c['draft']);p.update(status='published',version=c['draft']['version']+1,approved_at=now(),approval='Local faculty demo review',attachment_ids=[a['id'] for a in self.attachments(parts[1])])
                c.update(draft=p,published=copy.deepcopy(p));self.store.put('cases',parts[1],c)
                return self.send({'profile':p,'attachments':self.attachments(parts[1]),'validation':v})
            if parts[2:]==['attachments'] and method=='POST':
                name=Path(str(b.get('name',''))).name
                ext=Path(name).suffix.lower()
                types={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.txt':'text/plain','.md':'text/plain','.json':'application/json'}
                if ext not in types or not name:raise APIError(422,'Upload PDF, PNG, JPG, TXT, MD, or JSON.')
                raw=base64.b64decode(b.get('content',''),validate=True)
                if not raw or len(raw)>5*1024*1024:raise APIError(413,'Files must be between 1 byte and 5 MB.')
                if b.get('kind') not in ['source','artifact']:raise APIError(422,'Choose source or artifact.')
                if b.get('release') not in ['initial','question']:raise APIError(422,'Invalid release rule.')
                keys=b.get('keywords',[])
                if not isinstance(keys,list) or any(not isinstance(k,str) or len(k)>100 for k in keys):raise APIError(422,'Invalid trigger phrases.')
                if b['kind']=='artifact' and b['release']=='question' and not any(k.strip() for k in keys):raise APIError(422,'Add an artifact release phrase.')
                a={'id':uid(),'name':name,'size':len(raw),'mime':types[ext],'kind':b['kind'],'release':b['release'],'keywords':keys,'uploaded_at':now(),'sha256':hashlib.sha256(raw).hexdigest()}
                self.store.db.execute('INSERT INTO attachments VALUES(?,?,?,?)',(a['id'],parts[1],json.dumps(a),raw));self.store.db.commit()
                return self.send(a,201)
        if len(parts)==2 and parts[0]=='attachments' and method=='GET':
            self.faculty();return self.download_attachment(parts[1])
        if parts==['encounters'] and method=='GET':
            rows=[]
            for e in self.store.all('encounters'):
                if self.role=='faculty' or e['owner']==self.token:
                    rows.append({'id':e['id'],'patient':brief(e['profile']),'status':e['status'],'started_at':e['started_at'],'turns':sum(m['role']=='student' for m in e['messages']),'feedback_status':(e.get('feedback') or {}).get('status')})
            return self.send({'encounters':sorted(rows,key=lambda x:x['started_at'],reverse=True)})
        if parts==['encounters'] and method=='POST':
            c=self.case(b.get('patient_id',''));p=c.get('published')
            if not p:raise APIError(422,'Publish this patient before starting an encounter.')
            p=copy.deepcopy(p)
            a=[x for x in self.attachments(p['id']) if x['id'] in p.get('attachment_ids',[]) and x['kind']=='artifact']
            e={'id':uid(),'owner':self.token,'profile':p,'rubric':copy.deepcopy(RUBRIC),'status':'active','started_at':now(),'messages':[],'events':[],'disclosed':[f['id'] for f in p['facts'] if f['release']=='initial'],'attachments':a,'released_artifacts':[x['id'] for x in a if x['release']=='initial'],'requests':[],'feedback':None,'review_history':[]}
            e['messages'].append({'id':'t0','role':'patient','text':f"Hello, I’m {p['name'].split()[0]}. What would you like to talk about?",'timestamp':now(),'fact_ids':[],'kind':'opening'})
            event(e,'encounter_started',profile_version=p['version'])
            for fid in e['disclosed']:event(e,'fact_available',fact_id=fid,reason='baseline')
            for aid in e['released_artifacts']:event(e,'artifact_released',artifact_id=aid,reason='baseline')
            self.save_encounter(e);return self.send(public_encounter(e),201)
        if len(parts)>=2 and parts[0]=='encounters':
            e=self.encounter(parts[1])
            if len(parts)==2 and method=='GET':return self.send(public_encounter(e))
            if parts[2:]==['turns'] and method=='POST':
                if e['status']!='active':raise APIError(409,'This encounter is finished. Start a new attempt.')
                text=b.get('text','');rid=b.get('request_id','')
                if not isinstance(text,str) or not text.strip() or len(text)>4000:raise APIError(422,'Enter a question of 1–4000 characters.')
                if not isinstance(rid,str) or not rid or len(rid)>100:raise APIError(422,'A unique request ID is required.')
                if rid in e['requests']:return self.send(public_encounter(e))
                if len(e['requests'])>=200:raise APIError(422,'This demo supports up to 200 turns per encounter.')
                text=text.strip();tid='t'+str(len(e['messages']))
                e['messages'].append({'id':tid,'role':'student','text':text,'timestamp':now()})
                event(e,'student_turn',turn_id=tid)
                r=reply(e['profile'],text)
                e['messages'].append({'id':'t'+str(len(e['messages'])),'role':'patient','text':r['text'],'timestamp':now(),'fact_ids':r['fact_ids'],'kind':r['kind'],'reply_to':tid})
                for fid in r['fact_ids']:
                    if fid not in e['disclosed']:
                        e['disclosed'].append(fid);event(e,'fact_disclosed',fact_id=fid,turn_id=tid)
                if is_inquiry(text) and r['kind']!='boundary':
                    for a in e['attachments']:
                        if a['id'] not in e['released_artifacts'] and any(includes(text,k) for k in a['keywords']):
                            e['released_artifacts'].append(a['id']);event(e,'artifact_released',artifact_id=a['id'],turn_id=tid)
                e['requests'].append(rid);self.save_encounter(e);return self.send(public_encounter(e))
            if parts[2:]==['finish'] and method=='POST':
                if e['status']=='active':
                    e.update(status='completed',ended_at=now());event(e,'encounter_finished')
                    e['feedback']=assess(e,e['rubric']);event(e,'assessment_created',engine_version=ENGINE_VERSION)
                    e['feedback']['input_sha256']=hashlib.sha256(json.dumps({'profile':e['profile'],'rubric':e['rubric'],'messages':e['messages'],'engine_version':ENGINE_VERSION},sort_keys=True).encode()).hexdigest()
                    self.save_encounter(e)
                return self.send(public_encounter(e))
            if parts[2:]==['review'] and method=='POST':
                self.faculty()
                if not e.get('feedback'):raise APIError(409,'Finish the encounter before reviewing it.')
                if b.get('review_version')!=e['feedback']['review_version']:raise APIError(409,'Feedback has changed. Reload before reviewing.')
                reviewer=str(b.get('reviewer','')).strip()
                if not reviewer:raise APIError(422,'Enter the reviewer name.')
                updated=apply_review(e['feedback'],b.get('ratings',[]),{m['id'] for m in e['messages']},reviewer)
                e['review_history'].append(e['feedback']);e['feedback']=updated
                event(e,'faculty_review_saved',reviewer=reviewer,review_version=updated['review_version'])
                self.save_encounter(e);return self.send(public_encounter(e))
            if parts[2:]==['export'] and method=='GET':
                return self.send(public_encounter(e),headers={'Content-Disposition':f'attachment; filename="encounter-{e["id"]}.json"'})
            if len(parts)==4 and parts[2]=='artifacts' and method=='GET':
                if parts[3] not in e['released_artifacts']:raise APIError(403,'This record has not been released in this encounter.')
                event(e,'artifact_opened',artifact_id=parts[3]);self.save_encounter(e)
                return self.download_attachment(parts[3])
        if parts==['resources'] and method=='GET':
            self.faculty()
            return self.send({'resources':[{'id':str(i),'name':p.name,'size':p.stat().st_size} for i,p in enumerate(self.resources())]})
        if len(parts)==2 and parts[0]=='resources' and method=='GET':
            self.faculty()
            try:p=self.resources()[int(parts[1])]
            except (ValueError,IndexError):raise APIError(404,'Resource not found.')
            return self.send(p.read_bytes(),content_type=mimetypes.guess_type(p.name)[0] or 'application/octet-stream',headers={'Content-Disposition':'attachment; filename="'+p.name.encode('ascii','ignore').decode().replace('"','')+'"'})
        raise APIError(404,'Endpoint not found.')

    def resources(self):return sorted(p for p in (ROOT/'samples').rglob('*') if p.is_file() and p.suffix.lower() not in ['.png','.jpg'])

    def download_attachment(self,id):
        r=self.store.db.execute('SELECT metadata,content FROM attachments WHERE id=?',(id,)).fetchone()
        if not r:raise APIError(404,'Attachment not found.')
        a=json.loads(r['metadata']);name=a['name'].encode('ascii','ignore').decode().replace('"','').replace('\r','').replace('\n','')
        return self.send(bytes(r['content']),content_type=a['mime'],headers={'Content-Disposition':f'attachment; filename="{name}"'})

    def static(self):
        path=self.path_only
        if path=='/':p=FRONTEND/'index.html'
        else:p=(FRONTEND/path.lstrip('/')).resolve()
        if not p.is_relative_to(FRONTEND.resolve()) or not p.is_file():raise APIError(404,'File not found.')
        return self.send(p.read_bytes(),content_type=mimetypes.guess_type(p.name)[0] or 'application/octet-stream')

def make_server(port=8000,db_path=None,verbose=True):
    s=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    s.store=Store(db_path or ROOT/'data/twinverse.sqlite3');s.verbose=verbose
    return s
