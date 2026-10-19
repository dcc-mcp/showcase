#!/usr/bin/env python3
"""Short real X11 image/input gate first; longer native captures only with --full."""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import time
from pathlib import Path
from common import checked_godot, check_engine_log, copy_game, isolated_env, isolated_output, receipts, sha256, stop_process, write_json
from interaction import InputPlan
from media import inspect_audio, inspect_video


def image_stats(path):
    from PIL import Image, ImageStat
    with Image.open(path) as image:
        stat=ImageStat.Stat(image.convert('RGB'))
        if min(image.size)<200 or max(stat.stddev)<5:
            raise ValueError('Actual renderer image is blank or unexpectedly small')
        return {'width':image.width,'height':image.height,'stddev':stat.stddev,'sha256':sha256(path)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--godot',default='godot');p.add_argument('--full',action='store_true')
    args=p.parse_args();out=isolated_output(args.output,args.native);godot=checked_godot(args.godot)
    report={'schema':1,'passed':False,'mode':'full' if args.full else 'preview','route':'actual X11/XTest through xdotool',
            'audio_review':'not-tested; numerical rendered-audio measurement is separate from listening','checks':[],
            'limitations':['Software OpenGL is not physical GPU performance.','Preview is an image/input gate, not game completion.']}
    process=recorder=None;pressed=set();log=None
    try:
        if not os.environ.get('DISPLAY') or any(not shutil.which(x) for x in ('xdotool','ffmpeg')):
            raise RuntimeError('Real native gate requires DISPLAY, xdotool and ffmpeg; no injected-input fallback')
        project=out/'runtime-project';manifest=copy_game(args.native,project);write_json(out/'source-manifest.json',manifest)
        env=isolated_env(out/'session')
        # Fresh copied resources have no .godot import cache. Import them with
        # the real editor before a standalone runtime attempts GLB/font/audio loads.
        imported=subprocess.run([godot,'--headless','--editor','--import','--quit','--path',str(project)],
                                env=env,capture_output=True,text=True,timeout=180)
        import_log=imported.stdout+imported.stderr;(out/'import.log').write_text(import_log)
        check_engine_log(import_log)
        if imported.returncode:raise RuntimeError('Actual native resource import failed: '+str(imported.returncode))
        for entry in manifest['files']:
            if sha256(project/entry['path'])!=entry['sha256']:
                raise RuntimeError('Native resource import changed source bytes: '+entry['path'])
        report['resource_import']={'passed':True,'source_bytes_unchanged':True,
                                   'scope':'Generated import metadata/cache only'}
        log_path=out/'native.log';log=log_path.open('w')
        process=subprocess.Popen([godot,'--path',str(project),'--rendering-method','gl_compatibility','--rendering-driver','opengl3',
                                  '--audio-driver','PulseAudio' if args.full else 'Dummy','--resolution','1280x720','--position','0,0','--single-window','--fullscreen'],
                                 env=env,stdout=log,stderr=log)
        def live():
            if process.poll() is not None: raise RuntimeError('Actual Godot process exited early: '+str(process.returncode))
            text=log_path.read_text();check_engine_log(text);return text
        deadline=time.monotonic()+100
        while 'DAWNKEEP_FRAME_READY ' not in live():
            if time.monotonic()>deadline:raise TimeoutError('No actual frame_post_draw readiness')
            time.sleep(.1)
        deadline=time.monotonic()+15
        while not receipts(live()):
            if time.monotonic()>deadline:raise TimeoutError('No initial read-only state after rendered readiness')
            time.sleep(.1)
        def observe():
            values=receipts(live())
            if not values:raise ValueError('No read-only runtime state')
            return values[-1]
        def click(x,y):
            live();subprocess.run(['xdotool','mousemove','--sync',str(round(x)),str(round(y)),'click','1'],check=True,timeout=10)
            report.setdefault('events',[]).append({'type':'XTest click','x':x,'y':y})
        def key(name,down):
            subprocess.run(['xdotool','keydown' if down else 'keyup',name],check=True,timeout=10)
            (pressed.add if down else pressed.discard)(name)
            report.setdefault('events',[]).append({'type':'XTest keydown' if down else 'XTest keyup','key':name})
        def screenshot(name):
            live();time.sleep(.2);path=out/(name+'.png')
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','x11grab','-video_size','1280x720','-i',os.environ['DISPLAY'],'-frames:v','1','-threads','1',str(path)],check=True,timeout=30)
            report.setdefault('screenshots',[]).append({'name':path.name,**image_stats(path),'state':observe()})
        plan=InputPlan(observe,click,key,time.sleep,(1280,720),screenshot,report)
        plan.gate()
        write_json(out/'native.json',report) # available before long work starts
        if args.full:
            # This is an actual continuous screen recording, not a game demo.
            recorder=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','x11grab','-framerate','20','-video_size','1280x720','-i',os.environ['DISPLAY'],
                                       '-f','pulse','-i','default','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac',str(out/'native-input.mp4')])
            plan.full_desktop();stop_process(recorder);recorder=None
            subprocess.run(['ffmpeg','-v','error','-threads','1','-i',str(out/'native-input.mp4'),'-f','null','-'],check=True,timeout=90)
            report['movie']=inspect_video(out/'native-input.mp4')
            subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(out/'native-input.mp4'),'-vn','-c:a','pcm_s16le',str(out/'runtime-audio.wav')],check=True,timeout=90)
            report['captured_audio']=inspect_audio(out/'runtime-audio.wav')
        live();report['passed']=True
    except Exception as error:
        report['blocker']=str(error);raise
    finally:
        for name in pressed:
            subprocess.run(['xdotool','keyup',name],check=False)
        stop_process(recorder);stop_process(process)
        if log:log.close()
        write_json(out/'native.json',report)


if __name__=='__main__':main()
