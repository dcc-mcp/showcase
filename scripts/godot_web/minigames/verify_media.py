#!/usr/bin/env python3
"""Encode captured real canvas + audio, decode every frame, and record exact hashes."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from media_duration import media_duration
p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);a=p.parse_args();records=[]
for source in sorted(a.evidence.glob('*-native-gameplay-with-audio.webm')):
 target=source.with_suffix('.mp4')
 source_duration=media_duration(source)
 speed=3
 assert source_duration/speed<=60
 filters="setpts=(PTS-STARTPTS)/3,drawbox=x=0:y=0:w=iw:h=36:color=black@0.7:t=fill,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='3x speed | all three gardens | original interaction audio':fontcolor=white:fontsize=18:x=16:y=8"
 subprocess.run(['ffmpeg','-v','error','-y','-threads','1','-i',str(source),'-vf',filters,'-af','atempo=1.5,atempo=2','-r','30','-c:v','libx264','-threads','1','-preset','medium','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-movflags','+faststart',str(target)],check=True)
 raw=subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(target)],text=True);meta=json.loads(raw)
 video=next(s for s in meta['streams'] if s['codec_type']=='video');audio=next(s for s in meta['streams'] if s['codec_type']=='audio')
 subprocess.run(['ffmpeg','-v','error','-threads','1','-i',str(target),'-f','null','-'],check=True)
 assert video['codec_name']=='h264' and video['width']<=1280 and audio['codec_name']=='aac'
 records.append({'file':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size,'duration_seconds':float(meta['format']['duration']),'width':video['width'],'height':video['height'],'frames':int(video['nb_frames']),'audio_codec':audio['codec_name'],'full_decode':'passed','recording':'consecutive live native Godot Web canvas frames and actual output audio captured together','listening':'not-tested','playback_speed':speed,'original_complete_recording':source.name,'original_seconds':source_duration,'editing':'Entire consecutive capture at 3x speed with pitch-preserving audio acceleration and explicit top label; no omitted game sections'})
assert len(records)==2,records
(a.evidence/'media-verification.json').write_text(json.dumps(records,indent=2));print(json.dumps(records,indent=2))
