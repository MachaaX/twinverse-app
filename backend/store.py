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
        CREATE TABLE IF NOT EXISTS reply_cache(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        if not self.db.execute('SELECT 1 FROM cases LIMIT 1').fetchone():
            for p in seed_profiles():self.put('cases',p['id'],{'draft':p,'published':p,'history':[]})
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
