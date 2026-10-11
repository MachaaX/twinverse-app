"""Speech measurements, durable retries, retention and account access tests."""
import array
import base64
import copy
import io
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import wave

from backend.cloud_storage import CloudStorage
from backend.server import make_server, RUBRIC
from backend.engine import assess
from backend.speech import SpeechStore, SpeechError, analyze, decode_audio, MAX_BYTES, RETENTION_SECONDS
from backend.store import Store
from test_auth import AccountClient


TEXT='Hello I am a medical student could you explain your main concern'


def recording(quiet=False, clipped=False):
    samples=array.array('h')
    for i in range(6*16000):
        seconds=i/16000
        silent=quiet or seconds<0.5 or seconds>=5.5 or 2.5<=seconds<3.5
        samples.append(0 if silent else (32767 if clipped else round(8000*math.sin(2*math.pi*440*seconds))))
    output=io.BytesIO()
    with wave.open(output,'wb') as sound:
        sound.setparams((1,2,16000,0,'NONE','not compressed'));sound.writeframes(samples.tobytes())
    return output.getvalue()


class MeasurementsTests(unittest.TestCase):
    def test_gap_and_pace_measurements_have_no_affect_labels_or_score(self):
        result=analyze(recording(),TEXT,1000)
        self.assertEqual(result['duration_seconds'],6)
        self.assertEqual(result['speech_span_seconds'],5)
        self.assertEqual(result['estimated_words_per_minute'],144)
        self.assertEqual(result['quiet_gaps'],[{'start_seconds':2.5,'duration_seconds':1}])
        self.assertEqual(result['patient_playback_overlap_seconds'],1)
        self.assertIn('does not establish an interruption',' '.join(result['observations']))
        for field in ('score','emotion','sentiment','empathy','personality'):
            self.assertNotIn(field,result)

    def test_quiet_short_text_and_clipping_are_not_interpreted_as_delivery_scores(self):
        self.assertIsNone(analyze(recording(quiet=True),TEXT)['estimated_words_per_minute'])
        self.assertIsNone(analyze(recording(),'Hi')['estimated_words_per_minute'])
        self.assertGreater(analyze(recording(clipped=True),TEXT)['clipped_sample_percent'],60)

    def test_bad_or_oversized_audio_and_overlap_are_rejected(self):
        for raw in (b'',b'not a WAV',recording()[:100]):
            with self.assertRaises(SpeechError):analyze(raw,TEXT)
        with self.assertRaises(SpeechError):analyze(b'x'*(MAX_BYTES+1),TEXT)
        for overlap in (-1,6001,True,'2'):
            with self.assertRaises(SpeechError):analyze(recording(),TEXT,overlap)
        with self.assertRaises(SpeechError):decode_audio('not base64!')


class RemoteError(Exception):
    def __init__(self,code):self.response={'Error':{'Code':code}}


class FakeS3:
    def __init__(self):self.objects={};self.puts=[];self.deletes=[];self.hook=None;self.lose_response=False
    def put_object(self,**args):
        self.puts.append(args)
        if args['Key'] in self.objects:raise RemoteError('PreconditionFailed')
        self.objects[args['Key']]={'raw':args['Body'],'Metadata':args['Metadata'],'VersionId':'version-1'}
        if self.hook:self.hook()
        if self.lose_response:self.lose_response=False;raise RemoteError('RequestTimeout')
        return {'VersionId':'version-1'}
    def head_object(self,**args):
        if args['Key'] not in self.objects:raise RemoteError('404')
        return self.objects[args['Key']]
    def get_object(self,**args):return {'Body':io.BytesIO(self.objects[args['Key']]['raw'])}
    def delete_object(self,**args):
        self.deletes.append(args);self.objects.pop(args['Key'],None)


class FakeCloud:
    enabled=True;prefix='twinverse';kms_key=''
    def __init__(self):self.s3=FakeS3();self.documents={};self.offline=False;self.mirror_failure=False
    def require_config(self):pass
    def _bucket_args(self):return {'Bucket':'private-test','ExpectedBucketOwner':'454105254021'}
    def _s3(self):return self.s3
    def _connect(self):
        if self.offline:raise RuntimeError('secret credential must not leak')
        return self
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,query,args=None):
        if query.startswith('INSERT'):
            if self.mirror_failure:raise RuntimeError('private password')
            self.documents[args[0]]=json.loads(args[4])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'test.sqlite3')
        self.cloud=FakeCloud();self.speech=SpeechStore(self.store,self.cloud)
        self.encounter={'id':'encounter','owner':'student-id'};self.turn={'id':'t1','text':TEXT}
        self.raw=recording()
    def tearDown(self):self.store.db.close();self.temp.cleanup()
    def enqueue(self):
        public=self.speech.enqueue(self.encounter,self.turn,self.raw)
        return self.speech.get('encounter',public['id'])
    def retry(self,job):
        job=self.speech.get('encounter',job['id']);job['next_attempt']=0;self.speech._save(job);self.speech.process_once()
        return self.speech.get('encounter',job['id'])

    def test_private_upload_pg_mirror_and_exact_version_delete(self):
        job=self.enqueue();self.speech.process_once();job=self.speech.get('encounter',job['id'])
        self.assertEqual(self.speech.audio(job),self.raw)
        self.assertEqual(self.cloud.documents[job['id']]['measurements'],job['measurements'])
        args=self.cloud.s3.puts[0]
        self.assertEqual(args['IfNoneMatch'],'*');self.assertNotIn('ACL',args)
        self.assertEqual(args['ContentType'],'audio/wav');self.assertIn('/speech/',args['Key'])
        self.assertFalse((self.speech.directory/(job['id']+'.wav')).exists())
        self.speech.remove_audio(job)
        with self.assertRaises(SpeechError):self.speech.audio(job)
        self.speech.process_once()
        self.assertEqual(self.cloud.s3.deletes[0]['VersionId'],'version-1')
        self.assertTrue(self.cloud.documents[job['id']]['audio_deleted'])
        self.assertEqual(self.cloud.documents[job['id']]['measurements'],job['measurements'])

    def test_outage_retries_durably_without_reuploading_or_exposing_secrets(self):
        self.cloud.offline=True;job=self.enqueue();self.speech.process_once()
        self.assertFalse(self.cloud.s3.puts)
        self.speech=SpeechStore(self.store,self.cloud)
        failed=self.speech.get('encounter',job['id']);self.assertEqual(failed['status'],'queued')
        self.assertNotIn('secret',json.dumps(self.speech.public(failed)))
        self.cloud.offline=False;self.cloud.mirror_failure=True;job=self.retry(job)
        self.assertEqual(len(self.cloud.s3.puts),1)
        self.cloud.mirror_failure=False;job=self.retry(job)
        self.assertEqual(len(self.cloud.s3.puts),1)
        self.assertFalse(job['mirror_pending'])

    def test_delete_during_upload_cannot_reenable_playback(self):
        job=self.enqueue();self.cloud.s3.hook=lambda:self.speech.remove_audio(job)
        self.speech.process_once();saved=self.speech.get('encounter',job['id'])
        self.assertTrue(saved['audio_deleted']);self.assertFalse(self.cloud.s3.objects)
        self.assertFalse(self.speech.public(saved)['audio_available'])

    def test_unknown_successful_put_is_recovered_on_retry_or_expiry(self):
        job=self.enqueue();self.cloud.s3.lose_response=True;self.speech.process_once()
        saved=self.retry(job)
        self.assertTrue(saved['uploaded']);self.assertEqual(self.speech.audio(saved),self.raw)
        self.assertEqual(len(self.cloud.s3.objects),1)
        # Another unknown successful PUT, deleted before it can retry.
        self.turn={'id':'t3','text':TEXT};job=self.enqueue();self.cloud.s3.lose_response=True
        self.speech.process_once();self.speech.remove_audio(job);self.speech.process_once()
        saved=self.speech.get('encounter',job['id']);self.assertTrue(saved['audio_deleted'])
        self.assertEqual(self.cloud.s3.deletes[-1]['VersionId'],'version-1')
        self.assertNotIn(saved['object_key'],self.cloud.s3.objects)

    def test_local_expiry_and_duplicate_recording(self):
        self.speech=SpeechStore(self.store,CloudStorage({}));job=self.enqueue()
        self.assertEqual(self.enqueue()['id'],job['id'])
        with self.assertRaises(SpeechError):self.speech.enqueue(self.encounter,self.turn,recording(quiet=True))
        self.speech.process_once();self.assertEqual(self.speech.audio(job),self.raw)
        with patch('backend.speech.time.time',return_value=job['expires_at']+1):
            with self.assertRaises(SpeechError):self.speech.audio(job)
            self.speech.process_once()
        self.assertTrue(self.speech.get('encounter',job['id'])['audio_deleted'])


class SpeechApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'TWINVERSE_AUTH_STORAGE':'sqlite'});self.env.start()
        self.server=make_server(0,Path(self.temp.name)/'test.sqlite3',verbose=False,cloud_storage=CloudStorage({}),public_origin='')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=self.user('student@example.test');self.other=self.user('other@example.test')
        self.faculty=self.user('faculty@example.test','faculty')
        patient=self.client.call('/api/patients')[1]['patients'][0]
        self.e=self.client.call('/api/encounters','POST',{'patient_id':patient['id']})[1]
        self.path='/api/encounters/'+self.e['id']
        self.e=self.client.call(self.path+'/turns','POST',{'text':TEXT,'request_id':'voice-request'})[1]
        self.turn=next(m for m in self.e['messages'] if m['role']=='student')
        self.body={'turn_id':self.turn['id'],'consent':True,'content':base64.b64encode(recording()).decode(),'overlap_ms':0}
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.server.store.db.close()
        self.env.stop();self.temp.cleanup()
    def user(self,email,role='medical-student'):
        client=AccountClient(self.server);client.call('/api/session')
        self.assertEqual(client.call('/api/auth/signup','POST',{'name':'Speech Test','email':email,'role':role,'password':'private-test-password'})[0],201)
        return client

    def test_account_access_consent_csrf_and_recording_binding(self):
        anonymous=AccountClient(self.server);anonymous.call('/api/session')
        self.assertEqual(anonymous.call(self.path+'/speech')[0],401)
        self.assertEqual(self.other.call(self.path+'/speech')[0],403)
        self.assertEqual(self.client.call(self.path+'/speech','POST',self.body,csrf=False)[0],403)
        self.assertEqual(self.client.call(self.path+'/speech','POST',self.body|{'consent':False})[0],422)
        patient_turn=next(m['id'] for m in self.e['messages'] if m['role']=='patient')
        self.assertEqual(self.client.call(self.path+'/speech','POST',self.body|{'turn_id':patient_turn})[0],422)
        self.assertEqual(self.faculty.call(self.path+'/speech','POST',self.body)[0],403)
        status,clip=self.client.call(self.path+'/speech','POST',self.body);self.assertEqual(status,202,clip)
        self.server.speech.process_once()
        for client in (self.client,self.faculty):
            data=client.call(self.path+'/speech')[1];self.assertEqual(len(data['clips']),1)
            for private in ('owner','object_key','sha256','object_version'):self.assertNotIn(private,data['clips'][0])
        audio_path=self.path+'/speech/'+clip['id']+'/audio'
        self.assertEqual(self.other.call(audio_path)[0],403)
        self.assertEqual(self.faculty.call(audio_path,'DELETE')[0],403)
        self.assertEqual(self.client.call(audio_path,'DELETE')[0],202)
        self.assertEqual(self.client.call(audio_path)[0],410)
        self.server.speech.process_once()
        self.assertTrue(self.client.call(self.path+'/speech')[1]['clips'][0]['audio_deleted'])

    def test_audio_does_not_change_rubric_or_transcript_and_survives_completed_encounter(self):
        with self.server.store.lock:before=copy.deepcopy(self.server.store.get('encounters',self.e['id']))
        expected=assess(before,RUBRIC)
        self.client.call(self.path+'/speech','POST',self.body);self.server.speech.process_once()
        with self.server.store.lock:after=self.server.store.get('encounters',self.e['id'])
        self.assertEqual(before,after)
        # Assess uses a fresh timestamp; compare the actual scoring content.
        actual=assess(after,RUBRIC)
        self.assertEqual(expected['domains'],actual['domains']);self.assertEqual(expected['total'],actual['total'])
        self.assertEqual(self.turn['request_id'],'voice-request')
        self.client.call(self.path+'/finish','POST',{})
        self.assertTrue(self.client.call(self.path+'/speech')[1]['clips'][0]['audio_available'])


if __name__=='__main__':unittest.main()
