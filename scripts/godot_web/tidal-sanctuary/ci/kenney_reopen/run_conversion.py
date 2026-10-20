"""Frozen review-only coordinator. Execution requires a separately approved native window.

A fresh Python process per phase creates a distinct server, registry, project,
editor and Xvfb. No production assets are replaced. No request is retried.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import signal
import time
from run_preflight import durable_new, sha
ROOT=pathlib.Path(__file__).resolve().parent

def verify_freeze():
    freeze=json.loads((ROOT/'conversion-freeze.json').read_text())
    for name,digest in freeze['files'].items():
        if sha((ROOT/name).read_bytes()) != digest: raise ValueError('Frozen input changed: '+name)

def run(args):
    verify_freeze()
    if args.output.exists(): raise FileExistsError('Fresh output required; partial work is never replayed')
    args.output.mkdir()
    lifecycle=[]
    cancelled=False
    cleaning=False
    def cancel(signum,frame):
        nonlocal cancelled
        if cancelled:return
        cancelled=True
        if cleaning:return
        raise InterruptedError('Coordinator cancellation; waiting for owned session cleanup')
    previous={sig:signal.signal(sig,cancel) for sig in (signal.SIGTERM,signal.SIGINT)}
    report={'passed':False,'native_execution':True,'production_assets_replaced':False,'independent_session_reopen':False}
    try:
        for phase in ('convert','reopen'):
            session=args.output/phase
            command=[sys.executable,str(ROOT/'run_conversion_session.py'),'--phase',phase,'--output',str(session),'--ci',str(args.ci),'--archive',str(args.archive),'--baseline',str(args.baseline),'--godot',args.godot,'--xvfb',args.xvfb]
            if phase == 'reopen': command += ['--previous',str(args.output/'convert')]
            record={'phase':phase,'command':command,'start_monotonic_ns':time.monotonic_ns()}
            durable_new(args.output/(phase+'-launch.json'),json.dumps(record,indent=2).encode())
            with (args.output/(phase+'-caller.log')).open('x') as log:
                child=None
                try:
                    # Acquisition is signal-atomic: queued cancellation is
                    # delivered only after the child reference is owned and
                    # inside the cleanup-covered try. Child unmasks after its
                    # own cancellation handlers and cleanup scope are ready.
                    old_mask=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGTERM,signal.SIGINT})
                    try:
                        child=subprocess.Popen(command,stdout=log,stderr=log)
                        record['pid']=child.pid
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK,old_mask)
                    record['exit_code']=child.wait()
                except BaseException:
                    cleaning=True
                    # The session owns and actually waits for its editor/Xvfb.
                    # Never kill only Python and orphan those native children.
                    # If teardown stalls, remain waiting and do not start reopen.
                    if child is not None:
                        if child.poll() is None:child.send_signal(signal.SIGTERM)
                        child.wait()
                        result_path=session/'result.json'
                        record['cancellation_cleanup']=json.loads(result_path.read_text()) if result_path.is_file() else {'cleanup_unproven':True}
                    raise
                finally:
                    record['end_monotonic_ns']=time.monotonic_ns()
                    record['terminal_exit_code']=child.poll() if child is not None else None
                    lifecycle.append(record)
                    durable_new(args.output/(phase+'-wait.json'),json.dumps(record,indent=2).encode())
            if record['exit_code'] != 0: raise RuntimeError(phase+' caller failed; preserve all files, do not replay')
            result=json.loads((session/'result.json').read_text())
            if result.get('passed') is not True or result.get('cleanup_errors') != [] or result.get('editor_exit_code') is None or result.get('xvfb_exit_code') is None:
                raise RuntimeError(phase+' native validation/cleanup incomplete')
        if lifecycle[0]['end_monotonic_ns'] >= lifecycle[1]['start_monotonic_ns']:
            raise RuntimeError('Native session overlap')
        report.update(passed=True,independent_session_reopen=True,converted=4,reopened=4)
    except BaseException as exc:
        report['error']=repr(exc);raise
    finally:
        report['lifecycle']=lifecycle
        report['cancelled']=cancelled
        try:durable_new(args.output/'conversion-result.json',json.dumps(report,indent=2).encode())
        finally:
            for sig,handler in previous.items():signal.signal(sig,handler)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output','ci','archive','baseline'): p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--godot',required=True);p.add_argument('--xvfb',default='Xvfb')
    args=p.parse_args()
    for name in ('output','ci','archive','baseline'): setattr(args,name,getattr(args,name).resolve())
    run(args)
if __name__ == '__main__': main()
