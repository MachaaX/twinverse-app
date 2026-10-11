"""Loopback HTTP API, static frontend, and persistent account authorization."""
import base64
import copy
import hashlib
import json
import mimetypes
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs

# Optional: boto3 for Amazon Polly TTS
try:
    import boto3
    POLLY_AVAILABLE = True
except ImportError:
    POLLY_AVAILABLE = False
from .store import Store
from .seed import ROOT
from .engine import reply, assess, apply_review, release_feedback, includes, is_inquiry, is_records_request, artifacts_requested, ENGINE_VERSION
from . import generator, dialogue
from .cloud_storage import CloudStorage, CloudStorageError
from .auth import AuthStore, AuthError, GoogleLogin, SESSION_SECONDS, csrf_token
from .speech import SpeechStore, SpeechError, decode_audio

RUBRIC=json.loads((ROOT/'data/rubric.json').read_text())
FRONTEND=ROOT/'frontend'
MAX_BODY=8*1024*1024
REPORT_CATEGORIES={'patient_answer':'Patient said something wrong or made something up','scoring':'Score or feedback looks wrong','bug':'Something broke or did not load','content':'Clinical content looks inaccurate','other':'Other'}
MAX_REPORTS_PER_HOUR=20
MAX_LOGIN_FAILURES=5
LOCKOUT_SECONDS=60

# Shared demo password for the faculty view. Change it here, or start the app with
# TWINVERSE_FACULTY_PASSWORD="..." python3 run.py to override it without editing code.
DEFAULT_FACULTY_PASSWORD='twinverse-faculty'

# Separate password for the developer data view (ratings and reports).
DEFAULT_DEVELOPER_PASSWORD='twinverse-dev'

def load_developer_password():
    return os.environ.get('TWINVERSE_DEVELOPER_PASSWORD','').strip() or DEFAULT_DEVELOPER_PASSWORD

def csv_text(rows,fields):
    import csv,io
    out=io.StringIO();w=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');w.writeheader()
    for r in rows:w.writerow({k:('' if r.get(k) is None else r.get(k)) for k in fields})
    return out.getvalue()

def load_faculty_password():
    env=os.environ.get('TWINVERSE_FACULTY_PASSWORD','').strip()
    return (env,'TWINVERSE_FACULTY_PASSWORD') if env else (DEFAULT_FACULTY_PASSWORD,'default')

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
    d=p.get('difficulty')
    if d is not None and (not isinstance(d,dict) or any(type(d.get(k))!=int or not 1<=d.get(k)<=5 for k in ['temperament','openness'])):errors.append('Temperament and openness must be whole numbers from 1 to 5.')
    if p.get('dialogue_mode',None) not in (None,'scripted','generative'):errors.append('Choose scripted or AI conversation.')
    if any(isinstance(f,dict) and f.get('sensitivity') not in (None,'routine','sensitive') for f in facts):errors.append('Fact sensitivity must be routine or sensitive.')
    warnings.extend(p.get('validation_notes',[]) if isinstance(p.get('validation_notes',[]),list) else [])
    return {'errors':list(dict.fromkeys(errors)),'warnings':list(dict.fromkeys(warnings)),'note':'Structural checks only. Clinical correctness requires faculty review.'}

def brief(p):
    return {k:p.get(k) for k in ['id','name','age','gender','summary','image','version','status','provenance','generated_at']}

def event(e,kind,**fields):
    v={'id':uid(),'sequence':len(e['events'])+1,'type':kind,'timestamp':now(),**fields}
    e['events'].append(v);return v

FACULTY_ONLY_DOMAIN_KEYS=['suggested_score','suggested_coverage','suggested_note','suggested_evidence_ids','changed_from_suggestion']

def student_feedback(f):
    """Final, faculty-approved feedback as the student sees it (no auto-suggestions)."""
    out={k:v for k,v in copy.deepcopy(f).items() if k not in ['auto_score','suggested_summary']}
    for d in out['domains']:
        for k in FACULTY_ONLY_DOMAIN_KEYS:d.pop(k,None)
    return out

def pending_feedback(f):
    """Shown to students until faculty release a score: no scores, notes, or auto-suggestions."""
    return {'status':'awaiting_release','released':False,'total':None,'available_points':0,'review_version':f['review_version'],'input_sha256':f.get('input_sha256'),'checkpoints':f['checkpoints'],
            'domains':[{k:d[k] for k in ['id','key','name','descriptors','triggers_review_if_score_1']}|{'score':None,'review_note':'','evidence_ids':[],'observations':[]} for d in f['domains']]}

def feedback_for(e,role):
    f=e.get('feedback')
    if not f or role=='faculty':return f
    released=e.get('released_feedback')
    if released:return {**released,'update_pending':not f.get('released')}
    return pending_feedback(f)

def ratings_for(e,role):
    r=e.get('ratings') or {}
    return r if role=='faculty' else {k:v for k,v in r.items() if k=='student'}

def clean_rating(b):
    stars=b.get('stars');comment=b.get('comment','')
    if type(stars)!=int or not 1<=stars<=5:raise APIError(422,'Choose 1 to 5 stars.')
    if not isinstance(comment,str) or len(comment)>2000:raise APIError(422,'Keep the comment under 2000 characters.')
    return {'stars':stars,'comment':comment.strip(),'at':now()}

def public_encounter(e,role='student'):
    return {'id':e['id'],'patient':brief(e['profile']),'status':e['status'],'started_at':e['started_at'],'clock_started_at':e['clock_started_at'] if 'clock_started_at' in e else e['started_at'],'ended_at':e.get('ended_at'),'messages':e['messages'],'events':e['events'],'records':[f for f in e['profile']['facts'] if f['id'] in e['disclosed'] and f.get('release')!='faculty_only'],'artifacts':[a for a in e.get('attachments',[]) if a['id'] in e['released_artifacts'] and a['kind']=='artifact'],'feedback':feedback_for(e,role),'ratings':ratings_for(e,role),'engine_version':ENGINE_VERSION}

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
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' blob:; media-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        if getattr(self,'new_token',None):
            secure='; Secure' if self.server.public_origin.startswith('https://') else ''
            policy=f'SameSite=Lax; Max-Age={SESSION_SECONDS}' if self.server.auth else 'SameSite=Strict'
            self.send_header('Set-Cookie',f'twinverse_session={self.new_token}; Path=/; HttpOnly; {policy}{secure}')
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(data)

    def do_GET(self):self.handle_request('GET')
    def do_POST(self):self.handle_request('POST')
    def do_PUT(self):self.handle_request('PUT')
    def do_DELETE(self):self.handle_request('DELETE')

    def handle_request(self,method):
        try:
            self.new_token=None
            # Nginx forwards the original Host/Origin to this loopback-only backend.
            host=self.headers.get('Host','')
            public=urlparse(self.server.public_origin)
            local=host.split(':')[0] in ['127.0.0.1','localhost']
            if not local and (not self.server.public_origin or host!=public.netloc):raise APIError(403,'This host is not configured for TwinVerse.')
            origin=self.headers.get('Origin')
            expected=f'http://{host}' if local else self.server.public_origin
            if origin and origin!=expected:raise APIError(403,'Cross-origin requests are not allowed.')
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
            if self.path_only=='/api/health' and method=='GET':
                return self.send({'status':'ok','engine':ENGINE_VERSION,'llm_connected':False,'release':self.server.release})
            if self.server.auth:self.session()
            else:
                with self.store.lock:self.session()
            if self.server.auth:
                if method in ('POST','PUT','DELETE'):
                    supplied=self.headers.get('X-CSRF-Token','')
                    if not secrets.compare_digest(supplied,self.csrf):raise APIError(403,'Your session changed. Refresh the page and try again.')
                if self.path_only.startswith('/api/auth/') or self.path_only=='/api/session':
                    return self.account_route(method,body)
                if not self.user:raise APIError(401,'Sign in to access your workspace.')
            speech=re.fullmatch(r'/api/encounters/([^/]+)/speech(?:/([^/]+)/audio)?',self.path_only)
            if speech:return self.speech_route(method,body,*speech.groups())
            if method=='POST' and self.path_only in ('/api/generator/generate','/api/generator/test'):
                return self.slow_generator_call(body)
            turn=re.fullmatch(r'/api/encounters/([^/]+)/turns',self.path_only)
            if method=='POST' and turn:return self.generative_turn(turn.group(1),body)
            publish=re.fullmatch(r'/api/patients/([^/]+)/publish',self.path_only)
            if method=='POST' and publish:return self.publish_case(publish.group(1),body)
            with self.server.store.lock:
                self.route(method,body)
        except APIError as e:self.send({'error':e.message},e.status)
        except AuthError as e:self.send({'error':e.message},e.status)
        except SpeechError as e:self.send({'error':e.message},e.status)
        except (ValueError,TypeError,KeyError) as e:self.send({'error':str(e)},400)
        except Exception:
            import traceback;traceback.print_exc()
            self.send({'error':'Unexpected local server error. Check the terminal for details.'},500)

    @property
    def store(self):return self.server.store

    def speech_route(self,method,body,eid,clip_id):
        # Authorize against the encounter before accessing private storage.
        with self.store.lock:
            encounter=self.encounter(eid)
            owner=encounter['owner']==self.owner_id
            if method in ('POST','DELETE') and not owner:
                raise APIError(403,'Only the owner can record or delete audio for this encounter.')
            turn=next((m for m in encounter['messages'] if m['id']==body.get('turn_id') and m['role']=='student'),None)
        speech=self.server.speech
        if not clip_id and method=='GET':
            return self.send({'clips':[speech.public(j) for j in speech.jobs(eid)],'may_delete':owner,'retention_days':7})
        if not clip_id and method=='POST':
            if body.get('consent') is not True:raise APIError(422,'Opt in before storing a recording.')
            if not turn:raise APIError(422,'The recording must belong to an existing student message.')
            clip=speech.enqueue(encounter,turn,decode_audio(body.get('content')),body.get('overlap_ms',0))
            return self.send(clip,202)
        job=speech.get(eid,clip_id) if clip_id else None
        if not job:raise APIError(404,'Recording not found.')
        if method=='GET':return self.send(speech.audio(job),content_type='audio/wav')
        if method=='DELETE':
            speech.remove_audio(job)
            return self.send({'deleted':True,'measurements_preserved':True},202)
        raise APIError(405,'Method not allowed.')

    def session(self):
        c=SimpleCookie();c.load(self.headers.get('Cookie',''))
        token=c['twinverse_session'].value if 'twinverse_session' in c else ''
        if self.server.auth:
            valid=bool(re.fullmatch(r'[A-Za-z0-9_-]{43}',token))
            self.user=self.server.auth.lookup(token) if valid else None
            if not valid:token=secrets.token_urlsafe(32);self.new_token=token
            self.token=token;self.csrf=csrf_token(token)
            self.role=('faculty' if self.user['role']=='faculty' else 'student') if self.user else None
            self.owner_id=self.user['id'] if self.user else None
            return
        row=self.store.db.execute('SELECT role FROM sessions WHERE token=?',(token,)).fetchone()
        if not row:
            token=secrets.token_urlsafe(32);self.new_token=token
            self.store.db.execute('INSERT INTO sessions VALUES(?,?)',(token,'student'));self.store.db.commit()
            self.role='student'
        else:self.role=row['role']
        self.token=token
        self.owner_id=token

    def account_status(self):
        return {'authenticated':bool(self.user),'user':self.user,'role':self.role,
                'csrf_token':self.csrf,'developer':self.token in self.server.dev_sessions,
                'google_available':self.server.google.available,'mode':'accounts'}

    def sign_in(self,user):
        old=self.token
        token=self.server.auth.create_session(user['id'],previous_token=old)
        self.server.dev_sessions.discard(old)
        self.token=token;self.new_token=token;self.csrf=csrf_token(token);self.user=user
        self.role='faculty' if user['role']=='faculty' else 'student';self.owner_id=user['id']

    def auth_rate_limit(self):
        # Use the proxy-set IP when hosted; rotating anonymous cookies cannot bypass this.
        ip=self.headers.get('X-Real-IP',self.client_address[0]) if self.server.public_origin else self.client_address[0]
        key='auth:'+ip;current=time.time()
        with self.store.lock:
            attempts=self.server.auth_attempts
            for old in list(attempts):
                if attempts[old][1]<current-600:attempts.pop(old,None)
            count,started=attempts.get(key,(0,current))
            if count>=30:raise APIError(429,'Too many sign-in attempts. Try again in ten minutes.')
            attempts[key]=(count+1,started)

    def account_route(self,method,b):
        path=self.path_only
        if path=='/api/session':
            if method!='GET':raise APIError(405,'Account roles are set at signup. Use login or logout.')
            return self.send(self.account_status())
        if path=='/api/auth/config' and method=='GET':
            return self.send({'google_available':self.server.google.available})
        if path=='/api/auth/logout' and method=='POST':
            self.server.auth.logout(self.token);self.server.dev_sessions.discard(self.token)
            self.token=secrets.token_urlsafe(32);self.new_token=self.token;self.csrf=csrf_token(self.token)
            self.user=None;self.role=None;self.owner_id=None
            return self.send(self.account_status())
        if path in ('/api/auth/signup','/api/auth/login','/api/auth/google/start') and method=='POST':
            self.auth_rate_limit()
            if path.endswith('/google/start'):
                origin=self.server.public_origin or 'http://'+self.headers.get('Host','')
                url=self.server.google.start(self.server.auth,self.token,b.get('intent','login'),b.get('role'),self.user,origin)
                return self.send({'url':url})
            if path.endswith('/signup'):
                user=self.server.auth.signup(b.get('name'),b.get('email'),b.get('password'),b.get('role'))
            else:user=self.server.auth.login(b.get('email'),b.get('password'))
            self.sign_in(user)
            return self.send(self.account_status(),201 if path.endswith('/signup') else 200)
        if path=='/api/auth/google/callback' and method=='GET':
            values=parse_qs(urlparse(self.path).query)
            get=lambda key:values.get(key,[''])[0] if len(values.get(key,[]))<=1 else ''
            try:
                state=self.server.auth.consume_oauth(get('state'),self.token)
                if get('error'):raise AuthError(401,'Google sign-in was cancelled.')
                claims=self.server.google.claims(get('code'),state)
                user=self.server.auth.google_user(claims,state,self.user)
                self.sign_in(user)
                return self.send(b'',303,headers={'Location':'/#cases'})
            except AuthError as exc:
                # Only a safe application error is placed in the fragment, never OAuth tokens.
                from urllib.parse import urlencode
                return self.send(b'',303,headers={'Location':'/#login?'+urlencode({'error':exc.message})})
        raise APIError(404,'Authentication endpoint not found.')

    def check_faculty_password(self,supplied,expected=None,key=None):
        failures=self.server.login_failures;key=key or self.token;expected=expected or self.server.faculty_password
        count,locked_until=failures.get(key,(0,0))
        if locked_until>time.time():raise APIError(429,f'Too many incorrect passwords. Try again in {int(locked_until-time.time())+1} seconds.')
        if not isinstance(supplied,str) or not secrets.compare_digest(supplied.strip().encode(),expected.encode()):
            count+=1
            failures[key]=(0,time.time()+LOCKOUT_SECONDS) if count>=MAX_LOGIN_FAILURES else (count,0)
            raise APIError(403,'Incorrect developer password.' if key.startswith('dev:') else 'Incorrect faculty password.')
        failures.pop(key,None)

    def developer(self):
        if self.server.auth:self.faculty()
        if self.token not in self.server.dev_sessions:raise APIError(403,'Unlock the Developer tab with the developer password.')

    def developer_data(self):
        reports=sorted(self.store.all('reports'),key=lambda r:r['created_at'],reverse=True)
        ratings=[]
        for e in self.store.all('encounters'):
            f=e.get('feedback') or {}
            for kind,r in (e.get('ratings') or {}).items():
                ratings.append({'encounter_id':e['id'],'patient':e['profile']['name'],'kind':kind,'stars':r['stars'],'comment':r.get('comment',''),
                                'at':r['at'],'by':r.get('by',''),'auto_total':r.get('auto_total',(f.get('auto_score') or {}).get('total')),
                                'final_total':f.get('total'),'released':bool(e.get('released_feedback')),'turns':sum(m['role']=='student' for m in e['messages'])})
        ratings.sort(key=lambda r:r['at'],reverse=True)
        def stats(kind):
            xs=[r['stars'] for r in ratings if r['kind']==kind]
            return {'count':len(xs),'average':round(sum(xs)/len(xs),2) if xs else None,'distribution':{str(n):xs.count(n) for n in range(1,6)}}
        count=lambda key:{k:sum(r[key]==k for r in reports) for k in dict.fromkeys(r[key] for r in reports)}
        return {'generated_at':now(),'ratings':ratings,'reports':reports,
                'summary':{'conversation':stats('student'),'auto_score':stats('auto_score'),
                           'reports_by_category':count('category_label'),'reports_by_status':count('status'),'reports_by_role':count('role'),
                           'encounters':len(self.store.all('encounters'))}}

    def slow_generator_call(self,b):
        """Bedrock calls can take a minute, so they run without holding the store lock."""
        with self.server.store.lock:
            self.faculty()
        try:
            if self.path_only.endswith('/test'):return self.send(generator.test_connection())
            req=b.get('request')
            check=generator.check_request(req)
            if check['errors']:raise APIError(422,' '.join(check['errors']))
            raw,model=generator.generate_case(req)
            profile,reports=generator.normalize(raw,req,f'AI-generated from faculty description ({model})')
        except generator.GeneratorError as e:raise APIError(502,str(e))
        portrait,portrait_note=generator.generate_portrait(profile['image_prompt'],profile['age'],profile['gender'])
        if portrait_note:profile['validation_notes'].append(portrait_note)
        with self.server.store.lock:
            return self.send(self.save_generated(profile,reports,f'AI-generated draft from a faculty description ({model}). Faculty review required.',req.get('files') or [],portrait),201)

    def save_generated(self,profile,reports,provenance,uploads=(),portrait=None):
        p=dict(profile);p.update(id=uid(),version=0,status='draft',image='',provenance=provenance,source_refs=[],generated_at=now())
        def attach(name,raw,mime,kind,keywords):
            a={'id':uid(),'name':name,'size':len(raw),'mime':mime,'kind':kind,'release':'question','keywords':keywords,'uploaded_at':now(),'sha256':hashlib.sha256(raw).hexdigest()}
            self.store.db.execute('INSERT INTO attachments VALUES(?,?,?,?)',(a['id'],p['id'],json.dumps(a),raw));return a
        for r in reports:
            name=re.sub(r'[^a-z0-9]+','-',r['title'].lower()).strip('-')[:60] or 'clinical-report'
            attach(name+'.txt',(r['body']+'\n').encode(),'text/plain','artifact',r['keywords'])
        for f in uploads:  # the faculty's own files stay as faculty-only knowledge sources
            name=Path(f['name']).name
            attach(name,base64.b64decode(f['content']),generator.FILE_TYPES[Path(name).suffix.lower()],'source',[])
        if portrait:
            a=attach('portrait.jpg',portrait,'image/jpeg','portrait',[]);p['image']=f"/api/portraits/{a['id']}"
        self.store.db.commit()
        self.store.put('cases',p['id'],{'draft':p,'published':None,'history':[]})
        return {'profile':p,'attachments':self.attachments(p['id']),'validation':validate_profile(p)}

    def generative_turn(self,eid,b):
        """AI replies run outside the store lock; the turn is recorded before and after."""
        with self.server.store.lock:
            e=self.encounter(eid)
            # AI with guardrails is the default; patients set to "scripted" use approved wording only.
            if e['profile'].get('dialogue_mode','generative')!='generative':return self.route('POST',b)
            if e['status']!='active':raise APIError(409,'This encounter is finished. Start a new attempt.')
            text=b.get('text','');rid=b.get('request_id','');language=b.get('language','en')
            if not isinstance(text,str) or not text.strip() or len(text)>4000:raise APIError(422,'Enter a question of 1–4000 characters.')
            if not isinstance(rid,str) or not rid or len(rid)>100:raise APIError(422,'A unique request ID is required.')
            if rid in e['requests']:return self.send(public_encounter(e,self.role))
            if len(e['requests'])>=200:raise APIError(422,'This demo supports up to 200 turns per encounter.')
            if e.get('pending_turn'):raise APIError(409,'The patient is still answering the previous question.')
            text=text.strip();tid='t'+str(len(e['messages']))
            e['messages'].append({'id':tid,'role':'student','text':text,'timestamp':now(),'request_id':rid,'language':language});e['clock_started_at']=e.get('clock_started_at') or e['messages'][-1]['timestamp'];e['pending_turn']=tid
            event(e,'student_turn',turn_id=tid);self.save_encounter(e)
            profile=e['profile'];history=copy.deepcopy(e['messages'][:-1])
            key=dialogue.cache_key(profile,text,e['disclosed'],dialogue.rapport_established(e['messages']))
            row=self.store.db.execute('SELECT value FROM reply_cache WHERE key=?',(key,)).fetchone()
        try:
            if row:r=json.loads(row['value'])
            elif not generator.live_status()['live_available']:r=dialogue.fallback(profile,history,text,None,keep_kind=True)  # no key: scripted, still guarded
            else:r=dialogue.generate_reply(profile,history,text,language)
        except Exception:
            import traceback;traceback.print_exc()
            r=dialogue.fallback(profile,history,text,'AI reply failed unexpectedly; scripted wording used.')
        with self.server.store.lock:
            if not row and r['kind']=='generative':
                self.store.db.execute('INSERT OR REPLACE INTO reply_cache VALUES(?,?)',(key,json.dumps(r)));self.store.db.commit()
            e=self.encounter(eid);e.pop('pending_turn',None)
            e['messages'].append({'id':'t'+str(len(e['messages'])),'role':'patient','text':r['text'],'timestamp':now(),'fact_ids':r['fact_ids'],'kind':r['kind'],'reply_to':tid,'cached':bool(row)})
            if r.get('guardrail'):event(e,'guardrail_blocked',turn_id=tid,reason=r['guardrail'])
            self.record_disclosure(e,r,text,tid);e['requests'].append(rid)
            self.save_encounter(e);return self.send(public_encounter(e,self.role))

    def record_disclosure(self,e,r,text,tid):
        for fid in r['fact_ids']:
            if fid not in e['disclosed']:
                e['disclosed'].append(fid);event(e,'fact_disclosed',fact_id=fid,turn_id=tid)
        if is_records_request(text) and r['kind']!='boundary':
            waiting=[a for a in e['attachments'] if a['id'] not in e['released_artifacts'] and a.get('release')=='question']
            for a in artifacts_requested(text,waiting):
                e['released_artifacts'].append(a['id']);event(e,'artifact_released',artifact_id=a['id'],turn_id=tid)

    def faculty(self):
        if self.role!='faculty':raise APIError(403,'A faculty account is required for this action.')

    def case(self,id):
        c=self.store.get('cases',id)
        if not c or c.get('deleted_at'):raise APIError(404,'Patient not found.')
        return c

    def encounter(self,id):
        e=self.store.get('encounters',id)
        if not e:raise APIError(404,'Encounter not found.')
        if e['owner']!=self.owner_id and self.role!='faculty':raise APIError(403,'This encounter belongs to another user.')
        return e

    def attachments(self,case_id):
        return [json.loads(r['metadata']) for r in self.store.db.execute('SELECT metadata FROM attachments WHERE case_id=?',(case_id,))]

    def save_encounter(self,e):self.store.put('encounters',e['id'],e,e['owner'])

    def publish_case(self,pid,b):
        """Snapshot under the local lock; perform cloud IO without blocking readers."""
        with self.store.lock:
            self.faculty();c=self.case(pid)
            if pid in self.server.publishing_cases:raise APIError(409,'This patient is being approved. Wait for the save to finish.')
            if b.get('approved') is not True:raise APIError(422,'Confirm faculty review before publishing.')
            if 'draft_version' in b and b['draft_version']!=c['draft']['version']:
                raise APIError(409,'This case changed. Reload it before approving.')
            v=validate_profile(c['draft'])
            if v['errors']:raise APIError(422,' '.join(v['errors']))
            attachments=self.attachments(pid)
            p=copy.deepcopy(c['draft'])
            p.pop('cloud_storage',None)
            p.update(status='published',version=c['draft']['version']+1,approved_at=now(),
                     approval='Local faculty demo review',attachment_ids=[a['id'] for a in attachments])
            if self.server.auth:
                p.update(approval='Faculty account review',approved_by={'id':self.user['id'],'name':self.user['name']})
            files=[]
            if self.server.cloud_storage.enabled:
                files=[(json.loads(row['metadata']),bytes(row['content'])) for row in
                       self.store.db.execute('SELECT metadata,content FROM attachments WHERE case_id=?',(pid,))]
                # Organizer portraits are static assets rather than attachment rows.
                image=p.get('image','')
                if image.startswith('/assets/patients/'):
                    path=(FRONTEND/image.lstrip('/')).resolve()
                    if not path.is_relative_to((FRONTEND/'assets/patients').resolve()) or not path.is_file():
                        raise APIError(422,'The patient portrait is missing. Restore it before approving.')
                    raw=path.read_bytes()
                    files.append(({'id':'portrait-'+pid,'name':path.name,'kind':'portrait',
                                   'mime':mimetypes.guess_type(path.name)[0] or 'image/jpeg',
                                   'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},raw))
            self.server.publishing_cases.add(pid)
        try:
            receipt=self.server.cloud_storage.publish(p,files)
            if receipt:p['cloud_storage']=receipt
            with self.store.lock:
                if c.get('published'):c['history'].append(c['published'])
                c.update(draft=p,published=copy.deepcopy(p));self.store.put('cases',pid,c)
            return self.send({'profile':p,'attachments':attachments,'validation':v,
                              'storage':self.server.cloud_storage.status()})
        except CloudStorageError as exc:
            raise APIError(502,f'Approval could not finish. Your draft and previous published version are preserved. {exc}') from None
        finally:
            with self.store.lock:self.server.publishing_cases.discard(pid)

    def route(self,method,b):
        parts=self.path_only.strip('/').split('/')[1:]
        if parts==['health'] and method=='GET':return self.send({'status':'ok','engine':ENGINE_VERSION,'llm_connected':False,'release':self.server.release})
        if parts==['tts'] and method=='POST':
            # Amazon Polly TTS with word timing for lip-sync
            text=b.get('text') or b.get('input') or ''
            voice=b.get('voice','Joanna')
            language=b.get('language','en')
            if not text or len(text)>3000:raise APIError(422,'Text required (max 3000 chars)')

            # Supported multilingual voices
            SUPPORTED_VOICES = {
                'en': ['Joanna', 'Ruth', 'Kendra', 'Matthew', 'Stephen', 'Joey'],
                'es': ['Lucia', 'Mia', 'Miguel', 'Andres'],
                'fr': ['Lea', 'Celine', 'Mathieu'],
                'de': ['Vicki', 'Marlene', 'Hans'],
                'pt': ['Vitoria', 'Ines', 'Ricardo'],
                'it': ['Bianca', 'Carla', 'Giorgio']
            }

            # Validate voice for language
            valid_voices = []
            for voices in SUPPORTED_VOICES.values():
                valid_voices.extend(voices)

            print(f'[TTS] POLLY_AVAILABLE={POLLY_AVAILABLE}, Language: {language}, Voice: {voice}', flush=True)
            if not POLLY_AVAILABLE:
                # Fallback: return minimal response
                print('[TTS] boto3 not available, returning empty', flush=True)
                return self.send({'audioContent':'','timepoints':[],'audioDuration':0})

            try:
                print(f'[TTS] Creating Polly client with region: {os.getenv("AWS_REGION","us-west-2")}', flush=True)
                from botocore.config import Config
                config = Config(signature_version='v4')
                polly=boto3.client('polly',
                    region_name=os.getenv('AWS_REGION','us-west-2'),
                    config=config
                )

                # Use standard engine for all voices to ensure compatibility
                engine = 'neural' if voice in valid_voices else 'standard'
                validated_voice = voice if voice in valid_voices else 'Joanna'

                print(f'[TTS] Requesting audio for: "{text[:50]}..." using voice: {validated_voice}, engine: {engine}', flush=True)
                # Get audio
                audio_response=polly.synthesize_speech(
                    Text=text,
                    OutputFormat='mp3',
                    VoiceId=validated_voice,
                    Engine=engine
                )
                audio_bytes=audio_response['AudioStream'].read()
                audio_b64=base64.b64encode(audio_bytes).decode('utf-8')
                print(f'[TTS] Got audio: {len(audio_bytes)} bytes')

                # Get speech marks for timing
                print('[TTS] Requesting speech marks...')
                marks_response=polly.synthesize_speech(
                    Text=text,
                    OutputFormat='json',
                    VoiceId=validated_voice,
                    Engine=engine,
                    SpeechMarkTypes=['word']
                )
                marks_data=marks_response['AudioStream'].read().decode('utf-8')
                marks=[json.loads(line) for line in marks_data.strip().split('\n') if line.strip()]
                print(f'[TTS] Got {len(marks)} speech marks')

                # Format for TalkingHead speakAudio: separate arrays
                words=[]
                wtimes=[]
                wdurations=[]

                for i, m in enumerate(marks):
                    if m.get('type')=='word':
                        words.append(m['value'])
                        wtimes.append(m['time'])
                        # Calculate duration: time until next word, or 300ms for last word
                        if i+1<len(marks):
                            wdurations.append(marks[i+1]['time']-m['time'])
                        else:
                            wdurations.append(300)  # Default 300ms for last word

                print(f'[TTS] SUCCESS: Returning {len(audio_b64)} chars audio, {len(words)} words')
                return self.send({
                    'audioContent':audio_b64,
                    'words':words,
                    'wtimes':wtimes,
                    'wdurations':wdurations,
                    'audioDuration':len(audio_bytes)/16000*1000  # Rough estimate
                })
            except Exception as e:
                # Fallback on error
                print(f'[TTS] ERROR: {type(e).__name__}: {e}')
                import traceback
                traceback.print_exc()
                return self.send({'audioContent':'','timepoints':[],'audioDuration':0})
        if parts==['session']:
            if method=='POST':
                if b.get('role') not in ['student','faculty']:raise APIError(400,'Choose Student or Faculty.')
                if b['role']=='faculty' and self.role!='faculty':self.check_faculty_password(b.get('password'))
                self.role=b['role'];self.store.db.execute('UPDATE sessions SET role=? WHERE token=?',(self.role,self.token));self.store.db.commit()
            return self.send({'role':self.role,'developer':self.token in self.server.dev_sessions,'mode':'local-demo','faculty_login':'password','authentication':'Faculty view requires the shared demo password.'})
        if parts==['developer','login'] and method=='POST':
            if self.server.auth:self.faculty()
            self.check_faculty_password(b.get('password'),self.server.developer_password,'dev:'+self.token)
            self.server.dev_sessions.add(self.token);return self.send({'developer':True})
        if parts==['developer','logout'] and method=='POST':
            self.server.dev_sessions.discard(self.token);return self.send({'developer':False})
        if parts==['developer','data'] and method=='GET':
            self.developer();return self.send(self.developer_data())
        if len(parts)==3 and parts[:2]==['developer','export'] and method=='GET':
            self.developer();d=self.developer_data()
            if parts[2]=='data.json':return self.send(json.dumps(d,indent=2,ensure_ascii=False).encode(),headers={'Content-Disposition':'attachment; filename="twinverse-feedback-data.json"'})
            if parts[2]=='ratings.csv':
                return self.send(csv_text(d['ratings'],['at','kind','stars','comment','patient','encounter_id','by','auto_total','final_total','released','turns']).encode(),content_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="twinverse-ratings.csv"'})
            if parts[2]=='reports.csv':
                rows=[{**r,**{'context_'+k:v for k,v in r['context'].items()}} for r in d['reports']]
                return self.send(csv_text(rows,['created_at','status','role','category_label','message','context_route','context_patient','context_encounter_id','context_turn_id','context_user_agent','id']).encode(),content_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="twinverse-reports.csv"'})
            raise APIError(404,'Unknown export.')
        if parts==['rubric'] and method=='GET':return self.send(RUBRIC)
        if parts==['storage','status'] and method=='GET':
            self.faculty();return self.send(self.server.cloud_storage.status())
        if parts and parts[0]=='generator':
            self.faculty()
            if parts==['generator','status'] and method=='GET':return self.send(generator.live_status())
            if parts==['generator','check'] and method=='POST':return self.send(generator.check_request(b.get('request')))
            if parts==['generator','example'] and method=='POST':
                try:
                    example_request,raw=generator.load_example()
                    profile,reports=generator.normalize(raw,example_request,'Static generator example')
                except generator.GeneratorError as e:raise APIError(500,str(e))
                profile['validation_notes'].append('Static example: no portrait is generated offline.')
                return self.send({**self.save_generated(profile,reports,'Static example of the plain-language generator (no AI call). Faculty review required.'),'request':example_request},201)
        if parts==['validate'] and method=='POST':
            self.faculty();return self.send(validate_profile(b.get('profile',{})))
        if parts==['patients'] and method=='GET':
            patients=[]
            for c in self.store.all('cases'):
                if c.get('deleted_at'):continue
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
            if method!='GET' and parts[1] in self.server.publishing_cases:
                raise APIError(409,'This patient is being approved. Wait for the save to finish.')
            if len(parts)==2 and method=='DELETE':
                # Keep a tombstone so an empty collection is not reseeded on restart.
                # Encounter snapshots and their attachment downloads remain available.
                self.store.put('cases',parts[1],{'deleted_at':now()})
                return self.send({'deleted':True,'id':parts[1]})
            if len(parts)==2 and method=='GET':return self.send({'profile':c['draft'],'attachments':self.attachments(parts[1]),'validation':validate_profile(c['draft'])})
            if len(parts)==2 and method=='PUT':
                p=b.get('profile',{});v=validate_profile(p)
                if v['errors']:raise APIError(422,' '.join(v['errors']))
                if p.get('version')!=c['draft']['version']:raise APIError(409,'This case changed. Reload it before saving.')
                p.update(id=parts[1],status='draft',version=c['draft']['version']+1,image=c['draft'].get('image',''),generated_at=c['draft'].get('generated_at'))
                c['draft']=p;self.store.put('cases',parts[1],c)
                return self.send({'profile':p,'attachments':self.attachments(parts[1]),'validation':v})
            if parts[2:]==['validate'] and method=='POST':return self.send(validate_profile(b.get('profile',c['draft'])))
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
        if len(parts)==2 and parts[0]=='portraits' and method=='GET':
            r=self.store.db.execute('SELECT metadata,content FROM attachments WHERE id=?',(parts[1],)).fetchone()
            if not r or json.loads(r['metadata'])['kind']!='portrait':raise APIError(404,'Portrait not found.')
            return self.send(bytes(r['content']),content_type='image/jpeg')
        if len(parts)==2 and parts[0]=='attachments' and method=='GET':
            self.faculty();return self.download_attachment(parts[1])
        if parts==['encounters'] and method=='GET':
            rows=[]
            for e in self.store.all('encounters'):
                if self.role=='faculty' or e['owner']==self.owner_id:
                    rows.append({'id':e['id'],'patient':brief(e['profile']),'status':e['status'],'started_at':e['started_at'],'turns':sum(m['role']=='student' for m in e['messages']),'feedback_status':(e.get('feedback') or {}).get('status'),'released':bool(e.get('released_feedback')),'release_pending':bool(e.get('feedback')) and not (e.get('feedback') or {}).get('released')})
            return self.send({'encounters':sorted(rows,key=lambda x:x['started_at'],reverse=True)})
        if parts==['student-metrics'] and method=='GET':
            self.faculty()
            students={row['id']:{**row,'encounters':[]} for row in (self.server.auth.students() if self.server.auth else [])}
            for encounter in self.store.all('encounters'):
                owner=encounter.get('owner')
                if not owner:
                    continue
                if owner not in students:
                    if self.server.auth:
                        continue
                    students[owner]={'id':owner,'name':'Student account','encounters':[]}
                feedback=encounter.get('feedback') or {}
                if not feedback:
                    continue
                students[owner]['encounters'].append({
                    'id':encounter['id'],'patient_name':encounter['profile'].get('name','Patient'),
                    'started_at':encounter['started_at'],'ended_at':encounter.get('ended_at'),
                    'status':feedback.get('status','awaiting_release'),
                    'released':bool(encounter.get('released_feedback')),
                    'total':feedback.get('total'),'available_points':feedback.get('available_points'),
                    'domains':[{'id':d.get('id'),'key':d.get('key'),'name':d.get('name'),
                                'score':d.get('score'),'suggested_score':d.get('suggested_score')}
                               for d in feedback.get('domains',[])]})
            for student in students.values():
                student['encounters'].sort(key=lambda item:item['started_at'],reverse=True)
            return self.send({'students':sorted(students.values(),key=lambda item:item['name'].casefold())})
        if parts==['encounters'] and method=='POST':
            c=self.case(b.get('patient_id',''));p=c.get('published')
            if not p:raise APIError(422,'Publish this patient before starting an encounter.')
            p=copy.deepcopy(p)
            a=[x for x in self.attachments(p['id']) if x['id'] in p.get('attachment_ids',[]) and x['kind']=='artifact']
            e={'id':uid(),'owner':self.owner_id,'profile':p,'rubric':copy.deepcopy(RUBRIC),'status':'active','started_at':now(),'messages':[],'events':[],'disclosed':[f['id'] for f in p['facts'] if f['release']=='initial'],'attachments':a,'released_artifacts':[x['id'] for x in a if x['release']=='initial'],'requests':[],'feedback':None,'review_history':[]}
            e['clock_started_at']=None  # the student opens the conversation; the timer starts then
            event(e,'encounter_started',profile_version=p['version'])
            for fid in e['disclosed']:event(e,'fact_available',fact_id=fid,reason='baseline')
            for aid in e['released_artifacts']:event(e,'artifact_released',artifact_id=aid,reason='baseline')
            self.save_encounter(e);return self.send(public_encounter(e,self.role),201)
        if len(parts)>=2 and parts[0]=='encounters':
            e=self.encounter(parts[1])
            if len(parts)==2 and method=='GET':return self.send(public_encounter(e,self.role))
            if parts[2:]==['turns'] and method=='POST':
                if e['status']!='active':raise APIError(409,'This encounter is finished. Start a new attempt.')
                text=b.get('text','');rid=b.get('request_id','')
                if not isinstance(text,str) or not text.strip() or len(text)>4000:raise APIError(422,'Enter a question of 1–4000 characters.')
                if not isinstance(rid,str) or not rid or len(rid)>100:raise APIError(422,'A unique request ID is required.')
                if rid in e['requests']:return self.send(public_encounter(e,self.role))
                if len(e['requests'])>=200:raise APIError(422,'This demo supports up to 200 turns per encounter.')
                text=text.strip();tid='t'+str(len(e['messages']))
                e['messages'].append({'id':tid,'role':'student','text':text,'timestamp':now(),'request_id':rid});e['clock_started_at']=e.get('clock_started_at') or e['messages'][-1]['timestamp']
                event(e,'student_turn',turn_id=tid)
                r=reply(e['profile'],text)
                e['messages'].append({'id':'t'+str(len(e['messages'])),'role':'patient','text':r['text'],'timestamp':now(),'fact_ids':r['fact_ids'],'kind':r['kind'],'reply_to':tid})
                self.record_disclosure(e,r,text,tid)
                e['requests'].append(rid);self.save_encounter(e);return self.send(public_encounter(e,self.role))
            if parts[2:]==['finish'] and method=='POST':
                if e['status']=='active':
                    e.update(status='completed',ended_at=now());event(e,'encounter_finished')
                    e['feedback']=assess(e,e['rubric']);event(e,'assessment_created',engine_version=ENGINE_VERSION)
                    e['feedback']['input_sha256']=hashlib.sha256(json.dumps({'profile':e['profile'],'rubric':e['rubric'],'messages':e['messages'],'engine_version':ENGINE_VERSION},sort_keys=True).encode()).hexdigest()
                    self.save_encounter(e)
                return self.send(public_encounter(e,self.role))
            if parts[2:]==['review'] and method=='POST':
                self.faculty()
                if not e.get('feedback'):raise APIError(409,'Finish the encounter before reviewing it.')
                if b.get('review_version')!=e['feedback']['review_version']:raise APIError(409,'Feedback has changed. Reload before reviewing.')
                reviewer=str(b.get('reviewer','')).strip()
                if self.server.auth:reviewer=self.user['name']
                if not reviewer:raise APIError(422,'Enter the reviewer name.')
                updated=apply_review(e['feedback'],b.get('ratings',[]),{m['id'] for m in e['messages']},reviewer,b.get('summary'))
                e['review_history'].append(e['feedback']);e['feedback']=updated
                event(e,'faculty_review_saved',reviewer=reviewer,review_version=updated['review_version'])
                self.save_encounter(e);return self.send(public_encounter(e,self.role))
            if parts[2:]==['release'] and method=='POST':
                self.faculty()
                if not e.get('feedback'):raise APIError(409,'Finish the encounter before releasing feedback.')
                if b.get('review_version')!=e['feedback']['review_version']:raise APIError(409,'Feedback has changed. Reload before releasing.')
                reviewer=str(b.get('reviewer') or e['feedback'].get('reviewer','')).strip()
                if self.server.auth:reviewer=self.user['name']
                if not reviewer:raise APIError(422,'Enter the reviewer name.')
                try:e['feedback']=release_feedback(e['feedback'],reviewer)
                except ValueError as err:raise APIError(422,str(err))
                e['released_feedback']=student_feedback(e['feedback'])
                event(e,'feedback_released',reviewer=reviewer,review_version=e['feedback']['review_version'])
                self.save_encounter(e);return self.send(public_encounter(e,self.role))
            if parts[2:]==['rating'] and method=='POST':
                kind=b.get('kind')
                if kind=='student':
                    if self.role=='faculty' and e['owner']!=self.owner_id:raise APIError(403,'Only the student who ran this encounter can rate the conversation.')
                    if e['status']!='completed':raise APIError(409,'Finish the encounter before rating it.')
                    rating=clean_rating(b)
                elif kind=='auto_score':
                    self.faculty()
                    if not e.get('feedback'):raise APIError(409,'Finish the encounter before rating the automatic score.')
                    rating={**clean_rating(b),'by':str(b.get('reviewer') or e['feedback'].get('reviewer') or 'Faculty').strip()[:80],'auto_total':(e['feedback'].get('auto_score') or {}).get('total')}
                else:raise APIError(422,'Rate the conversation or the automatic score.')
                if self.server.auth:rating['by']=self.user['name']
                e.setdefault('ratings',{})[kind]=rating;event(e,'rating_saved',rating_kind=kind,stars=rating['stars'])
                self.save_encounter(e);return self.send(public_encounter(e,self.role))
            if parts[2:]==['export'] and method=='GET':
                return self.send(public_encounter(e,self.role),headers={'Content-Disposition':f'attachment; filename="encounter-{e["id"]}.json"'})
            if len(parts)==4 and parts[2]=='artifacts' and method=='GET':
                if parts[3] not in e['released_artifacts']:raise APIError(403,'This record has not been released in this encounter.')
                event(e,'artifact_opened',artifact_id=parts[3]);self.save_encounter(e)
                return self.download_attachment(parts[3])
        if parts==['reports'] and method=='POST':
            category=b.get('category');message=b.get('message','');context=b.get('context') or {}
            if category not in REPORT_CATEGORIES:raise APIError(422,'Choose what kind of problem this is.')
            if not isinstance(message,str) or not 5<=len(message.strip())<=2000:raise APIError(422,'Describe the problem in 5 to 2000 characters.')
            if not isinstance(context,dict):raise APIError(422,'Invalid context.')
            recent=[t for t in self.server.report_times.get(self.token,[]) if t>time.time()-3600]
            if len(recent)>=MAX_REPORTS_PER_HOUR:raise APIError(429,'Too many reports from this browser. Try again later.')
            self.server.report_times[self.token]=recent+[time.time()]
            ctx={k:str(context.get(k,''))[:200] for k in ['route','encounter_id','turn_id','patient','user_agent'] if context.get(k)}
            r={'id':uid(),'category':category,'category_label':REPORT_CATEGORIES[category],'message':message.strip(),'role':self.role,'context':ctx,'status':'open','created_at':now()}
            self.store.put('reports',r['id'],r);return self.send({'id':r['id'],'status':'open'},201)
        if parts==['reports'] and method=='GET':
            self.faculty();return self.send({'reports':sorted(self.store.all('reports'),key=lambda r:r['created_at'],reverse=True),'categories':REPORT_CATEGORIES})
        if len(parts)==2 and parts[0]=='reports' and method=='PUT':
            self.faculty();r=self.store.get('reports',parts[1])
            if not r:raise APIError(404,'Report not found.')
            if b.get('status') not in ('open','resolved'):raise APIError(422,'Status must be open or resolved.')
            r.update(status=b['status'],updated_at=now());self.store.put('reports',r['id'],r);return self.send(r)
        if parts==['ratings','summary'] and method=='GET':
            self.faculty();return self.send(self.ratings_summary())
        if parts==['resources'] and method=='GET':
            self.faculty()
            return self.send({'resources':[{'id':str(i),'name':p.name,'size':p.stat().st_size} for i,p in enumerate(self.resources())]})
        if len(parts)==2 and parts[0]=='resources' and method=='GET':
            self.faculty()
            try:p=self.resources()[int(parts[1])]
            except (ValueError,IndexError):raise APIError(404,'Resource not found.')
            return self.send(p.read_bytes(),content_type=mimetypes.guess_type(p.name)[0] or 'application/octet-stream',headers={'Content-Disposition':'attachment; filename="'+p.name.encode('ascii','ignore').decode().replace('"','')+'"'})
        raise APIError(404,'Endpoint not found.')

    def ratings_summary(self):
        convo,auto,by_patient=[],[],{}
        for e in self.store.all('encounters'):
            r=e.get('ratings') or {}
            name=e['profile']['name']
            if 'student' in r:
                convo.append({**r['student'],'patient':name,'encounter_id':e['id']})
                by_patient.setdefault(name,[]).append(r['student']['stars'])
            if 'auto_score' in r:auto.append({**r['auto_score'],'patient':name,'encounter_id':e['id']})
        avg=lambda xs:round(sum(xs)/len(xs),2) if xs else None
        recent=lambda xs:[x for x in sorted(xs,key=lambda x:x['at'],reverse=True) if x['comment']][:10]
        return {'conversation':{'average':avg([x['stars'] for x in convo]),'count':len(convo),'recent_comments':recent(convo)},
                'auto_score':{'average':avg([x['stars'] for x in auto]),'count':len(auto),'recent_comments':recent(auto)},
                'by_patient':sorted([{'patient':k,'average':avg(v),'count':len(v)} for k,v in by_patient.items()],key=lambda x:x['patient'])}

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

def make_server(port=8000,db_path=None,verbose=True,faculty_password=None,cloud_storage=None,public_origin=None,auth_store=None):
    public_origin=(public_origin if public_origin is not None else os.environ.get('TWINVERSE_PUBLIC_ORIGIN','')).rstrip('/')
    if public_origin:
        origin=urlparse(public_origin)
        if (origin.scheme not in ('http','https') or not origin.netloc or origin.path
            or origin.query or origin.fragment or origin.username or origin.password):
            raise ValueError('TWINVERSE_PUBLIC_ORIGIN must be an http(s) origin, without a path or credentials.')
        if (auth_store is False and (faculty_password or load_faculty_password()[0])==DEFAULT_FACULTY_PASSWORD
            or load_developer_password()==DEFAULT_DEVELOPER_PASSWORD):
            raise ValueError('Set private TWINVERSE_FACULTY_PASSWORD and TWINVERSE_DEVELOPER_PASSWORD before hosting.')
    s=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    s.public_origin=public_origin
    release_file=ROOT/'.release'
    s.release=release_file.read_text().strip() if release_file.is_file() else 'local'
    s.store=Store(db_path or os.environ.get('TWINVERSE_DB_PATH') or ROOT/'data/twinverse.sqlite3');s.verbose=verbose
    s.cloud_storage=cloud_storage if cloud_storage is not None else CloudStorage()
    s.speech=SpeechStore(s.store,s.cloud_storage)
    # False is an explicit legacy adapter for pre-account regression tests only.
    s.auth=None if auth_store is False else auth_store or AuthStore(s.store,s.cloud_storage)
    s.google=GoogleLogin()
    s.publishing_cases=set()
    s.faculty_password,s.faculty_password_source=(faculty_password,'test') if faculty_password else load_faculty_password()
    s.login_failures={};s.auth_attempts={};s.report_times={};s.dev_sessions=set()
    s.developer_password=load_developer_password()
    # Only the explicit legacy regression adapter resets its shared demo role.
    if not s.auth:s.store.db.execute("UPDATE sessions SET role='student'");s.store.db.commit()
    return s
