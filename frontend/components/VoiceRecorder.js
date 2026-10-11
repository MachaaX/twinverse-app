const LIMIT=90;

// Average source samples into 16 kHz bins, then encode a standard PCM WAV.
export function encodeWav(chunks, rate) {
  const length=chunks.reduce((total,c)=>total+c.length,0);
  const input=new Float32Array(length);let offset=0;
  for(const chunk of chunks){input.set(chunk,offset);offset+=chunk.length;}
  const frames=Math.min(LIMIT*16000,Math.floor(length*16000/rate));
  const bytes=new Uint8Array(44+frames*2),view=new DataView(bytes.buffer);
  const string=(at,value)=>{for(let i=0;i<value.length;i++)view.setUint8(at+i,value.charCodeAt(i));};
  string(0,'RIFF');view.setUint32(4,bytes.length-8,true);string(8,'WAVE');string(12,'fmt ');
  view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);
  view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);
  view.setUint16(34,16,true);string(36,'data');view.setUint32(40,frames*2,true);
  for(let i=0;i<frames;i++){
    const start=Math.floor(i*rate/16000),end=Math.max(start+1,Math.floor((i+1)*rate/16000));
    let value=0;for(let j=start;j<Math.min(end,length);j++)value+=input[j];
    value=Math.max(-1,Math.min(1,value/(Math.min(end,length)-start)));
    view.setInt16(44+i*2,Math.round(value*(value<0?32768:32767)),true);
  }
  return bytes;
}

export class VoiceRecorder {
  constructor(){this.generation=0;this.session=null;}
  isAvailable(){return !!(window.isSecureContext&&navigator.mediaDevices?.getUserMedia&&window.AudioContext&&window.AudioWorkletNode);}
  get active(){return !!this.session;}
  async start({isPatientPlaying=()=>false,onLimit=()=>{}}={}) {
    this.cancel();const generation=this.generation;
    if(!this.isAvailable())throw new Error('Audio coaching needs HTTPS and a browser with microphone recording support.');
    const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
    if(generation!==this.generation){stream.getTracks().forEach(track=>track.stop());return false;}
    const session={stream,chunks:[],samples:0,overlap:0,context:null,node:null,timer:null,finishing:null,cancelled:false};
    this.session=session;
    try{
      const context=session.context=new AudioContext();
      await context.audioWorklet.addModule('/components/speech-recorder-worklet.js');
      if(session.cancelled||generation!==this.generation)return false;
      const node=session.node=new AudioWorkletNode(context,'speech-capture');
      const source=context.createMediaStreamSource(stream),mute=context.createGain();mute.gain.value=0;
      source.connect(node);node.connect(mute);mute.connect(context.destination);
      node.port.onmessage=event=>{
        if(event.data.ended){session.end?.();return;}
        if(session.cancelled)return;
        const chunk=event.data.pcm?.subarray(0,Math.max(0,LIMIT*context.sampleRate-session.samples));
        if(chunk?.length){session.chunks.push(chunk);session.samples+=chunk.length;if(isPatientPlaying())session.overlap+=chunk.length/context.sampleRate;}
      };
      await context.resume();
      if(session.cancelled)return false;
      session.timer=setTimeout(onLimit,LIMIT*1000);
      return true;
    }catch(error){if(this.session===session)this.cancel();throw error;}
  }
  stop() {
    const session=this.session;if(!session)return Promise.resolve(null);
    if(session.finishing)return session.finishing;
    session.finishing=(async()=>{
      clearTimeout(session.timer);
      // Flush the audio thread before closing; release the microphone promptly.
      if(session.node)await new Promise(resolve=>{
        const timer=setTimeout(resolve,250);session.end=()=>{clearTimeout(timer);resolve();};session.node.port.postMessage('stop');
      });
      session.stream.getTracks().forEach(track=>track.stop());
      await session.context?.close().catch(()=>{});
      if(this.session===session)this.session=null;
      if(session.cancelled||!session.chunks.length)return null;
      const bytes=encodeWav(session.chunks,session.context.sampleRate);
      session.chunks=[];
      if(bytes.length<44+3200)return null;
      // Convert in chunks to avoid argument-stack limits for long utterances.
      let binary='';for(let i=0;i<bytes.length;i+=16384)binary+=String.fromCharCode(...bytes.subarray(i,i+16384));
      return {content:btoa(binary),overlap_ms:Math.min(Math.floor((bytes.length-44)/32),Math.round(session.overlap*1000))};
    })();
    return session.finishing;
  }
  cancel(){
    ++this.generation;const session=this.session;this.session=null;
    if(!session)return;
    session.cancelled=true;clearTimeout(session.timer);session.chunks=[];
    session.stream.getTracks().forEach(track=>track.stop());session.node?.disconnect();session.end?.();
    session.context?.close().catch(()=>{});
  }
}
export const voiceRecorder=new VoiceRecorder();
