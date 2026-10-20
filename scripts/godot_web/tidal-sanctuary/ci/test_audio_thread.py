"""Deterministic fabricated fixtures test rejection logic; never live PCM proof."""
import copy
import unittest
from audio_thread import meter_stream, pcm_interval, pcm_signal, marked_pcm_window


def meter_fixture(seconds=2.5, rms=.01, source=None, rate=8000):
    frames = round(rate / 10)
    windows = []
    for index in range(round(seconds * 10)):
        square = rms * rms * frames
        windows.append({"sequence":index+1,"start_frame":index*frames,"end_frame":(index+1)*frames,
            "frames":frames,"channels":2,"samples":frames*2,"channel_samples":[frames,frames],
            "square_sum":2*square,"channel_square_sum":[square,square],"rms":rms,"channel_rms":[rms,rms],
            "peak":rms,"channel_peak":[rms,rms],"clipped_samples":0,"channel_clipped_samples":[0,0],
            "clipped_fraction":0,"complete":True,"segment":1})
    return {"schema":1,"status":"ready","sample_rate":rate,"window_frames":frames,"overflow":False,
            "errors":[],"role":"mix" if source is None else "bus","tap_id":"mix:1" if source is None else "node:"+str(source),"windows":windows,"gaps":[],"source":source,"streams":[],"graph":{"input_active":True}}


def context_fixture(seconds=2.5, rms=.01):
    return {"id":1,"state":"running","context_time":seconds,"sample_rate":8000,
            "audio_thread":meter_fixture(seconds,rms)}


def timed_fixture(seconds=2.5):
    return {'wall_ms':seconds*1000,'marks':[{'wall_ms':0,'context_times':[{'id':1,'time':0}]}],
            'pcm_cutoff':{'wall_ms':seconds*1000,'context_times':[{'id':1,'time':seconds}]},
            'pcm_barriers':[{'context':1,'tap_id':'mix:1','processed_end_frame':round(seconds*8000)}]}


class AudioThreadFixtures(unittest.TestCase):
    def test_exact_real_frame_accounting_and_signal(self):
        context=context_fixture()
        windows=pcm_interval(context,0,2.5,2)
        result=pcm_signal(windows,True)
        self.assertEqual(result['pcm_frames'],20000)
        self.assertEqual(result['pcm_windows'],25)
        self.assertEqual(result['first_frame'],0)
        self.assertEqual(result['last_frame'],20000)

    def test_zero_pcm_is_quiet_and_never_audible(self):
        windows=pcm_interval(context_fixture(rms=0),0,2.5,2)
        pcm_signal(windows,False)
        with self.assertRaises(ValueError):pcm_signal(windows,True)
        with self.assertRaises(ValueError):pcm_signal(pcm_interval(context_fixture(),0,2.5,2),False)

    def test_dropped_duplicated_reordered_overlapping_frames_fail(self):
        for mode in ('drop','duplicate','reorder','overlap','sequence','frame-count','channel-count','channel-missing'):
            context=context_fixture();windows=context['audio_thread']['windows']
            if mode=='drop':del windows[5]
            if mode=='duplicate':windows.insert(5,copy.deepcopy(windows[5]))
            if mode=='reorder':windows[5],windows[6]=windows[6],windows[5]
            if mode=='overlap':windows[5]['start_frame']-=1
            if mode=='sequence':windows[5]['sequence']+=1
            if mode=='frame-count':windows[5]['frames']-=1
            if mode=='channel-count':windows[5]['samples']-=1
            if mode=='channel-missing':windows[5]['channel_samples'][0]-=1
            with self.subTest(mode=mode),self.assertRaises(ValueError):meter_stream(context)

    def test_invalid_statistics_clipping_and_status_fail(self):
        for key,value in [('rms',float('nan')),('rms',-.1),('rms',.2),('square_sum',2),('peak',2),
                          ('clipped_samples',100),('clipped_fraction',.1),('complete',False)]:
            context=context_fixture();context['audio_thread']['windows'][4][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):meter_stream(context)
        for change in ({'status':'loading'},{'overflow':True},{'errors':['lost block']},{'sample_rate':44100},{'window_frames':100}):
            context=context_fixture();context['audio_thread'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):meter_stream(context)

    def test_no_input_is_a_gap_not_invented_silence(self):
        context=context_fixture();meter=context['audio_thread'];removed=meter['windows'].pop(5)
        meter['gaps']=[{key:removed[key] for key in ('sequence','start_frame','end_frame','frames')}|{'reason':'no-input'}]
        meter_stream(context)
        for audible in (True,False):
            with self.subTest(audible=audible),self.assertRaises(ValueError):
                pcm_signal(pcm_interval(context,0,2.5,2),audible)

    def test_pre_source_gap_is_allowed_outside_selected_pcm(self):
        context=context_fixture();meter=context['audio_thread'];removed=meter['windows'][:3];meter['windows']=meter['windows'][3:]
        meter['gaps']=[{key:item[key] for key in ('sequence','start_frame','end_frame','frames')}|{'reason':'no-input'} for item in removed]
        pcm_signal(pcm_interval(context,.3,2.5,2),True)

    def test_missing_frozen_or_future_audio_clock_fails(self):
        for change in ({'context_time':0},{'context_time':float('nan')},{'audio_thread':None}):
            context=context_fixture();context.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):meter_stream(context)

    def test_wall_and_audio_clocks_are_independently_required(self):
        context=context_fixture();snapshot=timed_fixture()
        marked_pcm_window(snapshot,context,0,2500,2,True)
        for change in ('wall-short','wrong-context','no-mark','suspended','frozen'):
            snap=copy.deepcopy(snapshot);ctx=copy.deepcopy(context);end=2500
            if change=='wall-short':end=1000;snap['wall_ms']=end
            if change=='wrong-context':snap['marks'][0]['context_times'][0]['id']=2
            if change=='no-mark':snap['marks']=[]
            if change=='suspended':ctx['state']='suspended'
            if change=='frozen':snap['marks'][0]['context_times'][0]['time']=2.4
            with self.subTest(change=change),self.assertRaises(ValueError):marked_pcm_window(snap,ctx,0,end,2,True)

    def test_delivery_delay_does_not_relabel_pcm_capture_times(self):
        context=context_fixture()
        for item in context['audio_thread']['windows']:item['delivery_ms']=100000
        result=marked_pcm_window(timed_fixture(),context,0,2500,2,True)
        self.assertEqual(result['last_frame'],20000)
        self.assertEqual(result['last_ms'],2500)

    def test_cutoff_and_barrier_fail_closed_without_delivery_backfill(self):
        for mutation in ('missing-cutoff','future-cutoff','missing-watermark','short-watermark','short-before-flush'):
            snapshot=timed_fixture();context=context_fixture()
            if mutation=='missing-cutoff':snapshot.pop('pcm_cutoff')
            if mutation=='future-cutoff':snapshot['pcm_cutoff']['context_times'][0]['time']=2.6
            if mutation=='missing-watermark':snapshot['pcm_barriers']=[]
            if mutation=='short-watermark':snapshot['pcm_barriers'][0]['processed_end_frame']-=1
            if mutation=='short-before-flush':
                # Receiving enough later PCM cannot enlarge the original cutoff.
                snapshot['pcm_cutoff']['wall_ms']=1000
                snapshot['pcm_cutoff']['context_times'][0]['time']=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                marked_pcm_window(snapshot,context,0,2500,2,True)
        snapshot=timed_fixture();snapshot['wall_ms']=100000
        result=marked_pcm_window(snapshot,context_fixture(),0,100000,2,True)
        self.assertEqual(result['last_ms'],2500)
        self.assertEqual(result['delivery_snapshot_ms'],100000)
        self.assertEqual(result['pcm_frames'],20000)

    def test_partial_pcm_is_retained_without_padding(self):
        context=context_fixture();meter=context['audio_thread'];last=meter['windows'][-1]
        for key in ('frames','samples','square_sum','end_frame'):
            if key=='end_frame':last[key]-=400
            else:last[key]/=2
        for key in ('frames','samples'):last[key]=int(last[key])
        last['channel_samples']=[400,400];last['channel_square_sum']=[.04,.04];last['complete']=False
        context['context_time']=2.45
        windows=pcm_interval(context,0,2.45,2)
        self.assertEqual(pcm_signal(windows,True)['pcm_frames'],19200)
        self.assertTrue(windows[-1]['complete'])
        self.assertFalse(meter['windows'][-1]['complete'])
        self.assertEqual(meter['windows'][-1]['frames'],400)

    def test_partial_channel_transition_at_interval_edge_is_not_padded(self):
        context=context_fixture();meter=context['audio_thread']
        first=meter['windows'][0]
        first.update({'end_frame':64,'frames':64,'channels':1,'samples':64,
            'channel_samples':[64],'square_sum':0,'channel_square_sum':[0],
            'rms':0,'channel_rms':[0],'peak':0,'channel_peak':[0],
            'channel_clipped_samples':[0],'complete':False})
        for item in meter['windows'][1:]:
            item['start_frame']-=736;item['end_frame']-=736
        context['context_time']=2.408
        selected=pcm_interval(context,0,2.408,2)
        self.assertEqual(pcm_signal(selected,True,minimum_fraction=1)['pcm_frames'],19200)
        self.assertEqual(meter['windows'][0]['frames'],64)
        # A real incomplete transition inside the required interval cannot be
        # skipped to bridge two otherwise-contiguous audible runs.
        meter['windows'][10]['complete']=False
        meter['windows'][10]['frames']-=1
        with self.assertRaises(ValueError):pcm_interval(context,0,2.408,2)

    def test_bus_meter_must_be_unique(self):
        context=context_fixture();bus=meter_fixture(source=7);context['audio_thread']['streams']=[bus]
        meter_stream(context,7)
        for streams in ([],[bus,copy.deepcopy(bus)]):
            context['audio_thread']['streams']=streams
            with self.assertRaises(ValueError):meter_stream(context,7)


if __name__=='__main__':unittest.main()
