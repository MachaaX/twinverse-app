import json
import sqlite3
import threading
from pathlib import Path
from .seed import seed_profiles

class Store:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.db=sqlite3.connect(path,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, document TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS encounters(id TEXT PRIMARY KEY, owner TEXT NOT NULL, document TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attachments(id TEXT PRIMARY KEY, case_id TEXT NOT NULL, metadata TEXT NOT NULL, content BLOB NOT NULL);
        ''')
        if not self.db.execute('SELECT 1 FROM cases LIMIT 1').fetchone():
            for p in seed_profiles():self.put('cases',p['id'],{'draft':p,'published':p,'history':[]})
        self.load_case_files()
        self.db.commit()

    def put(self,table,id,value,owner=None):
        with self.lock:
            if table=='encounters':self.db.execute('INSERT OR REPLACE INTO encounters VALUES(?,?,?)',(id,owner,json.dumps(value)))
            else:self.db.execute('INSERT OR REPLACE INTO cases VALUES(?,?)',(id,json.dumps(value)))
            self.db.commit()

    def get(self,table,id):
        row=self.db.execute(f'SELECT document FROM {table} WHERE id=?',(id,)).fetchone()
        return json.loads(row['document']) if row else None

    def all(self,table):
        return [json.loads(r['document']) for r in self.db.execute(f'SELECT document FROM {table}')]

    def load_case_files(self):
        """Install curated demo cases from data/cases/*.json.
        A case is (re)installed when it is new or its case_file_version changed,
        so editing the JSON and restarting is enough; faculty edits in the app
        are kept until the file version is bumped."""
        folder=Path(__file__).resolve().parent.parent/'data/cases'
        for f in sorted(folder.glob('*.json')):
            case=json.loads(f.read_text(encoding='utf-8'));p=case.get('profile')
            if not p or not p.get('id'):continue
            p={**p,'case_file':f.name,'case_file_version':case.get('case_file_version',1)}
            current=self.get('cases',p['id'])
            if current and (current.get('published') or {}).get('case_file_version')==p['case_file_version']:continue
            history=(current or {}).get('history',[])+([current['published']] if current and current.get('published') else [])
            self.put('cases',p['id'],{'draft':p,'published':p,'history':history})
