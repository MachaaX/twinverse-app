// Camera frames are rendered locally. Only cloned audio tracks leave this class
// for the existing WAV recorder; no video encoding, uploads, or snapshots.
export class VideoPreview {
  constructor(){this.generation=0;this.session=null;}
  isAvailable(){return !!(window.isSecureContext&&navigator.mediaDevices?.getUserMedia&&window.MediaStream);}
  get active(){return !!this.session;}
  async start(video,{onEnded=()=>{}}={}){
    this.stop();const generation=this.generation;
    if(!this.isAvailable())throw new Error('Camera preview needs HTTPS and camera support.');
    if(!video)throw new Error('The camera preview is unavailable on this page.');
    const stream=await navigator.mediaDevices.getUserMedia({
      video:{facingMode:'user',width:{ideal:320},height:{ideal:320}},
      audio:{echoCancellation:true,noiseSuppression:true}
    });
    if(generation!==this.generation){stream.getTracks().forEach(track=>track.stop());return false;}
    const session={stream,video,observer:null};this.session=session;
    try{
      const frame=video.parentElement;
      const resize=()=>{
        const {width,height}=frame.getBoundingClientRect();
        // A square <= a quarter of either dimension is <= 1/16 frame area.
        const size=Math.max(0,Math.floor(Math.min(width,height)*.25));
        video.style.setProperty('--camera-preview-size',Math.min(160,size)+'px');
      };
      resize();
      session.observer=new ResizeObserver(resize);session.observer.observe(frame);
      video.srcObject=new MediaStream(stream.getVideoTracks());video.hidden=false;
      for(const track of stream.getTracks())track.addEventListener('ended',()=>{
        if(this.session!==session)return;
        this.stop();onEnded();
      });
      await video.play();
      if(generation!==this.generation)return false;
      return true;
    }catch(error){if(this.session===session)this.stop();throw error;}
  }
  audioForTurn(){
    const tracks=this.session?.stream.getAudioTracks().filter(track=>track.readyState==='live');
    if(!tracks?.length)throw new Error('The camera microphone is unavailable. Switch to Voice mode or reconnect your device.');
    // The recorder owns these clones and can stop them without ending preview.
    return new MediaStream(tracks.map(track=>track.clone()));
  }
  stop(){
    ++this.generation;const session=this.session;this.session=null;
    if(!session)return;
    session.observer?.disconnect();session.video.pause();session.video.srcObject=null;session.video.hidden=true;
    session.stream.getTracks().forEach(track=>track.stop());
  }
}
export const videoPreview=new VideoPreview();
