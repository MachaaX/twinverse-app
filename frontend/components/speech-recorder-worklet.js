// Runs on the audio thread; sends bounded mono PCM to the main thread.
class SpeechCapture extends AudioWorkletProcessor {
  constructor() {
    super(); this.buffer=new Float32Array(4096); this.used=0; this.closed=false;
    this.port.onmessage=event=>{
      if(event.data==='stop'){this.flush();this.closed=true;this.port.postMessage({ended:true});}
    };
  }
  flush() {
    if(this.used){const pcm=this.buffer.slice(0,this.used);this.port.postMessage({pcm},[pcm.buffer]);this.used=0;}
  }
  process(inputs) {
    if(this.closed)return false;
    const channels=inputs[0];
    if(channels?.length){
      for(let i=0;i<channels[0].length;i++){
        let value=0;for(const channel of channels)value+=channel[i];
        this.buffer[this.used++]=value/channels.length;
        if(this.used===this.buffer.length)this.flush();
      }
    }
    return true;
  }
}
registerProcessor('speech-capture',SpeechCapture);
