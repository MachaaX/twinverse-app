/* Local camera privacy, sizing, permission races, and track ownership. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../frontend/components/VideoPreview.js'),'utf8').replace(/^export /gm,'');
(async()=>{
 class Track {
  constructor(kind){this.kind=kind;this.readyState='live';this.handlers={};}
  stop(){this.readyState='ended';}
  clone(){return new Track(this.kind);}
  addEventListener(name,fn){this.handlers[name]=fn;}
 }
 class Stream {
  constructor(tracks){this.tracks=tracks;}
  getTracks(){return this.tracks;}
  getAudioTracks(){return this.tracks.filter(t=>t.kind==='audio');}
  getVideoTracks(){return this.tracks.filter(t=>t.kind==='video');}
 }
 let dimensions={width:600,height:500},grant,stream,constraints,observer,play,onPlay;
 class Observer {constructor(fn){this.fn=fn;observer=this;}observe(){}disconnect(){this.disconnected=true;}}
 const video={parentElement:{getBoundingClientRect:()=>dimensions},style:{setProperty(_key,value){this.size=parseInt(value);}},hidden:true,async play(){onPlay?.();if(play)await play;},pause(){}};
 const sandbox=vm.createContext({window:{isSecureContext:true,MediaStream:Stream},MediaStream:Stream,ResizeObserver:Observer,
  navigator:{mediaDevices:{async getUserMedia(c){constraints=c;return grant?await grant:stream;}}},console});
 vm.runInContext(source,sandbox);const preview=vm.runInContext('videoPreview',sandbox);
 const fresh=()=>new Stream([new Track('video'),new Track('audio')]);stream=fresh();
 assert.ok(await preview.start(video));assert.ok(constraints.video&&constraints.audio);
 assert.equal(video.srcObject.getAudioTracks().length,0);assert.equal(video.srcObject.getVideoTracks().length,1);
 for(const bounds of [{width:600,height:500},{width:200,height:200},{width:1500,height:350},{width:120,height:600}]){
  dimensions=bounds;observer.fn();assert.ok(video.style.size**2/(bounds.width*bounds.height)<=.08);
  assert.ok(video.style.size<=Math.min(bounds.width,bounds.height)-24);
  if(Math.sqrt(bounds.width*bounds.height*.08)<=Math.min(bounds.width,bounds.height)-24){
   assert.ok(video.style.size>=Math.sqrt(bounds.width*bounds.height*.08)-1);
  }
 }
 const audio=preview.audioForTurn();assert.equal(audio.getVideoTracks().length,0);
 assert.notEqual(audio.getAudioTracks()[0],stream.getAudioTracks()[0]);audio.getTracks().forEach(t=>t.stop());
 assert.equal(stream.getAudioTracks()[0].readyState,'live');assert.equal(stream.getVideoTracks()[0].readyState,'live');
 preview.stop();assert.equal(video.srcObject,null);assert.equal(video.hidden,true);assert.equal(preview.active,false);
 assert.ok(observer.disconnected);assert.ok(stream.getTracks().every(t=>t.readyState==='ended'));
 console.log('PASS Camera preview stays video-only, audio clones stay audio-only, size targets 8% within frame bounds, all owned tracks stop.');
 let resolve;grant=new Promise(r=>resolve=r);const pending=preview.start(video);preview.stop();stream=fresh();resolve(stream);
 assert.equal(await pending,false);assert.ok(stream.getTracks().every(t=>t.readyState==='ended'));grant=null;
 console.log('PASS Late camera permission cannot reactivate capture after navigation.');
 let ended=0;stream=fresh();await preview.start(video,{onEnded:()=>ended++});stream.getVideoTracks()[0].handlers.ended();
 assert.equal(ended,1);assert.equal(preview.active,false);assert.equal(video.srcObject,null);
 assert.ok(stream.getTracks().every(t=>t.readyState==='ended'));
 console.log('PASS Camera disconnect releases microphone and clears preview.');
 let reject;play=new Promise((_r,j)=>reject=j);const entered=new Promise(r=>onPlay=r);stream=fresh();const older=preview.start(video);await entered;
 preview.stop();play=null;onPlay=null;stream=fresh();await preview.start(video);reject(new Error('Old playback failed'));
 await assert.rejects(older,/Old playback failed/);assert.ok(preview.active);preview.stop();
 grant=Promise.reject(Object.assign(new Error('Denied'),{name:'NotAllowedError'}));
 await assert.rejects(preview.start(video),/Denied/);assert.equal(preview.active,false);assert.equal(video.hidden,true);
 console.log('PASS Stale playback failures and denied permissions leave camera lifecycle safe.');
})().catch(error=>{console.error(error);process.exitCode=1;});
