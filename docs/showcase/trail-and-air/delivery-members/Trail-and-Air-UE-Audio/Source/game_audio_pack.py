"""Trail & Air: deterministic original game-audio synthesis.

MIT code; CC0-1.0 generated audio. NumPy and the Python standard library only.
The WAVs written here are procedural SOURCE WAVs, not DAW or REAPER renders.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import wave
import numpy as np

TAU=2*np.pi
PACK_NAME='Trail & Air'
VERSION='1.0'


def smooth(x):
    x=np.clip(x,0,1)
    return x*x*(3-2*x)


def hz(m):
    return 440*2**((m-69)/12)


def pan(x,p):
    a=(p+1)*np.pi/4
    return np.column_stack([x*np.cos(a),x*np.sin(a)])


def noise(n,sr,rng,low,high,pink=0):
    # DFT-domain synthesis is intrinsically circular at exactly n samples.
    f=np.fft.rfftfreq(n,1/sr)
    spectrum=rng.normal(size=len(f))+1j*rng.normal(size=len(f))
    shape=(1-np.exp(-(f/max(low,1))**4))*np.exp(-(f/high)**4)
    shape/=np.maximum(f,20)**pink
    spectrum*=shape
    spectrum[0]=0
    if n%2==0:
        spectrum[-1]=spectrum[-1].real
    x=np.fft.irfft(spectrum,n)
    return x/max(1e-12,np.std(x))


def add(dst,src,start,sr,level=1):
    i=round(start*sr)
    if i>=len(dst):return
    skip=max(0,-i); i=max(0,i)
    count=min(len(src)-skip,len(dst)-i)
    if count>0:dst[i:i+count]+=src[skip:skip+count]*level


def circular_add(dst,src,start,sr,level=1):
    # Supports events and tails crossing the seam without a fade or dead zone.
    start=round(start*sr)%len(dst)
    offset=0
    while offset<len(src):
        count=min(len(dst)-start,len(src)-offset)
        dst[start:start+count]+=src[offset:offset+count]*level
        offset+=count;start=0


def low_thud(t,freq,decay):
    phase=TAU*(freq*t+28*.015*(1-np.exp(-t/.015)))
    return np.sin(phase)*np.exp(-t/decay)*smooth(t/.0025)


def footstep(surface,variant,sr,rng):
    durations={'stone':[.29,.34,.31,.37,.33,.41],
               'grass':[.28,.35,.32,.38,.30,.42]}
    duration=durations[surface][variant]
    t=np.arange(round(duration*sr))/sr
    stone=surface=='stone'
    body=noise(len(t),sr,rng,65,1350 if stone else 850,pink=.22)
    body*=np.exp(-t/(.036 if stone else .048))*smooth(t/.003)
    x=body*.55+low_thud(t,rng.uniform(78,115),.032)*.47
    # Heel, then toe: clustered low-energy grains make a grounded double action.
    toe=rng.uniform(.075,.115)
    count=20 if stone else 13
    for i in range(count):
        start=rng.uniform(.007,.052) if i<count//2 else toe+rng.uniform(-.020,.060)
        duration_grain=rng.uniform(.006,.019) if stone else rng.uniform(.012,.035)
        tg=np.arange(max(8,round(duration_grain*sr)))/sr
        grain=noise(len(tg),sr,rng,900 if stone else 420,6900 if stone else 3600)
        grain*=smooth(tg/.0013)*np.exp(-tg/(duration_grain*.25))*smooth((duration_grain-tg)/.003)
        add(x,grain,start,sr,rng.uniform(.025,.105) if stone else rng.uniform(.018,.070))
    # Short scraping / foliage compression bed with irregular amplitude.
    texture=noise(len(t),sr,rng,1350 if stone else 620,6100 if stone else 4200,pink=.10)
    window=smooth((t-.035)/.023)*smooth((duration-.025-t)/.075)
    window*=np.exp(-np.maximum(0,t-.045)/(.075 if stone else .102))
    irregular=.68+.20*np.sin(TAU*rng.uniform(23,41)*t+rng.uniform(0,TAU))
    x+=texture*window*irregular*(.125 if stone else .175)
    # A quiet toe landing is more organic than an isolated noise burst.
    tt=np.maximum(0,t-toe)
    toe_body=noise(len(t),sr,rng,80,950 if stone else 710)
    toe_env=np.where(t>=toe,np.exp(-tt/.030)*smooth(tt/.002),0)
    x+=toe_body*toe_env*.17
    return x


def environment(sr,rng,duration=20.0):
    n=round(duration*sr);t=np.arange(n)/sr
    common=noise(n,sr,rng,80,1750,pink=.52)
    broad=[]
    gust=.71+.19*np.sin(TAU*t/duration+.9)+.10*np.sin(TAU*3*t/duration+2.0)
    for ch in range(2):
        side=noise(n,sr,rng,120,2050,pink=.46)
        leaves=noise(n,sr,rng,1500,5600,pink=.10)
        flutter=.48+.26*np.sin(TAU*7*t/duration+ch*.65)+.15*np.sin(TAU*17*t/duration+1.4)
        air=(.76*common+.32*side)*gust
        broad.append(.76*air+.075*leaves*flutter)
    return np.column_stack(broad)


def pad(chord,length,sr,rng):
    t=np.arange(round(length*sr))/sr
    env=smooth(t/1.25)*smooth((length-t)/2.0)
    x=np.zeros((len(t),2))
    for i,note in enumerate(chord):
        f=hz(note);phase=rng.uniform(0,TAU)
        for ch,sign in enumerate((-1,1)):
            p=TAU*f*2**(sign*(2.5+i*.35)/1200)*t+phase
            x[:,ch]+=(np.sin(p)+.12*np.sin(2*p)+.025*np.sin(3*p))*env/len(chord)
    return x


def bell(note,length,sr):
    t=np.arange(round(length*sr))/sr
    phase=TAU*hz(note)*t
    x=np.sin(phase+.18*np.sin(2.002*phase)*np.exp(-t/.16))*np.exp(-t/.64)
    x+=.07*np.sin(2.001*phase)*np.exp(-t/.15)
    return x*smooth(t/.012)*smooth((length-t)/.35)


def music(sr,rng,bpm=100):
    beat=60/bpm;duration=32*beat
    n=round(duration*sr)
    x=np.zeros((n,2))
    chords=[[50,57,60,64,65],[43,55,59,62,64],[46,57,62,64,65],[50,57,59,62,64]]
    for i,chord in enumerate(chords):
        circular_add(x,pad(chord,8*beat+1.6,sr,rng),i*8*beat,sr,.30)
    melody=[(4,69,.13,-.28),(10,76,.09,.26),(18,77,.11,-.10),(26,76,.10,.30),(29,74,.08,-.25)]
    melodic=np.zeros_like(x)
    for when,note,vel,p in melody:
        circular_add(melodic,pan(bell(note,2.3,sr),p),when*beat,sr,vel)
    x+=melodic
    for repeats in range(1,5):
        x+=np.roll(melodic[:,::-1] if repeats%2 else melodic,round(beat*.75*repeats*sr),axis=0)*.24*.51**(repeats-1)
    # Very quiet, periodic early diffusion; no endpoint fade that would expose a seam.
    dry=x.copy()
    for delay,amount in ((.067,.065),(.113,.051),(.193,.030),(.317,.020)):
        x+=np.roll(dry[:,::-1],round(delay*sr),axis=0)*amount
    return x


def interaction(kind,sr,rng):
    duration={'confirm':.55,'discovery':1.65,'soft_impact':.62}[kind]
    n=round(duration*sr);t=np.arange(n)/sr
    if kind=='soft_impact':
        x=.68*low_thud(t,69,.075)
        puff=noise(n,sr,rng,160,1650,pink=.10)
        x+=.14*puff*np.exp(-t/.043)*smooth(t/.004)
        return x
    x=np.zeros(n)
    events=[(0,74,.55),(.105,81,.34)] if kind=='confirm' else [(0,69,.40),(.17,76,.31),(.38,81,.24)]
    for when,note,level in events:
        length=min(1.2,duration-when)
        add(x,bell(note,length,sr),when,sr,level)
    return x


def db(value):return float(20*np.log10(max(1e-12,float(value))))


def finish(x,peak,looping,sr):
    if x.ndim==1:x=x[:,None]
    x=x-np.mean(x,axis=0)
    if not looping:
        t=np.arange(len(x))/sr
        # Never abruptly truncate a synthesized transient.
        window=smooth(t/.0015)*smooth((len(x)/sr-t)/min(.055,len(x)/sr*.20))
        x*=window[:,None]
        x[:8]=0;x[-16:]=0
    x*=peak/max(1e-12,np.max(np.abs(x)))
    return x


def write24(path,x,sr,rng):
    active=(np.abs(x)>0)
    dither=(rng.random(x.shape)-rng.random(x.shape))/8388608*active
    v=np.rint(np.clip(x+dither,-1,1-1/8388608)*8388608).astype(np.int32)
    b=np.empty((*v.shape,3),dtype=np.uint8)
    for i in range(3):b[:,:,i]=(v>>(8*i))&255
    with wave.open(str(path),'wb') as f:
        f.setnchannels(x.shape[1]);f.setsampwidth(3);f.setframerate(sr);f.writeframes(b.tobytes())


def stats(x,sr,looping):
    report={'peak_dbfs':db(np.max(np.abs(x))),'rms_dbfs':db(np.sqrt(np.mean(x*x))),
            'dc_offset':[float(v) for v in np.mean(x,axis=0)],
            'finite':bool(np.all(np.isfinite(x))),
            'clipped_samples':int(np.count_nonzero(np.abs(x)>=1))}
    if looping:
        jump=np.abs(x[0]-x[-1])
        internal=np.abs(np.diff(x,axis=0))
        report['loop_boundary']={
            'wrap_step_linear_per_channel':[float(v) for v in jump],
            'interior_step_p999_per_channel':[float(v) for v in np.quantile(internal,.999,axis=0)],
            'wrap_step_within_interior_p999':bool(np.all(jump<=np.quantile(internal,.999,axis=0))),
            'head_tail_rms_difference_db':db(np.sqrt(np.mean(x[:round(sr*.25)]**2)))-db(np.sqrt(np.mean(x[-round(sr*.25):]**2))),
            'method':'Circular synthesis and circular event/tail wrapping; normal adjacent-sample continuity, not repeated endpoint samples'}
    else:
        report['zero_boundary_frames']=bool(np.all(x[:8]==0) and np.all(x[-16:]==0))
    return report


def generate(output_dir,sample_rate=48000,seed=73):
    """Write 17 original WAVs and a host-import/game-playback manifest.

    Loop end markers are exclusive. gain_linear/pan are neutral host-import
    settings; suggested_game_gain_db applies later in the game audio system.
    """
    if not isinstance(sample_rate,int) or not 22050<=sample_rate<=192000:
        raise ValueError('sample_rate must be an integer from 22050 to 192000')
    if not isinstance(seed,int) or seed<0:raise ValueError('seed must be nonnegative')
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(seed);sr=sample_rate;assets=[]
    def save(identifier,name,x,peak,category,surface=None,looping=False,gain=-8,pitch=(.95,1.05),volume=(-1.5,1.0),bpm=None):
        x=finish(x,peak,looping,sr)
        filename=identifier+'.wav'
        write24(output/filename,x,sr,rng)
        item={'id':identifier,'name':name,'wav_path':filename,'path':filename,
              'native_export_target':filename,'native_export_target_name':filename,
              'gain_linear':1.0,'gain_db':0.0,'pan':0.0,
              'suggested_game_gain_db':gain,'category':category,'surface':surface,
              'sample_rate':sr,'bit_depth':24,'channels':x.shape[1],
              'frames':len(x),'duration_seconds':len(x)/sr,'looping':looping,
              'loop_start_frame':0 if looping else None,'loop_end_frame':len(x) if looping else None,
              'loop_end_frame_exclusive':True if looping else None,
              'randomization':{'pitch_multiplier_min':pitch[0],'pitch_multiplier_max':pitch[1],
                               'volume_db_min':volume[0],'volume_db_max':volume[1],
                               'avoid_immediate_repeat':category=='footstep'},
              'metrics':stats(x,sr,looping),'sha256':hashlib.sha256((output/filename).read_bytes()).hexdigest()}
        if bpm is not None:item.update({'bpm':bpm,'bars':8,'time_signature':[4,4]})
        assets.append(item)
    for surface in ('stone','grass'):
        for variant in range(6):
            save('footstep_'+surface+'_'+str(variant+1).zfill(2),
                 ('Soft Gravel / Stone' if surface=='stone' else 'Grass / Earth')+' '+str(variant+1),
                 footstep(surface,variant,sr,rng),.32 if surface=='stone' else .27,
                 'footstep',surface,gain=-8 if surface=='stone' else -6,
                 pitch=(.94,1.06),volume=(-2.0,1.0))
    save('environment_soft_wind_foliage_loop','Soft Wind & Foliage Loop',environment(sr,rng),
         .105,'environment',looping=True,gain=-5,pitch=(1.0,1.0),volume=(0.0,0.0))
    save('music_sparse_tonal_loop','Sparse Tonal Music Loop',music(sr,rng),
         .15,'music',looping=True,gain=-8,pitch=(1.0,1.0),volume=(0.0,0.0),bpm=100)
    for kind,peak,gain in [('confirm',.20,-7),('discovery',.19,-8),('soft_impact',.28,-7)]:
        save('interaction_'+kind,kind.replace('_',' ').title(),interaction(kind,sr,rng),peak,
             'interaction',gain=gain,pitch=(.99,1.01) if kind!='soft_impact' else (.96,1.04),volume=(-1.0,.5))
    manifest={'pack_name':PACK_NAME,'version':VERSION,'seed':seed,'sample_rate':sr,'audio_license':'CC0-1.0',
              'code_license':'MIT','source_provenance':'Original deterministic procedural source WAVs; not a REAPER or DAW render',
              'subjective_listening':'Unavailable; no listening assessment is claimed',
              'assets':assets,'tracks':assets,
              'integration_notes':[
                  'Host import: unity gain, center pan. Export each asset separately at the declared exact frame count.',
                  'Use native_export_target as the exported filename. Do not add a render tail or normalize.',
                  'Suggested game gains are separate from unity host-import gains; apply them once in the game audio system.',
                  'Mono footsteps and interactions can be spatialized. Environmental and music loops are stereo beds.',
                  'Loop end frames are exclusive. Loop the full file without additional crossfades or fades.',
                  'Footstep surface labels are generic. Choose variants without immediate repetition and use the bounded pitch/volume randomization.',
                  'Music is 8 bars at 100 BPM, 4/4. Keep its playback rate fixed to preserve the authored loop period.']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output_dir',nargs='?',default='source_wavs')
    p.add_argument('--sample-rate',type=int,default=48000);p.add_argument('--seed',type=int,default=73)
    args=p.parse_args();m=generate(args.output_dir,args.sample_rate,args.seed)
    print(json.dumps({'pack_name':m['pack_name'],'assets':len(m['assets']),
                      'loops':[{k:a[k] for k in ['id','frames','duration_seconds','metrics']} for a in m['assets'] if a['looping']]},indent=2))
