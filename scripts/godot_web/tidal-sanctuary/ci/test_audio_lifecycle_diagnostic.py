import copy, json, pathlib, sys, tempfile, unittest
from unittest.mock import patch, MagicMock
import diagnose_audio_lifecycle as d

class DiagnosticContract(unittest.TestCase):
    def health(self):
        return {'errors':[],'history_overflow':False,'contexts':[{'id':1,'state':'running','context_time':80,'meters':[{'status':'ready','overflow':False} for _ in range(3)]}]}
    def test_exact_build_both_fields_required(self):
        correct={'executable_version':d.VERSION,'sha256':d.BINARY_SHA};d.verify_browser(correct)
        for key in correct:
            bad=dict(correct);bad[key]='different'
            with self.assertRaises(ValueError):d.verify_browser(bad)
    def test_failure_is_not_health(self):
        for key,val in [('errors',['actual missing frame']),('history_overflow',True)]:
            v=self.health();v[key]=val
            with self.assertRaises(ValueError): d.verify_health(v)
        v=self.health();v['contexts'][0]['meters'][0]['status']='failed'
        with self.assertRaises(ValueError):d.verify_health(v)
    def test_context_budget_finite_and_not_reset(self):
        for t in [96.001,float('nan'),-1,None]:
            v=self.health();v['contexts'][0]['context_time']=t
            with self.assertRaises((ValueError,TimeoutError)):d.verify_health(v)
        with self.assertRaises(TimeoutError):d.check_deadline(100,215)
        d.check_deadline(100,214.9)
        self.assertEqual(d.CYCLES*len(d.DURATIONS),32);self.assertEqual(d.TOTAL_SECONDS,120)
    def test_natural_ends_and_actual_counts(self):
        good={'status':'ready','context_state':'running','cue_counts':[1,1,0,0],'cue_playing':False};d.validate_cue_state(good,1)
        for key,value in [('cue_playing',True),('context_state','suspended'),('cue_counts',[1,0,0,0])]:
            v=dict(good);v[key]=value
            with self.assertRaises(ValueError): d.validate_cue_state(v,1)
    def test_html_original_api_and_no_audio_replacement(self):
        base=b'<body><script src="/web_audio.js"></script></body>'
        with patch.object(d,'fixture_resources',return_value=({'/':(base,'text/html')},{'web_audio.js':{'sha256':'original'}})):
            resources,hashes=d.resources_for(pathlib.Path('.'))
        html=resources['/'][0].decode()
        for i in range(4):self.assertIn('TidalWebAudio.playCue('+str(i)+')',html)
        self.assertIn('TidalWebAudio.resetCues()',html);self.assertNotIn('createBuffer',html)
        self.assertEqual(hashes['web_audio.js']['sha256'],'original')
    def test_normal_reaped_worker_never_signals_or_probes_old_pgid(self):
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td)/'fresh';proc=MagicMock();proc.pid=999999;proc.wait.return_value=0;proc.poll.return_value=0
            def launch(*a,**k):
                (out/'receipt.json').write_text(json.dumps({'passed':True,'qualifies_full_game':False}));return proc
            with patch.object(sys,'argv',['diagnostic','--chromium','unused','--source','unused','--output',str(out)]),patch.object(d.subprocess,'Popen',side_effect=launch),patch.object(d,'owned_identity',return_value={'pid':999999,'pgrp':999999,'session':999999,'starttime':123}),patch.object(d.os,'killpg') as kill:
                self.assertEqual(d.main(),0);kill.assert_not_called()
            report=json.loads((out/'receipt.json').read_text());self.assertTrue(report['owned_worker_wait_completed']);self.assertIsNone(report['emergency_termination'])
    def test_timeout_checks_original_identity_before_signal(self):
        proc=MagicMock();proc.pid=123;proc.poll.return_value=None;proc.wait.return_value=-9
        identity={'pid':123,'pgrp':123,'session':123,'starttime':45}
        with patch.object(d,'owned_identity',return_value=identity),patch.object(d.os,'killpg') as kill:
            result=d.terminate_live_owned(proc,identity);kill.assert_called_once_with(123,d.signal.SIGKILL)
            self.assertTrue(result['signal_sent']);self.assertTrue(result['wait_completed']);self.assertTrue(result['uncertain'])
    def test_pid_reuse_or_unknown_session_never_signals(self):
        proc=MagicMock();proc.pid=123;proc.poll.return_value=None
        identity={'pid':123,'pgrp':123,'session':123,'starttime':45}
        for actual in [dict(identity,starttime=46),dict(identity,session=2),dict(identity,pgrp=2)]:
            with patch.object(d,'owned_identity',return_value=actual),patch.object(d.os,'killpg') as kill:
                result=d.terminate_live_owned(proc,identity);kill.assert_not_called();self.assertTrue(result['uncertain'])
        proc.poll.return_value=0
        with patch.object(d,'owned_identity') as read,patch.object(d.os,'killpg') as kill:
            self.assertTrue(d.terminate_live_owned(proc,identity)['wait_completed']);read.assert_not_called();kill.assert_not_called()
    def test_cleanup_denial_is_uncertain(self):
        proc=MagicMock();proc.pid=123;proc.poll.return_value=None
        identity={'pid':123,'pgrp':123,'session':123,'starttime':45}
        with patch.object(d,'owned_identity',return_value=identity),patch.object(d.os,'killpg',side_effect=PermissionError('injected denial')):
            result=d.terminate_live_owned(proc,identity)
        self.assertTrue(result['uncertain']);self.assertFalse(result['signal_sent'])
    def test_first_error_precedes_next_stimulus(self):
        source=pathlib.Path(d.__file__).read_text()
        self.assertIn("health();page.locator(selector).click",source)
        self.assertIn("click('#cue'+str(index));pause(duration+.35)",source)
        self.assertNotIn('meter.restart',source)
    def test_workflow_diagnostic_is_opt_in_and_separate(self):
        path=pathlib.Path(__file__).parents[4]/'.github/workflows/tidal-sanctuary-preview.yml'
        if not path.is_file(): path=pathlib.Path(__file__).with_name('tidal-sanctuary-preview.yml')
        text=path.read_text()
        self.assertIn('audio_diagnostic_only:\n',text)
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' && inputs.audio_diagnostic_only && !inputs.smoke_only && !inputs.consumer_only && !inputs.vector_only }}",text)
        self.assertIn('!inputs.vector_only && !inputs.audio_diagnostic_only }}',text)
        self.assertIn('Audio source lifecycle diagnostic (NOT full acceptance)',text)
if __name__=='__main__':unittest.main()
