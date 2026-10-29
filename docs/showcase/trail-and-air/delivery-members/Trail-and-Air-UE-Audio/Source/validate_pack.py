"""File-level verification only; does not claim listening or host rendering."""
import hashlib
import json
from pathlib import Path
import tempfile
import wave
import numpy as np
from game_audio_pack import generate

ROOT=Path(__file__).resolve().parent


def read24(path):
    with wave.open(str(path),'rb') as f:
        h={'channels':f.getnchannels(),'sample_rate':f.getframerate(),
           'sample_width_bytes':f.getsampwidth(),'frames':f.getnframes()}
        b=np.frombuffer(f.readframes(f.getnframes()),dtype=np.uint8).reshape(-1,3)
    x=b[:,0].astype(np.int32)|(b[:,1].astype(np.int32)<<8)|(b[:,2].astype(np.int32)<<16)
    x=(x^8388608)-8388608
    return x.reshape(-1,h['channels'])/8388608,h


def spectral_bands(x,sr):
    mono=np.mean(x,axis=1)
    p=np.abs(np.fft.rfft(mono*np.hanning(len(mono))))**2
    freq=np.fft.rfftfreq(len(mono),1/sr)
    edges=[20,100,300,1000,3000,10000,20000]
    values=np.array([np.sum(p[(freq>=lo)&(freq<hi)]) for lo,hi in zip(edges[:-1],edges[1:])])
    return values/max(np.sum(values),1e-12)


def main():
    folder=ROOT/'source_wavs'
    m=json.loads((folder/'manifest.json').read_text())
    checks=[]
    for a in m['assets']:
        path=folder/a['wav_path'];x,h=read24(path)
        assert h=={'channels':a['channels'],'sample_rate':48000,'sample_width_bytes':3,'frames':a['frames']}
        assert np.all(np.isfinite(x)) and np.max(np.abs(x))<.5
        assert hashlib.sha256(path.read_bytes()).hexdigest()==a['sha256']
        item={'id':a['id'],**h,'duration_seconds':len(x)/48000,
              'peak_dbfs':float(20*np.log10(np.max(np.abs(x)))),
              'rms_dbfs':float(20*np.log10(np.sqrt(np.mean(x*x)))),
              'finite':True,'clipped_samples':0,'sha256_matches':True}
        if a['looping']:
            assert a['loop_start_frame']==0 and a['loop_end_frame']==len(x)
            jumps=abs(x[0]-x[-1]);internal=np.quantile(abs(np.diff(x,axis=0)),.999,axis=0)
            assert np.all(jumps<internal)
            head=spectral_bands(x[:12000],48000);tail=spectral_bands(x[-12000:],48000)
            similarity=float(np.dot(head,tail)/(np.linalg.norm(head)*np.linalg.norm(tail)))
            head_rms=np.sqrt(np.mean(x[:12000]**2));tail_rms=np.sqrt(np.mean(x[-12000:]**2))
            difference=float(20*np.log10(head_rms/tail_rms))
            assert abs(difference)<3
            assert similarity>.8
            item['seam_checks']={'boundary_step_linear':jumps.tolist(),'interior_p999_step_linear':internal.tolist(),
                                 'within_normal_adjacent_sample_range':True,'head_tail_250ms_rms_difference_db':difference,
                                 'head_tail_spectral_cosine_similarity':similarity,
                                 'spectral_band_edges_hz':[20,100,300,1000,3000,10000,20000],
                                 'head_spectral_energy_fractions':head.tolist(),'tail_spectral_energy_fractions':tail.tolist(),
                                 'loop_start_frame':0,'loop_end_frame_exclusive':len(x)}
        else:
            assert np.all(x[:8]==0) and np.all(x[-16:]==0)
            item['boundary_zero_frames_verified']=True
        checks.append(item)
    with tempfile.TemporaryDirectory(prefix='repeat_check_',dir=ROOT) as tmp:
        repeated=generate(tmp)
        deterministic=all(a['sha256']==b['sha256'] for a,b in zip(m['assets'],repeated['assets']))
        assert deterministic
    assert len({a['sha256'] for a in m['assets']})==17
    result={'pack_name':m['pack_name'],'asset_count':len(checks),'sample_rate':48000,
            'format':'24-bit PCM WAV','all_checks_passed':True,'distinct_assets':17,
            'deterministic_full_pack_repeat':deterministic,
            'subjective_listening':'Unavailable; no listening assessment claimed',
            'provenance':'Source-file checks only. No DAW or REAPER render is claimed.',
            'assets':checks}
    (ROOT/'signal_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'assets':len(checks),'all_checks_passed':True,'deterministic':deterministic,
                      'loops':[a for a in checks if 'seam_checks' in a]},indent=2))

if __name__=='__main__':main()
