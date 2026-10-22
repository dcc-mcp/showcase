#!/usr/bin/env python3
"""Actual audio-only source lifecycle diagnosis; NEVER full-game qualification."""
from __future__ import annotations
import argparse, contextlib, gzip, json, math, os, signal, subprocess, sys, threading, time
from pathlib import Path
from http.server import ThreadingHTTPServer
from check_audio_observer_browser import fixture_resources, handler_for, file_hash, save_report

VERSION='Google Chrome 155.0.8059.39'
BINARY_SHA='9bfb381296dffe75f3419d07b6cc64525105ed117d1453a4ef3b291cb97d2b58'
TOTAL_SECONDS=120
WORK_SECONDS=115
CONTEXT_SECONDS=96
SOURCE_SHA={'web_audio.js': 'c68f8578245319f6ea5bb93a88e9a0d0564a47b5f6589af5ddf0a4b8c158a36c', 'assets/audio/tidekeeper-loop.ogg': '8e6c858574496d6f9c903224626fa98f8beb921fbfe926bd79af24caefd4ba9a', 'assets/audio/chart_read.wav': 'afe98709f197693e2d7c439c21a7038060100efcd911f1f6f5a6019f0089b7d6', 'assets/audio/key_pickup.wav': '93ffb7ae211d62d47665e61955f7460b5cd11719f62098c46fe4eb5fc8e531bb', 'assets/audio/pearl_pickup.wav': '8cfb5f2f1b41d1c3c7a51cc6dcb494b532ab3af23cdeb994a70ff3c9df3b92a7', 'assets/audio/beacon_resolve.wav': '276f3af29fdb90306e355f0858e4f6a94a0a5e3ff3b6ab973ad1624d0f300b76'}
CYCLES=8
DURATIONS=(.72,1.05,1.65,4.8)
SCOPE='Source-only real Chrome audio diagnostic; not gameplay/full acceptance or an intermittent defect fix'

def verify_browser(value):
    if value.get('executable_version')!=VERSION or value.get('sha256')!=BINARY_SHA:
        raise ValueError('Exact original Chrome version/binary mismatch; no playback')

def verify_health(value):
    if value.get('errors') or value.get('history_overflow') is not False:
        raise ValueError('Actual audio observer failed: '+str(value.get('errors')))
    contexts=value.get('contexts')
    if not isinstance(contexts,list) or len(contexts)!=1: raise ValueError('Ambiguous actual context')
    c=contexts[0]
    clock=c.get('context_time')
    if type(clock) not in (int,float) or not math.isfinite(clock) or clock<0: raise ValueError('Invalid context clock')
    if clock>CONTEXT_SECONDS: raise TimeoutError('96s context ceiling')
    meters=c.get('meters',[])
    if len(meters)!=3 or any(m.get('status')!='ready' or m.get('overflow') is not False for m in meters):
        raise ValueError('Actual meter not ready; no further stimulus')
    return c

def check_deadline(start, now):
    if now-start>=WORK_SECONDS: raise TimeoutError('115s work ceiling')

def validate_cue_state(state,index):
    if state.get('status')!='ready' or state.get('context_state')!='running': raise ValueError('Original backend not running')
    if state.get('cue_counts')!=[int(i<=index) for i in range(4)] or state.get('cue_playing') is not False:
        raise ValueError('Original cue did not naturally end / count mismatch')

def resources_for(source):
    resources,hashes=fixture_resources(source)
    html=resources['/'][0].decode()
    buttons=''.join(f'<button id="cue{i}" onclick="TidalWebAudio.playCue({i})">Cue {i}</button>' for i in range(4))
    buttons+='<button id="reset" onclick="TidalWebAudio.resetCues()">Reset ended cue counts</button>'
    html=html.replace('</body>',buttons+'</body>').encode();resources['/']=(html,'text/html; charset=utf-8')
    import hashlib
    hashes['fixture.html']={'sha256':hashlib.sha256(html).hexdigest(),'bytes':len(html)}
    return resources,hashes

def worker(args):
    from playwright.sync_api import sync_playwright
    from external_chrome import OwnedChromeProfile, external_chrome
    from capture_browser import audio_probe_init_script, browser_executable, bounded_cdp, passive_evaluate, capture_audio_snapshot, validate_browser_arguments
    from audio_thread import meter_stream
    from audio_source_contract import validate_cue_pcm
    report={'schema':1,'scope':SCOPE,'passed':False,'qualifies_full_game':False,'stage':'preflight','stimuli':[]}
    out=Path(args.output); server=None; thread=None; page=None; failures=[]; start=time.monotonic()
    def save(): save_report(out,report)
    def retain(name,value):
        p=out/(name+'.json.gz')
        with gzip.open(p,'wt',encoding='utf-8') as f: json.dump(value,f,allow_nan=False)
        report.setdefault('snapshots',{})[name]={'path':p.name,'sha256':file_hash(p),'bytes':p.stat().st_size};save()
    def health():
        check_deadline(start,time.monotonic())
        if failures: raise RuntimeError('Browser errors: '+str(failures))
        return verify_health(passive_evaluate(page,'() => __tidalAudio.health()'))
    def pause(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            health();page.wait_for_timeout(min(1000,max(1,(end-time.monotonic())*1000)))
        health()
    def click(selector):
        health();page.locator(selector).click(timeout=3000)
        report['stimuli'].append({'selector':selector,'method':'real browser mouse click','wall_elapsed':time.monotonic()-start});save()
    save()
    try:
        browser=browser_executable(args.chromium);browser['sha256']=file_hash(browser['executable_path']);report['browser']=browser;save();verify_browser(browser)
        resources,report['original_source']=resources_for(Path(args.source))
        if any(report['original_source'].get(n,{}).get('sha256')!=sha for n,sha in SOURCE_SHA.items()): raise ValueError('Original production source hash mismatch')
        ci=Path(__file__).resolve().parent
        report['observer_source_sha256']={n:file_hash(ci/n) for n in ['audio_probe.js','audio_meter_worklet.js','diagnose_audio_lifecycle.py','external_chrome.py']}
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(resources));thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.05},daemon=True);thread.start()
        with sync_playwright() as pw, contextlib.ExitStack() as stack:
            profile=stack.enter_context(OwnedChromeProfile());report['owned_browser']={}
            b,context=stack.enter_context(external_chrome(pw,browser['executable_path'],report=report['owned_browser'],profile=profile,timeout=5,headed=False))
            if b.version!='155.0.8059.39': raise ValueError('Runtime version mismatch')
            report['browser']['runtime_version']=b.version
            context.add_init_script(script=audio_probe_init_script());page=context.new_page();page.set_default_timeout(3000)
            page.on('pageerror',lambda e:failures.append(str(e)))
            page.on('console',lambda m: failures.append(m.text) if m.type=='error' else None)
            session=context.new_cdp_session(page)
            command=bounded_cdp(session,'Browser.getBrowserCommandLine',timeout=3)['arguments'];validate_browser_arguments(command);report['browser']['arguments']=command
            bounded_cdp(session,'detach',timeout=2)
            try:
                response=page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='domcontentloaded',timeout=5000)
                if response is None or response.status!=200: raise ValueError('Fixture HTTP failure')
                report['observer_ready']=passive_evaluate(page,'async () => {if(!await prepared) throw Error(TidalWebAudio.getState()); return __tidalAudio.ready();}')
                baseline=capture_audio_snapshot(page);retain('baseline',baseline)
                if baseline['starts'] or baseline['contexts'][0]['context_time']!=0 or baseline['contexts'][0]['state']!='suspended': raise ValueError('Unexpected pre-input playback')
                click('#begin');pause(2)
                report['stage']='cue-source-lifecycle';save()
                for cycle in range(CYCLES):
                    if cycle: click('#reset')
                    for index,duration in enumerate(DURATIONS):
                        click('#cue'+str(index));pause(duration+.35)
                        state=json.loads(passive_evaluate(page,'() => TidalWebAudio.getState()'))
                        validate_cue_state(state,index)
                    report['completed_cycles']=cycle+1;save()
                final=capture_audio_snapshot(page);retain('final',final)
                health();c=final['contexts'][0]
                for stream in c['audio_thread']['streams']: meter_stream(c,stream['source'])
                music=[v for v in final['starts'] if v['name']=='music'];cues=[v for v in final['starts'] if v['name']!='music']
                if len(music)!=1 or len(cues)!=32: raise ValueError('Real source count mismatch')
                report['cue_pcm']=[validate_cue_pcm(final,v,c) for v in cues]
                if c['context_time']<64: raise ValueError('Insufficient actual context span')
                report['context_seconds']=c['context_time'];report['music_source_id']=music[0]['id']
                report['normal_close']=profile.close_normally(bounded_cdp,timeout=3)
                report.update(passed=True,status='completed_without_reproduction',stage='complete')
            except Exception:
                try: retain('failure',passive_evaluate(page,'() => ({audio:__tidalAudio.snapshot(),state:TidalWebAudio.getState()})'))
                except Exception as e: report['diagnostic_error']=repr(e)
                raise
    except Exception as e: report.update(passed=False,status='failed',error=repr(e))
    finally:
        try:
            if server: server.shutdown();server.server_close()
            if thread: thread.join(timeout=2)
            if thread and thread.is_alive(): raise RuntimeError('Owned HTTP thread cleanup uncertain')
        except Exception as e: report.update(passed=False,status='failed',cleanup_error=repr(e))
        report['elapsed_seconds']=time.monotonic()-start;report['browser_errors']=failures;save()
    return 0 if report['passed'] else 1

def owned_identity(pid):
    # Linux hosted runner only. Identity is captured while our child is alive.
    fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'pgrp':int(fields[2]),'session':int(fields[3]),'starttime':int(fields[19])}

def terminate_live_owned(proc,identity):
    result={'signal_sent':False,'wait_completed':False,'uncertain':False}
    if proc.poll() is not None:
        result['wait_completed']=True
        return result  # Never signal/probe a reaped leader's historical PGID.
    try:
        current=owned_identity(proc.pid)
        if (identity is None or current!=identity or current['pgrp']!=proc.pid
                or current['session']!=proc.pid):
            result.update(uncertain=True,reason='Live worker identity/session not verified')
            return result
        # Recheck owned Popen liveness immediately before the verified session signal.
        if proc.poll() is not None:
            result['wait_completed']=True
            return result
        os.killpg(proc.pid,signal.SIGKILL);result['signal_sent']=True
        result['exit_code']=proc.wait(timeout=2);result['wait_completed']=True
        result['uncertain']=True  # Individual descendant termination is not certified.
        result['descendants']='Signal sent only while verified owned leader alive; individual descendant exits not certified'
    except (OSError,ValueError,IndexError,subprocess.TimeoutExpired) as e:
        result.update(uncertain=True,reason=repr(e))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--chromium',required=True);p.add_argument('--source',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    if args.worker: return worker(args)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False);start=time.monotonic();proc=None;error=None;code=None;identity=None;termination=None
    with (out/'worker.log').open('wb') as log:
        try:
            proc=subprocess.Popen([sys.executable,__file__,'--worker','--chromium',args.chromium,'--source',args.source,'--output',args.output],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try: identity=owned_identity(proc.pid)
            except (OSError,ValueError,IndexError): pass
            code=proc.wait(timeout=WORK_SECONDS)
        except Exception as e:
            error=repr(e)
            if proc is not None: termination=terminate_live_owned(proc,identity)
    try: report=json.loads((out/'receipt.json').read_text())
    except (OSError,ValueError): report={'scope':SCOPE,'passed':False,'qualifies_full_game':False}
    if error or code!=0 or time.monotonic()-start>TOTAL_SECONDS: report.update(passed=False,supervisor_error=error,worker_exit_code=code)
    report['owned_worker_wait_completed']=proc is not None and proc.poll() is not None
    report['owned_worker_identity']=identity;report['emergency_termination']=termination
    report['cleanup_scope']='Normal native cleanup is recorded by owned Chrome wrapper; never signal a reaped historical PGID'
    if termination and termination['uncertain']: report.update(passed=False,cleanup_uncertain=True)
    report['total_seconds']=time.monotonic()-start;report['maximum_seconds']=TOTAL_SECONDS;save_report(out,report);print(json.dumps(report))
    return 0 if report.get('passed') else 1
if __name__=='__main__': raise SystemExit(main())
