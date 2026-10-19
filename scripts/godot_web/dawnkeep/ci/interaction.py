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


def support_pad(state,viewport):
    positions={p['id']:p['position'] for p in state.get('pads',[])}
    candidates=[]
    for pad in state['ui'].get('pads',[]):
        if not(20<pad['x']<viewport[0]-20 and 130<pad['y']<viewport[1]-(260 if viewport[0]<500 else 155)):continue
        position=positions[pad['id']]
        point=[position['x'],position.get('y',0),position['z']] if isinstance(position,dict) else position
        # The actual game rejects construction under the hero. Keep that rule.
        if math.dist(point,state['hero']['position'])>2:candidates.append(pad)
    if not candidates:raise RuntimeError('No visible support pad clear of the hero')
    return next((p for p in candidates if p['id']==2),candidates[0])


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
            # Project known empty terrain using current observed camera geometry.
            # A fixed screen fraction can select a support pad in portrait.
            if not self.world_click(-8,2):
                raise RuntimeError('Actual movement terrain is outside the visible viewport')
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
        self.screenshot('equipment');before=self.tap('close')
        state=self.wait(lambda s:s['ui'].get('shop')=='','equipment shop actually closed',before['sample_id'])
        pad=support_pad(state,self.viewport);self.click(pad['x'],pad['y'])
        state=self.wait(lambda s:s.get('selected_pad')==pad['id'] and 'tower_sunbow' in s['ui']['controls'],'support pad selected',state['sample_id'])
        self.tap('tower_sunbow')
        state=self.wait(lambda s:any(t['id']==pad['id'] and t['kind']=='sunbow' for t in s.get('towers',[])),'actual support tower built',state['sample_id'])
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
        state=self.wait(lambda s:any(t['id']==pad['id'] and t['kind']=='sunbow' for t in s['towers']),'support tower rebuilt after selling',state['sample_id'])
        before=self.tap('close');self.wait(lambda s:s['ui'].get('shop')=='','tower panel actually closed',before['sample_id'])
        self.minimap_click(-8,2);self.pause(1.5)
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
                    if self.cast_observed(skill):casts.add(skill)
                    self.pause(.15)
            if time.monotonic()-last_move>2.5 and not state['hero'].get('dead'):
                # Intercept enemies with actual terrain clicks. Screen projection
                # is derived only from observed current orthographic pad points.
                enemies=state.get('enemies',[])
                if enemies:
                    target=max(enemies,key=lambda e:e.get('progress',0));pos=target['position']
                    # Public minimap movement cannot accidentally select a build
                    # pad under an enemy or click through the resulting shop.
                    self.minimap_click(pos[0],pos[2])
                last_move=time.monotonic()
            if state['hero'].get('level',1)>=3 and 'r' in casts and state.get('wave',0)>=2:
                self.report['combat_observed']={'before':initial,'after':state,'cast_skills':sorted(casts),'scope':'Two-wave hero progression, not eight-wave victory proof'}
                break
            self.pause(.2)
        else:raise TimeoutError('Two-wave hero/ultimate progression was not established with actual inputs')
        if casts!={'q','e','r'}:raise RuntimeError('All three abilities were not used through real controls')
        self.screenshot('combat-progress')
        # Await fresh pause/confirmation/reset receipts, not a fixed wall delay
        # that can expire before a slow software Web renderer handles the tap.
        self.restart_game('after portrait combat')
        self.screenshot('restart')

    def minimap_click(self, x, z):
        """A real click on the game's public minimap, using passive UI geometry."""
        state=self.current();rect=state['ui'].get('minimap')
        if not isinstance(rect,dict):raise ValueError('Visible minimap geometry is missing')
        if any(type(rect.get(k)) not in (int,float) or not math.isfinite(rect[k]) for k in ('x','y','w','h')):
            raise ValueError('Invalid actual minimap geometry')
        # These are the public map's documented world bounds, not a game command.
        sx=rect['x']+(max(-17,min(17,x))+17)/34*rect['w']
        sy=rect['y']+(max(-11,min(11,z))+11)/22*rect['h']
        if not (0<sx<self.viewport[0] and 0<sy<self.viewport[1]):raise ValueError('Minimap click is outside viewport')
        self.click(sx,sy)

    def restart_game(self, label):
        old=self.current();controls=old['ui']['controls']
        if 'confirm_restart' not in controls:
            if 'restart' not in controls:
                self.tap('pause');self.wait(lambda s:s['paused'] and 'restart' in s['ui']['controls'],label+' restart available',old['sample_id'])
            before=self.tap('restart')
            self.wait(lambda s:'confirm_restart' in s['ui']['controls'],label+' confirmation visible',before['sample_id'])
        before=self.tap('confirm_restart')
        state=self.wait(lambda s:s.get('wave')==0 and s.get('core_hp')==20 and s.get('gold')==420 and
                        len(s.get('enemies',[]))==0 and len(s.get('towers',[]))==0 and
                        s['hero'].get('level')==1 and all(v==0 for v in s['hero'].get('equipment',{}).values()) and not s['paused'] and
                        not any(t in s['ui'].get('labels',[]) for t in ('THE LIGHT ENDURES','THE DAWNHEART FALLS','曙光永存','曙光之心已陨落')),
                        label+' fresh game reset',before['sample_id'])
        return state

    def buy_equipment(self, items):
        state=self.current()
        if state['hero'].get('dead'):return False
        before=self.tap('equipment')
        self.wait(lambda s:s['ui'].get('shop')=='equipment','actual equipment panel opened',before['sample_id'])
        purchased=[]
        for item in items:
            state=self.current();control=state['ui']['controls'].get('item_'+item,{})
            if not control.get('enabled'):continue
            if item=='potion' and state['hero']['hp']>=state['hero']['max_hp']:continue
            old_count=state['hero']['equipment'].get(item,0);self.tap('item_'+item)
            self.wait(lambda s:s['hero']['equipment'].get(item,0)>old_count,'actual equipment '+item+' purchased',state['sample_id'])
            purchased.append(item)
        state=self.current();self.tap('close')
        self.wait(lambda s:s['ui'].get('shop')=='','actual equipment panel closed',state['sample_id'])
        return bool(purchased)

    def enable_double_speed(self):
        state=self.current()
        if state.get('speed')==2:return
        if 'speed' not in state['ui']['controls']:raise ValueError('Desktop full route requires visible public speed control')
        self.tap('speed');self.wait(lambda s:s.get('speed')==2,'actual public 2x speed button',state['sample_id'])

    def cast_observed(self, skill):
        key={'q':'skill_1','e':'skill_2','r':'skill_3'}[skill]
        state=self.current()
        if not state['ui']['controls'].get(key,{}).get('enabled'):return False
        self.click(*control_center(state,key,self.viewport))
        # The last enemy can die between observation and the physical click.
        # A terminal/death transition interrupts the attempt; it must never be
        # credited as a successful cast or hide a missed click in active combat.
        after=self.wait(lambda s:float(s.get('skills',{}).get(skill,{}).get('cooldown',0))>0 or
                        s.get('phase') in ('victory','defeat') or s['hero'].get('dead') is True,
                        'actual '+skill.upper()+' ability attempt resolved',state['sample_id'])
        activated=float(after.get('skills',{}).get(skill,{}).get('cooldown',0))>0
        self.report.setdefault('skill_attempts',[]).append({'skill':skill,'activated':activated,
            'before':state,'after':after,'outcome':'cooldown observed' if activated else 'interrupted by terminal/death transition'})
        if activated:
            self.report.setdefault('checks',[]).append({'name':'actual '+skill.upper()+' ability activation','state':after})
        return activated

    def full_desktop(self, max_wall_seconds=1200, max_afk_wall_seconds=600):
        """Eight-wave victory and natural defeat through only public real inputs."""
        self.prepare_combat() # Equipment, tower branch, invalid repeat, sale, rebuild.
        self.restart_game('after economy controls')
        self.buy_equipment(['blade','plate','focus','boots'])
        self.enable_double_speed()
        start=time.monotonic();deadline=start+max_wall_seconds;last_move=0;last_shop=0
        last_wave=-1;cast_skills=set();boss_observed=False;milestones=[]
        gear_costs={'blade':110,'plate':95,'focus':120,'boots':85}
        while time.monotonic()<deadline:
            state=self.current();hero=state['hero']
            if state['phase']=='defeat':raise RuntimeError('Actual full defense route lost: '+str({'wave':state['wave'],'kills':state['kills'],'deaths':state['deaths']}))
            if state['phase']=='victory':
                if state['wave']!=8 or state['core_hp']<=0 or not boss_observed:
                    raise RuntimeError('Victory observer lacks actual eight-wave boss/core evidence')
                self.screenshot('eight-wave-victory')
                self.report['full_victory']={'state':state,'wall_seconds':time.monotonic()-start,
                    'observed_at_monotonic':time.monotonic(),'milestones':milestones,'boss_observed':True,'cast_skills':sorted(cast_skills),
                    'input_route':'Public minimap, equipment, ability, speed and next-wave controls; no state injection'}
                break
            if state['wave']!=last_wave:
                last_wave=state['wave'];milestones.append({'wave':last_wave,'state':state,'wall_seconds':time.monotonic()-start})
                if last_wave in (1,4,8):self.screenshot('wave-'+str(last_wave))
            if state.get('boss') and not boss_observed:
                boss_observed=True;self.screenshot('uncrowned-king')
            if hero.get('dead'):
                self.pause(.2);continue
            # Buy in the same bounded order as the independently checked public-
            # command balance strategy, but here every purchase is a real UI click.
            if time.monotonic()-last_shop>1:
                wanted=next((item for item in ('blade','plate','blade','focus','plate','focus','boots')
                             if hero['equipment'].get(item,0)<(2 if item=='boots' else 3)),None)
                if hero['hp']<hero['max_hp']*.3 and state['gold']>=45:
                    self.buy_equipment(['potion']);last_shop=time.monotonic();continue
                if wanted and state['gold']>=gear_costs[wanted]:
                    self.buy_equipment([wanted]);last_shop=time.monotonic();continue
            if state['phase']=='build':
                before=self.tap('start_wave');self.wait(lambda s:s['wave']>before['wave'],'actual next wave '+str(before['wave']+1),before['sample_id'])
                self.pause(.1);continue
            here=hero['position'];enemies=state.get('enemies',[])
            near=[e for e in enemies if math.dist(here,e['position'])<4.9]
            boss_near=any(e['kind']=='boss' for e in near)
            if hero['hp']<hero['max_hp']*.7 and self.cast_observed('e'):cast_skills.add('e')
            if (len(near)>=2 or boss_near) and self.cast_observed('q'):cast_skills.add('q')
            if (len(near)>=4 or boss_near) and self.cast_observed('r'):cast_skills.add('r')
            # Do not target the battlefield through a newly opened result modal.
            if self.current()['phase'] in ('victory','defeat'):continue
            if time.monotonic()-last_move>.25:
                state=self.current();here=state['hero']['position'];enemies=state.get('enemies',[])
                if enemies:
                    target=max(enemies,key=lambda e:float(e.get('progress',0))-math.dist(here,e['position'])*.12)
                    pos=target['position'];distance=math.dist(here,pos)
                    if distance>2.2:
                        # Stop in melee range rather than click into the enemy.
                        ratio=max(0,(distance-2.0)/distance)
                        self.minimap_click(here[0]+(pos[0]-here[0])*ratio,here[2]+(pos[2]-here[2])*ratio)
                    else:self.minimap_click(here[0],here[2])
                else:self.minimap_click(here[0],here[2])
                last_move=time.monotonic()
            self.pause(.12)
        else:raise TimeoutError('Actual eight-wave route did not reach a terminal victory within the diagnostic window')
        if cast_skills!={'q','e','r'}:raise RuntimeError('Victory route did not establish all three actual ability activations')
        self.restart_game('after actual victory')
        self.screenshot('victory-restart')
        self.enable_double_speed()
        start=time.monotonic();deadline=start+max_afk_wall_seconds;damage_seen=False;waves=[];last_wave=-1
        self.report['afk_wall_budget_seconds']=max_afk_wall_seconds
        # Natural loss route: no movement, purchases, towers, skills or damage
        # manipulation. Only the real next-wave control and observation.
        while time.monotonic()<deadline:
            state=self.current()
            if state['wave']!=last_wave:last_wave=state['wave'];waves.append({'wave':last_wave,'hp':state['core_hp']})
            if state['core_hp']<20 and not damage_seen:
                damage_seen=True;self.screenshot('natural-core-damage')
            if state['phase']=='defeat':
                if not damage_seen or state['core_hp']>0:raise RuntimeError('Defeat lacks natural core-damage evidence')
                self.screenshot('natural-defeat')
                self.report['natural_defeat']={'state':state,'wall_seconds':time.monotonic()-start,'waves':waves,'input_route':'AFK except public next-wave and 2x controls'}
                break
            if state['phase']=='victory':raise RuntimeError('AFK route unexpectedly won; no natural defeat established')
            if state['phase']=='build':
                before=self.tap('start_wave');self.wait(lambda s:s['wave']>before['wave'],'AFK actual next wave '+str(before['wave']+1),before['sample_id'])
            self.pause(.25)
        else:raise TimeoutError('Natural AFK defeat did not occur within the diagnostic window')
        self.restart_game('after natural defeat');self.screenshot('defeat-restart')
        self.report['full_gameplay_passed']=True
