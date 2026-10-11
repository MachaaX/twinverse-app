/* Audio encoding and microphone lifecycle checks, included by frontend CI. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../frontend/components/VoiceRecorder.js'),'utf8').replace(/^export /gm,'');
(async()=>{
 let stops=0,closes=0,node,grant,load,onModule;
 const tracks={getTracks:()=>[{stop(){stops++;}}]};
 class Context {
   sampleRate=48000;
   audioWorklet={addModule:async()=>{const pending=load;onModule?.();if(pending)await pending;}};
   createMediaStreamSource(){return {connect(){}};}
   createGain(){return {gain:{},connect(){}};}
   async resume(){}
   async close(){closes++;}
 }
 class Worklet {
   constructor(){node=this;this.port={postMessage:()=>this.port.onmessage({data:{ended:true}})};}
   connect(){}disconnect(){}
 }
 const sandbox=vm.createContext({window:{isSecureContext:true,AudioContext:Context,AudioWorkletNode:Worklet},
   AudioContext:Context,AudioWorkletNode:Worklet,navigator:{mediaDevices:{getUserMedia:async()=>grant?await grant:tracks}},
   setTimeout:()=>1,clearTimeout(){},btoa:value=>Buffer.from(value,'binary').toString('base64'),console});
 vm.runInContext(source,sandbox);
 const recorder=vm.runInContext('voiceRecorder',sandbox);
 assert.equal(recorder.isAvailable(),true);
 await recorder.start({isPatientPlaying:()=>true});
 node.port.onmessage({data:{pcm:new Float32Array(48000).fill(.25)}});
 const result=await recorder.stop(),bytes=Buffer.from(result.content,'base64');
 assert.equal(bytes.length,32044);assert.equal(bytes.toString('ascii',0,4),'RIFF');
 assert.equal(bytes.readUInt32LE(24),16000);assert.equal(bytes.readUInt16LE(22),1);
 assert.equal(bytes.readInt16LE(44),8192);assert.equal(result.overlap_ms,1000);
 assert.equal(stops,1);assert.equal(closes,1);assert.equal(recorder.active,false);
 console.log('PASS Recorder encodes valid mono PCM and releases its microphone after stop');
 let resolveGrant;grant=new Promise(resolve=>resolveGrant=resolve);
 const pending=recorder.start();recorder.cancel();resolveGrant(tracks);
 assert.equal(await pending,false);assert.equal(stops,2);assert.equal(recorder.active,false);
 grant=null;
 console.log('PASS Late microphone permission cannot restart recording after cancellation');
 let resolveLoad;load=new Promise(resolve=>resolveLoad=resolve);
 let entered=new Promise(resolve=>onModule=resolve);
 const loading=recorder.start();await entered;
 recorder.cancel();resolveLoad();assert.equal(await loading,false);
 assert.equal(stops,3);assert.equal(recorder.active,false);load=null;
 console.log('PASS Cancellation during worklet loading closes the microphone');
 await recorder.start();node.port.onmessage({data:{pcm:new Float32Array(48000)}});
 recorder.cancel();assert.equal(await recorder.stop(),null);assert.equal(recorder.active,false);
 console.log('PASS Navigation discards raw audio rather than submitting it');
 let rejectModule;load=new Promise((_resolve,reject)=>rejectModule=reject);
 entered=new Promise(resolve=>onModule=resolve);
 const old=recorder.start();await entered;
 recorder.cancel();load=null;await recorder.start();
 rejectModule(new Error('Old worklet failed'));
 await assert.rejects(old,/Old worklet failed/);assert.equal(recorder.active,true);recorder.cancel();
 console.log('PASS A late worklet failure cannot cancel a newer recording');
})().catch(error=>{console.error(error);process.exitCode=1;});
