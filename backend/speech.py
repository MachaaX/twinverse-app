"""Optional speech delivery coaching. No emotion inference or rubric scores.

SQLite is a durable processing outbox/cache. AWS mode stores recordings in S3
and completed measurements in PostgreSQL. Playback expires after 7 days;
raw-audio cleanup runs asynchronously and retries during outages.
"""
import argparse
import array
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
import uuid
import wave

from .cloud_storage import CloudStorage, load_environment

VERSION = 'speech-delivery-1'
MAX_SECONDS = 90
MAX_BYTES = 44 + MAX_SECONDS * 16000 * 2
RETENTION_SECONDS = 7 * 86400
SCHEMA = Path(__file__).parent / 'sql' / 'speech.sql'


class SpeechError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def decode_audio(content):
    if not isinstance(content, str) or len(content) > 4 * ((MAX_BYTES + 2) // 3):
        raise SpeechError(413, 'Each recording must be under 90 seconds.')
    try:
        raw = base64.b64decode(content, validate=True)
    except (ValueError, TypeError):
        raise SpeechError(422, 'Invalid audio encoding.') from None
    return raw


def analyze(raw, text, overlap_ms=0):
    """Recompute measurements from bounded PCM, never trust client features.

    Energy gaps are explicitly approximate: noise suppression and microphones
    affect them. No pitch, affect, personality or empathy classifications.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise SpeechError(413, 'Each recording must be under 90 seconds.')
    try:
        with wave.open(io.BytesIO(raw), 'rb') as sound:
            if (sound.getnchannels(), sound.getsampwidth(), sound.getframerate(), sound.getcomptype()) != (1, 2, 16000, 'NONE'):
                raise ValueError()
            frames = sound.getnframes()
            if not 1600 <= frames <= MAX_SECONDS * 16000:
                raise ValueError()
            pcm = sound.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError()
    except (wave.Error, EOFError, ValueError):
        raise SpeechError(422, 'Send a complete mono 16 kHz PCM WAV recording, 0.1–90 seconds long.') from None
    duration = frames / 16000
    if type(overlap_ms) is not int or not 0 <= overlap_ms <= math.ceil(duration * 1000):
        raise SpeechError(422, 'Invalid patient-playback overlap duration.')
    samples = array.array('h', pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    levels = [math.sqrt(sum((v / 32768) ** 2 for v in samples[i:i+320]) / len(samples[i:i+320]))
              for i in range(0, len(samples), 320)]
    peak = max(abs(v) for v in samples) / 32768
    threshold = max(0.008, max(levels) * 0.12)
    active = [i for i, value in enumerate(levels) if value >= threshold]
    first, last = (active[0], active[-1]) if active else (0, len(levels)-1)
    span = min(duration, (last-first+1) * 0.02)
    gaps, gap_start = [], None
    for i in range(first, last+2):
        quiet = i <= last and levels[i] < threshold
        if quiet and gap_start is None:
            gap_start = i
        elif not quiet and gap_start is not None:
            if (i-gap_start)*0.02 >= 0.5:
                gaps.append({'start_seconds': round(gap_start*0.02, 2), 'duration_seconds': round((i-gap_start)*0.02, 2)})
            gap_start = None
    words = len(re.findall(r"\b[\w]+(?:['’][\w]+)*\b", text))
    clipped = sum(abs(v) >= 32700 for v in samples) / frames
    reliable = bool(active) and span >= 3 and words >= 5 and peak > 0.01
    observations = []
    if reliable:
        observations.append('Try replaying the explanation and pausing between its key ideas.')
    if overlap_ms:
        observations.append('The microphone was active during patient playback. This is a browser timing observation; it does not establish an interruption.')
    if not active or peak <= 0.01:
        observations.append('The captured audio is very quiet. Check your microphone before interpreting delivery measurements.')
    if clipped > 0.005:
        observations.append('Some samples reached the recording limit. Try reducing microphone gain or moving farther from the microphone.')
    return {'version': VERSION, 'duration_seconds': round(duration, 2), 'speech_span_seconds': round(span, 2),
            'word_count': words, 'estimated_words_per_minute': round(words*60/span) if reliable else None,
            'pace_available': reliable, 'quiet_gaps': gaps, 'peak_dbfs': round(20*math.log10(max(peak, 0.000001)), 1),
            'clipped_sample_percent': round(clipped*100, 2), 'patient_playback_overlap_seconds': round(overlap_ms/1000, 2),
            'observations': observations,
            'limitations': 'Pace uses recognized words and an energy-based speech span. Quiet gaps are approximate. Microphone settings affect volume. No emotion, empathy or rubric score is inferred.'}


class SpeechStore:
    def __init__(self, store, cloud):
        self.store, self.cloud = store, cloud
        self.aws = bool(getattr(cloud, 'enabled', False))
        database = store.db.execute('PRAGMA database_list').fetchone()[2]
        self.directory = Path(database).parent / 'speech-audio'
        self.stop_event, self.wake, self.thread = threading.Event(), threading.Event(), None
        with store.lock:
            store.db.execute('''CREATE TABLE IF NOT EXISTS speech_jobs (
                id TEXT PRIMARY KEY, encounter_id TEXT NOT NULL, turn_id TEXT NOT NULL,
                document TEXT NOT NULL, UNIQUE(encounter_id,turn_id))''')
            store.db.commit()

    def _save(self, job):
        with self.store.lock:
            previous = self.store.db.execute('SELECT document FROM speech_jobs WHERE id=?', (job['id'],)).fetchone()
            if previous:
                saved = json.loads(previous[0])
                # A deletion requested during remote I/O must never be overwritten
                # by the worker's older snapshot.
                job['expires_at'] = min(job['expires_at'], saved['expires_at'])
                if saved.get('delete_pending') and not job.get('audio_deleted'):
                    job['delete_pending'] = True
                    job['next_attempt'] = 0
                if saved.get('audio_deleted'):
                    job.update(audio_deleted=True, delete_pending=False)
            self.store.db.execute('INSERT OR REPLACE INTO speech_jobs VALUES (?,?,?,?)',
                (job['id'], job['encounter_id'], job['turn_id'], json.dumps(job)))
            self.store.db.commit()

    def jobs(self, encounter_id=None):
        with self.store.lock:
            rows = self.store.db.execute('SELECT document FROM speech_jobs' + (' WHERE encounter_id=?' if encounter_id else ''),
                                         (encounter_id,) if encounter_id else ()).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, encounter_id, clip_id):
        return next((j for j in self.jobs(encounter_id) if j['id'] == clip_id), None)

    def public(self, job):
        return {key: job.get(key) for key in ('id', 'turn_id', 'status', 'created_at', 'expires_at', 'measurements', 'error', 'audio_deleted')} | {
            'audio_available': not job.get('audio_deleted') and job['expires_at'] > time.time() and job['status'] == 'ready'}

    def enqueue(self, encounter, turn, raw, overlap_ms=0):
        measurements = analyze(raw, turn['text'], overlap_ms)
        digest = hashlib.sha256(raw).hexdigest()
        with self.store.lock:
            old = next((j for j in self.jobs(encounter['id']) if j['turn_id'] == turn['id']), None)
            if old:
                if old['sha256'] != digest:
                    raise SpeechError(409, 'A different recording already belongs to this message.')
                return self.public(old)
            job_id, created = str(uuid.uuid4()), int(time.time())
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            path = self.directory / (job_id + '.wav')
            with path.open('xb') as output:
                os.chmod(path, 0o600); output.write(raw)
            prefix = getattr(self.cloud, 'prefix', 'twinverse')
            key = '/'.join(filter(None, [prefix, 'speech', job_id + '.wav']))
            job = {'id': job_id, 'encounter_id': encounter['id'], 'turn_id': turn['id'], 'owner': encounter['owner'],
                   'status': 'queued', 'created_at': created, 'expires_at': created+RETENTION_SECONDS,
                   'sha256': digest, 'object_key': key, 'measurements': measurements, 'aws': self.aws,
                   'attempts': 0, 'next_attempt': 0, 'audio_deleted': False, 'error': None}
            try:
                self._save(job)
            except Exception:
                path.unlink(missing_ok=True); raise
        self.wake.set()
        return self.public(job)

    def mirror(self, job):
        if not job['aws']:
            return
        with self.cloud._connect() as connection:
            connection.execute('''INSERT INTO public.twinverse_speech_clips
                (id,encounter_id,turn_id,student_id,document,created_at,expires_at)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s) ON CONFLICT (id) DO UPDATE SET document=EXCLUDED.document, expires_at=EXCLUDED.expires_at''',
                (job['id'], job['encounter_id'], job['turn_id'], job['owner'], json.dumps(job), job['created_at'], job['expires_at']))

    def _delete(self, job):
        if job['aws'] and job.get('upload_started') and not job.get('uploaded'):
            # Recover a PUT whose response was lost, including its version ID.
            try:
                head = self.cloud._s3().head_object(**self.cloud._bucket_args(), Key=job['object_key'])
                if head.get('Metadata', {}).get('sha256') != job['sha256']:
                    raise SpeechError(503, 'Recording integrity check failed.')
                job.update(uploaded=True, object_version=head.get('VersionId'))
                self._save(job)
            except Exception as exc:
                if getattr(exc, 'response', {}).get('Error', {}).get('Code') not in ('404', 'NoSuchKey', 'NotFound'):
                    raise
        if job['aws'] and job.get('uploaded'):
            args = {**self.cloud._bucket_args(), 'Key': job['object_key']}
            if job.get('object_version'):
                args['VersionId'] = job['object_version']
            self.cloud._s3().delete_object(**args)
        (self.directory / (job['id']+'.wav')).unlink(missing_ok=True)
        job.update(audio_deleted=True, delete_pending=False)

    def remove_audio(self, job):
        # Access stops immediately, even if AWS is down; background cleanup retries.
        with self.store.lock:
            job = self.get(job['encounter_id'], job['id'])
            job.update(delete_pending=True, expires_at=min(job['expires_at'], int(time.time())), next_attempt=0)
            self._save(job)
        self.wake.set()

    def process_once(self):
        for job in self.jobs():
            current = time.time()
            if job.get('next_attempt', 0) > current:
                continue
            try:
                if not job['audio_deleted'] and (job['expires_at'] <= current or job.get('delete_pending')):
                    self._delete(job)
                    if job['status'] == 'queued':
                        job.update(status='expired', error='Recording expired before cloud storage completed; measurements are preserved.')
                    job['mirror_pending'] = True
                    self._save(job)
                    self.mirror(job)
                    job['mirror_pending'] = False
                    self._save(job)
                    continue
                if job['status'] != 'queued' and not job.get('mirror_pending'):
                    continue
                if job['aws'] and not job.get('uploaded') and not job['audio_deleted']:
                    self.cloud.require_config()
                    # Confirm the PG table before creating a cloud object.
                    with self.cloud._connect() as connection:
                        connection.execute('SELECT id FROM public.twinverse_speech_clips LIMIT 0')
                    s3 = self.cloud._s3()
                    raw = (self.directory / (job['id']+'.wav')).read_bytes()
                    args = {**self.cloud._bucket_args(), 'Key': job['object_key'], 'Body': raw, 'ContentType': 'audio/wav',
                            'Metadata': {'sha256': job['sha256']}, 'IfNoneMatch': '*'}
                    if self.cloud.kms_key:
                        args.update(ServerSideEncryption='aws:kms', SSEKMSKeyId=self.cloud.kms_key)
                    job['upload_started'] = True
                    self._save(job)
                    try:
                        response = s3.put_object(**args)
                    except Exception as exc:
                        if getattr(exc, 'response', {}).get('Error', {}).get('Code') != 'PreconditionFailed':
                            raise
                        response = s3.head_object(**self.cloud._bucket_args(), Key=job['object_key'])
                        if response.get('Metadata', {}).get('sha256') != job['sha256']:
                            raise SpeechError(409, 'Stored recording integrity check failed.')
                    job.update(uploaded=True, object_version=response.get('VersionId'))
                    self._save(job)
                if job.get('delete_pending') or job['expires_at'] <= time.time():
                    self._delete(job)
                job.update(status='ready', error=None, mirror_pending=True)
                self._save(job)
                self.mirror(job)
                job['mirror_pending'] = False
                self._save(job)
                if job['aws']:
                    (self.directory / (job['id']+'.wav')).unlink(missing_ok=True)
            except Exception:
                job['attempts'] += 1
                job.update(next_attempt=int(current)+min(3600, 15*2**min(job['attempts'], 8)), mirror_pending=True,
                           error='Cloud storage is temporarily unavailable. Processing or deletion will retry; transcript and measurements are preserved.')
                self._save(job)
        # Clean staging files left by a crash before an outbox commit.
        known = {j['id']+'.wav' for j in self.jobs()}
        for path in self.directory.glob('*.wav'):
            if path.name not in known and path.stat().st_mtime < time.time()-RETENTION_SECONDS:
                path.unlink(missing_ok=True)

    def audio(self, job):
        job = self.get(job['encounter_id'], job['id'])
        if not self.public(job)['audio_available']:
            raise SpeechError(410, 'This recording is unavailable or has expired. Measurements remain saved.')
        if job['aws']:
            args = {**self.cloud._bucket_args(), 'Key': job['object_key']}
            if job.get('object_version'):
                args['VersionId'] = job['object_version']
            try:
                body = self.cloud._s3().get_object(**args)['Body']
                try:
                    raw = body.read(MAX_BYTES+1)
                finally:
                    body.close()
            except Exception:
                raise SpeechError(503, 'Recording playback is temporarily unavailable.') from None
        else:
            try:
                raw = (self.directory / (job['id']+'.wav')).read_bytes()
            except FileNotFoundError:
                raise SpeechError(410, 'The recording is no longer available.') from None
        if hashlib.sha256(raw).hexdigest() != job['sha256']:
            raise SpeechError(503, 'Recording integrity check failed.')
        if not self.public(self.get(job['encounter_id'], job['id']))['audio_available']:
            raise SpeechError(410, 'This recording has expired or was deleted.')
        return raw

    def start(self):
        def loop():
            while not self.stop_event.is_set():
                try:
                    self.process_once()
                except Exception:
                    print('Speech storage worker will retry.', flush=True)
                self.wake.wait(60); self.wake.clear()
        self.thread = threading.Thread(target=loop, daemon=True, name='speech-storage')
        self.thread.start()

    def close(self):
        self.stop_event.set(); self.wake.set()
        if self.thread:
            self.thread.join(timeout=35)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Initialize AWS speech metadata storage.')
    parser.add_argument('command', choices=['init-db'])
    parser.parse_args(); load_environment()
    with CloudStorage()._connect() as connection:
        connection.execute(SCHEMA.read_text())
    print('Speech metadata table is ready.')
