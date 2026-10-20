"""Decode and measure actual captured media; numerical checks never imply listening."""
import json
import math
import subprocess
import wave
from array import array
from pathlib import Path
from common import sha256


def inspect_audio(path):
    path=Path(path)
    with wave.open(str(path),'rb') as stream:
        if stream.getsampwidth()!=2:raise ValueError('Audio measurement needs actual signed 16-bit PCM')
        samples=array('h',stream.readframes(stream.getnframes()))
        if not samples:raise ValueError('Captured audio has no samples')
        peak=max(abs(x) for x in samples)/32768
        rms=math.sqrt(sum(float(x)*x for x in samples)/len(samples))/32768
        if peak<.001 or rms<.00005:raise ValueError('Actual captured audio is silent or below evidence threshold')
        return {'sha256':sha256(path),'seconds':stream.getnframes()/stream.getframerate(),
                'sample_rate':stream.getframerate(),'channels':stream.getnchannels(),'peak':peak,'rms':rms,
                'listening_review':'not-tested'}


def inspect_video(path):
    subprocess.run(['ffmpeg','-nostdin','-v','error','-threads','1','-i',str(path),'-f','null','-'],check=True,timeout=180)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],text=True))
    if not any(s.get('codec_type')=='video' and s.get('width',0)>200 for s in info['streams']):
        raise ValueError('Actual recorded movie is missing a video stream')
    return {'sha256':sha256(path),'full_decode_passed':True,'probe':info,'motion_review':'not-tested'}
