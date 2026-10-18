"""Common physical-input test plan; observers may never mutate game state."""
from __future__ import annotations
import math
import time


def validate_state(state):
    if state.get('schema') != 1 or type(state.get('sample_id')) is not int or state['sample_id'] <= 0:
        raise ValueError('Missing fresh schema-1 runtime state receipt')
    if type(state.get('physics_frame')) is not int or state['physics_frame'] <= 0:
        raise ValueError('Missing actual engine physics frame counter')
    if state.get('language') not in ('en','zh') or type(state.get('paused')) is not bool:
        raise ValueError('Missing language/pause state')
    position = state.get('hero', {}).get('position')
    if not isinstance(position, list) or len(position) != 3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in position):
        raise ValueError('Hero position must have three finite coordinates')
    if not isinstance(state.get('ui', {}).get('controls'), dict):
        raise ValueError('Missing visible UI control geometry')
    return state


def control_center(state, key, viewport, require_enabled=True):
    control = state['ui']['controls'].get(key)
    if not isinstance(control, dict) or (require_enabled and control.get('enabled', True) is not True):
        raise ValueError('Actual enabled control is unavailable: ' + key)
    values = [control.get(k) for k in ('x','y','w','h')]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
        raise ValueError('Invalid control geometry: ' + key)
    x,y,w,h = values
    if w < 1 or h < 1 or x < 0 or y < 0 or x+w > viewport[0]+1 or y+h > viewport[1]+1:
        raise ValueError('Visible control lies outside viewport: ' + key)
    return x+w/2, y+h/2


class InputPlan:
    def __init__(self, observe, click, key, pause, viewport, screenshot, report):
        self.observe, self.click, self.key, self.pause = observe, click, key, pause
        self.viewport, self.screenshot, self.report = viewport, screenshot, report

    def current(self):
        return validate_state(self.observe())

    def wait(self, predicate, message, after=0, seconds=12):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            state = self.current()
            if state['sample_id'] > after and predicate(state):
                self.report.setdefault('checks', []).append({'name':message,'state':state})
                return state
            self.pause(.1)
        raise TimeoutError(message)

    def tap(self, key):
        state = self.current()
        x,y = control_center(state,key,self.viewport)
        self.click(x,y)
        return state

    def gate(self, touch=False):
        state = self.current()
        if 'start' in state['ui']['controls']:
            self.tap('start')
            state = self.wait(lambda s:'start' not in s['ui']['controls'],'start menu dismissed',state['sample_id'])
        self.screenshot('initial-en' if state['language']=='en' else 'initial-zh')
        if state['paused']:
            self.tap('pause')
            state = self.wait(lambda s:not s['paused'],'resume before input gate',state['sample_id'])
        before = state['hero']['position']
        if touch:
            # Touch goes to terrain through Chromium's touch route. The target is
            # above the bottom HUD and outside the central Athena core.
            self.click(self.viewport[0]*.68,self.viewport[1]*.46)
            self.pause(1.3)
        else:
            self.key('d',True)
            try:
                self.pause(.9)
            finally:
                self.key('d',False)
        state = self.wait(lambda s:math.dist(s['hero']['position'],before)>.04,
                          'actual touch hero movement' if touch else 'actual keyboard hero movement',state['sample_id'])
        old_language=state['language']; self.tap('language')
        state=self.wait(lambda s:s['language']!=old_language,'actual language button',state['sample_id'])
        self.screenshot('language-'+state['language'])
        before_pause=state['paused']; self.tap('pause')
        state=self.wait(lambda s:s['paused']!=before_pause,'actual pause button',state['sample_id'])
        self.screenshot('paused-'+state['language'])
        self.tap('resume' if 'resume' in state['ui']['controls'] else 'pause')
        state=self.wait(lambda s:not s['paused'],'actual resume button',state['sample_id'])
        music=state.get('music',{})
        if type(music.get('muted')) is not bool:
            raise ValueError('Missing actual music mute observation')
        old_mute=music['muted']; self.tap('mute')
        state=self.wait(lambda s:s.get('music',{}).get('muted') is not old_mute,'actual mute button',state['sample_id'])
        self.tap('mute')
        state=self.wait(lambda s:s.get('music',{}).get('muted') is old_mute,'actual unmute button',state['sample_id'])
        self.screenshot('input-gate')
        self.report['input_image_gate_passed']=True
        return state

    def world_click(self, x, z):
        state=self.current()
        projected={p['id']:p for p in state['ui'].get('pads',[])}
        positions={p['id']:p['position'] for p in state.get('pads',[])}
        ids=(0,1,3)
        if any(i not in projected or i not in positions for i in ids):
            raise ValueError('Read-only actual pad projections are required for terrain targeting')
        def vector(value):
            return (value['x'],value['z']) if isinstance(value,dict) else (value[0],value[2])
        a,b,c=[vector(positions[i]) for i in ids]
        determinant=(b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1])
        if abs(determinant)<.001:raise ValueError('Degenerate projection basis')
        u=((x-a[0])*(c[1]-a[1])-(z-a[1])*(c[0]-a[0]))/determinant
        v=((b[0]-a[0])*(z-a[1])-(b[1]-a[1])*(x-a[0]))/determinant
        pa,pb,pc=[projected[i] for i in ids]
        sx=pa['x']+u*(pb['x']-pa['x'])+v*(pc['x']-pa['x'])
        sy=pa['y']+u*(pb['y']-pa['y'])+v*(pc['y']-pa['y'])
        if not (5<sx<self.viewport[0]-5 and 120<sy<self.viewport[1]-(250 if self.viewport[0]<500 else 150)):
            return False
        self.click(sx,sy)
        return True

    def prepare_combat(self):
        state=self.current()
        if state['language']!='en':
            self.tap('language');state=self.wait(lambda s:s['language']=='en','English controls restored',state['sample_id'])
        self.tap('equipment')
        state=self.wait(lambda s:s['ui'].get('shop')=='equipment','equipment shop opened',state['sample_id'])
        before=state['hero']['equipment']['blade'];gold=state['gold'];self.tap('item_blade')
        state=self.wait(lambda s:s['hero']['equipment']['blade']==before+1 and s['gold']<gold,'actual equipment purchased',state['sample_id'])
        self.screenshot('equipment');self.tap('close')
        self.pause(.4);state=self.current()
        candidates=[p for p in state['ui'].get('pads',[]) if 20<p['x']<self.viewport[0]-20 and 130<p['y']<self.viewport[1]-(260 if self.viewport[0]<500 else 155)]
        if not candidates:raise RuntimeError('No visible support pad in the current real viewport')
        pad=next((p for p in candidates if p['id']==2),candidates[0]);self.click(pad['x'],pad['y'])
        state=self.wait(lambda s:s.get('selected_pad')==pad['id'] and 'tower_sunbow' in s['ui']['controls'],'support pad selected',state['sample_id'])
        self.tap('tower_sunbow')
        state=self.wait(lambda s:any(t['id']==pad['id'] for t in s.get('towers',[])),'actual support tower built',state['sample_id'])
        self.tap('upgrade')
        state=self.wait(lambda s:any(t['id']==pad['id'] and t['level']==2 for t in s.get('towers',[])),'actual support tower branch upgraded',state['sample_id'])
        # Repeated unavailable upgrade is a real click; gold/level must not change.
        previous_gold=state['gold']
        x,y=control_center(state,'upgrade',self.viewport,require_enabled=False)
        self.click(x,y);self.pause(.4)
        repeated=self.current()
        if repeated['gold']!=previous_gold or not any(t['id']==pad['id'] and t['level']==2 for t in repeated['towers']):
            raise RuntimeError('Invalid repeated upgrade changed the game state')
        self.report['invalid_repeated_upgrade']={'before':state,'after':repeated}
        self.tap('sell')
        state=self.wait(lambda s:not any(t['id']==pad['id'] for t in s['towers']) and s['gold']>previous_gold,'actual tower sold with refund',repeated['sample_id'])
        self.tap('tower_sunbow')
        state=self.wait(lambda s:any(t['id']==pad['id'] for t in s['towers']),'support tower rebuilt after selling',state['sample_id'])
        self.tap('close');self.pause(.4);self.world_click(-8,2);self.pause(1.5)
        self.screenshot('prepared-defense')

    def combat(self, seconds=180):
        self.prepare_combat()
        state=self.current();initial=state
        if state.get('skills',{}).get('r',{}).get('unlocked') is not False:
            raise ValueError('New level-one hero should start with locked ultimate')
        self.report['ultimate_initially_locked']=True
        self.tap('start_wave')
        state=self.wait(lambda s:s.get('wave',0)>initial.get('wave',0),'wave began through actual button',state['sample_id'])
        self.wait(lambda s:len(s.get('enemies',[]))>0,'actual enemies spawned',seconds=20)
        self.screenshot('combat')
        casts=set();deadline=time.monotonic()+seconds;last_move=0;last_shot=0
        while time.monotonic()<deadline:
            state=self.current()
            if state.get('phase') in ('victory','defeat'):
                if state['phase']=='defeat':raise RuntimeError('Actual two-wave defense route lost the core')
                break
            if state.get('phase')=='build' and state.get('wave',0)<2:
                self.tap('start_wave');self.pause(.3);continue
            for index,skill in enumerate(('q','e','r'),1):
                control=state['ui']['controls'].get('skill_'+str(index),{})
                if control.get('enabled') and state.get('enemies'):
                    self.tap('skill_'+str(index));casts.add(skill);self.pause(.15)
            if time.monotonic()-last_move>2.5 and not state['hero'].get('dead'):
                # Intercept enemies with actual terrain clicks. Screen projection
                # is derived only from observed current orthographic pad points.
                enemies=state.get('enemies',[])
                if enemies:
                    target=max(enemies,key=lambda e:e.get('progress',0));pos=target['position']
                    self.world_click(pos[0],pos[2])
                last_move=time.monotonic()
            if state['hero'].get('level',1)>=3 and 'r' in casts and state.get('wave',0)>=2:
                self.report['combat_observed']={'before':initial,'after':state,'cast_skills':sorted(casts),'scope':'Two-wave hero progression, not eight-wave victory proof'}
                break
            self.pause(.2)
        else:raise TimeoutError('Two-wave hero/ultimate progression was not established with actual inputs')
        if casts!={'q','e','r'}:raise RuntimeError('All three abilities were not used through real controls')
        self.screenshot('combat-progress')
        old=self.current()
        if 'restart' not in old['ui']['controls']:
            self.tap('pause');self.pause(.3)
        self.tap('restart');self.pause(.3);state=self.current()
        if 'confirm_restart' in state['ui']['controls']:self.tap('confirm_restart')
        self.wait(lambda s:s.get('wave',0)==0 and len(s.get('enemies',[]))==0 and len(s.get('towers',[]))==0,'actual restart reset',old['sample_id'])
        self.screenshot('restart')
