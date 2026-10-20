"""Real browser target focus, with Playwright's forced-focus override removed.

Never dispatches DOM events or changes focus state through page JavaScript.
The retained CDP session disables emulation once AFTER final navigation, before
input or measurement. Navigation can restore Playwright's original-session
true override; every later navigation invalidates this proof and fails closed.
Transitions only use real target activation plus passive observations.
"""
from __future__ import annotations
import time

FOCUS_INIT = r"""(() => {
  const records = []; let overflow = false;
  const record = event => {
    if (records.length >= 128) { overflow = true; return; }
    records.push({type:event.type, trusted:event.isTrusted, wall_ms:performance.now(),
      focused:document.hasFocus(), visible:document.visibilityState === 'visible'});
  };
  window.addEventListener('focus', record);
  window.addEventListener('blur', record);
  document.addEventListener('visibilitychange', record);
  Object.defineProperty(window, '__tidalFocusEvidence', {value:() => ({
    records:records.map(item => ({...item})), overflow,
    focused:document.hasFocus(), visible:document.visibilityState === 'visible',
    visibility:document.visibilityState, wall_ms:performance.now(),
    document_url:location.href, time_origin:performance.timeOrigin})});
})()"""


def validate_focus_transition(before, after, active, require_hidden_lifecycle=False):
    if type(active) is not bool:
        raise ValueError('Focus expectation must be boolean')
    if before.get('overflow') is not False or after.get('overflow') is not False:
        raise ValueError('Focus event history overflow or absent')
    prior, current = before.get('records'), after.get('records')
    if not isinstance(prior, list) or not isinstance(current, list) or current[:len(prior)] != prior:
        raise ValueError('Focus event history was lost or replaced')
    if (before.get('focused') is not (not active) or type(before.get('visible')) is not bool
            or after.get('focused') is not active or type(after.get('visible')) is not bool
            or (active and after['visible'] is not True)):
        raise ValueError('Actual target activation has not changed DOM focus, or foreground is hidden')
    events = current[len(prior):]
    expected = 'focus' if active else 'blur'
    if not any(item.get('type') == expected and item.get('trusted') is True for item in events):
        raise ValueError('Target transition lacks its real trusted window event')
    # Target activation can switch window focus while both targets remain
    # visible. Do not equate a real blur with hidden-tab visibility. If the
    # browser does emit visibility changes, preserve and reconcile them.
    visibility = [item for item in events if item.get('type') == 'visibilitychange']
    if (any(type(item.get('visible')) is not bool for item in visibility)
            or (visibility and visibility[-1]['visible'] is not after['visible'])):
        raise ValueError('Observed visibility changes disagree with the actual final visibility')
    if any(item.get('trusted') is not True for item in events):
        raise ValueError('Synthetic focus events cannot qualify real target activation')
    if require_hidden_lifecycle:
        if (after['visible'] is not active or not visibility
                or not any(item.get('visible') is active for item in visibility)):
            raise ValueError('Headed tab lifecycle lacks real hidden/visible transition')
    return {'active':active, 'events':events, 'focused':after['focused'], 'visible':after['visible'],
            'scope':('headed same-window tab hidden/visible transition; OS focus not established'
                if require_hidden_lifecycle else 'browser target window focus; hidden-tab and OS focus not established')}


def prepare_real_focus(page, bounded_cdp):
    """Call before navigation. Retain the returned session until context.close."""
    session = page.context.new_cdp_session(page)
    page.add_init_script(script=FOCUS_INIT)
    return session


def wait_focus_state(page, passive_evaluate, active, timeout=3):
    if type(active) is not bool or type(timeout) not in (int, float) or not 0 < timeout <= 30:
        raise ValueError('Invalid bounded focus expectation')
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Actual DOM focus/visibility transition exceeded its bounded wait')
        value = passive_evaluate(page, '() => __tidalFocusEvidence()', timeout=remaining)
        if time.monotonic() >= deadline:
            raise TimeoutError('Late DOM focus observation exceeded its bounded wait')
        if not isinstance(value, dict) or value.get('overflow') is not False:
            raise ValueError('Missing or overflowed passive focus evidence')
        if (value.get('focused') is active and type(value.get('visible')) is bool
                and (not active or value['visible'] is True)):
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError('Actual DOM focus/visibility state did not match target activation: ' + repr(value))
        page.wait_for_timeout(50)


class RealTargetFocus:
    def __init__(self, page, bounded_cdp, passive_evaluate, require_hidden=False):
        if type(require_hidden) is not bool:
            raise ValueError('Hidden lifecycle selection must be explicit boolean')
        self.require_hidden = require_hidden
        self._companion = None
        self.page = page
        self._passive = passive_evaluate
        self._bounded = bounded_cdp
        self._target_sessions = {}
        # Keep this session alive through all navigation and target switches.
        # Detaching a session early may discard its emulation settings.
        self.session = prepare_real_focus(page, bounded_cdp)
        self.report = {'method':'real Page.bringToFront after one-time forced-focus removal',
                       'scope':('headed same-window hidden/visible lifecycle required; OS focus not established'
                           if require_hidden else 'browser target window focus; hidden-tab and OS focus not established'),
                       'emulation_disabled_after_navigation':False, 'transitions':[]}
        self._settle_attempted = False
        self._navigation = None

    @staticmethod
    def _identity(value):
        url, origin = value.get('document_url'), value.get('time_origin')
        if not isinstance(url,str) or not url or type(origin) not in (int,float) or not 0 < origin < float('inf'):
            raise ValueError('Missing exact document navigation identity')
        return (url,origin)

    def _read(self, timeout=3):
        value = self._passive(self.page, '() => __tidalFocusEvidence()', timeout=timeout)
        if not isinstance(value, dict):
            raise ValueError('Missing passive focus evidence')
        return value

    def settle_after_navigation(self, timeout=3):
        if type(timeout) not in (int,float) or not 0 < timeout <= 30:
            raise ValueError('Invalid bounded post-navigation setup timeout')
        if self._settle_attempted:
            raise ValueError('Focus emulation removal may be attempted only once per page lifecycle')
        self._settle_attempted = True
        deadline = time.monotonic() + timeout
        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError('Post-navigation focus setup exceeded its bounded wait')
            return value
        before = self._read(timeout=remaining())
        identity = self._identity(before)
        self.report['setup'] = {'document_url':identity[0],'time_origin':identity[1],'before':before}
        # The original Playwright session may restore true at navigation. This
        # removal therefore happens only after the final committed document.
        self._bounded(self.session,'Emulation.setFocusEmulationEnabled',{'enabled':False},timeout=remaining())
        after = self._read(timeout=remaining())
        remaining()
        self.report['setup']['after'] = after
        if self._identity(after) != identity:
            raise ValueError('Document navigated during focus-emulation removal')
        self._navigation = identity
        self.report['emulation_disabled_after_navigation'] = True
        return after

    def snapshot(self, timeout=3):
        if self._navigation is None:
            raise ValueError('Focus setup must settle after navigation and before measurement')
        value = self._read(timeout=timeout)
        if self._identity(value) != self._navigation:
            raise ValueError('Navigation invalidated post-navigation focus setup')
        return value

    def verify_same_window_tabs(self, companion, timeout=3):
        """Read genuine Chrome target/window IDs; do not create or emulate windows."""
        if not isinstance(companion,RealTargetFocus) or companion.page is self.page:
            raise ValueError('Same-window proof requires a distinct prepared companion')
        if type(timeout) not in (int,float) or not 0 < timeout <= 30:
            raise ValueError('Invalid bounded window inspection timeout')
        deadline=time.monotonic()+timeout
        def remaining():
            value=deadline-time.monotonic()
            if value<=0:raise TimeoutError('Genuine window inspection exceeded deadline')
            return value
        entries=[]
        for probe in (self,companion):
            # Window/target metadata is browser-process evidence. The caller
            # validates the measured document identity before every switch;
            # do not queue another renderer DOM round-trip here.
            if probe._navigation is None:
                raise ValueError('Window proof requires both pages to have settled after navigation')
            target=self._bounded(probe.session,'Target.getTargetInfo',{},timeout=remaining()).get('targetInfo',{})
            target_id=target.get('targetId')
            if not isinstance(target_id,str) or not target_id:
                raise ValueError('Chrome did not identify the exact page target')
            if target.get('url') != probe._navigation[0]:
                raise ValueError('Browser target URL changed after final focus setup')
            window=self._bounded(probe.session,'Browser.getWindowForTarget',{'targetId':target_id},timeout=remaining())
            remaining()
            if type(window.get('windowId')) is not int or not isinstance(window.get('bounds'),dict):
                raise ValueError('Chrome did not return genuine browser window metadata')
            entries.append({'target_id':target_id,'url':target['url'],'window_id':window['windowId'],'bounds':window['bounds']})
        self.report['same_window_tabs']={'targets':entries,'passed':False}
        self.report.setdefault('window_history',[]).append(self.report['same_window_tabs'])
        if entries[0]['target_id']==entries[1]['target_id'] or entries[0]['window_id']!=entries[1]['window_id']:
            raise ValueError('Browser targets are not distinct tabs in the same genuine window')
        self.report['same_window_tabs']['passed']=True
        self._companion=companion
        return self.report['same_window_tabs']

    def switch_to(self, target, active, timeout=3, require_hidden_lifecycle=False):
        if type(require_hidden_lifecycle) is not bool:
            raise ValueError('Hidden lifecycle selection must be boolean')
        require_hidden_lifecycle = self.require_hidden or require_hidden_lifecycle
        if type(active) is not bool or type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise ValueError('Invalid bounded focus transition')
        if require_hidden_lifecycle and not self.report.get('same_window_tabs',{}).get('passed'):
            raise ValueError('Hidden-tab lifecycle requires genuine same-window proof first')
        if require_hidden_lifecycle and target is not (self.page if active else self._companion.page):
            raise ValueError('Target activation must use the exact verified window tabs')
        deadline = time.monotonic() + timeout
        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError('Actual target focus transition exceeded its bounded wait')
            return value
        before = self.snapshot(timeout=remaining())
        remaining()  # A late passive reply cannot be accepted.
        if require_hidden_lifecycle:
            self.verify_same_window_tabs(self._companion,timeout=remaining())
        entry = {'active':active, 'before':before, 'passed':False,
                 'require_hidden_lifecycle':require_hidden_lifecycle}
        self.report['transitions'].append(entry)
        try:
            session = self.session if target is self.page else self._target_sessions.get(id(target))
            if session is None:
                session = target.context.new_cdp_session(target)
                self._target_sessions[id(target)] = session
            self._bounded(session, 'Page.bringToFront', {}, timeout=remaining())
            remaining()
            while True:
                after = self.snapshot(timeout=remaining())
                entry['after'] = after
                remaining()
                try:
                    entry['proof'] = validate_focus_transition(before, after, active, require_hidden_lifecycle=require_hidden_lifecycle)
                    entry['passed'] = True
                    return after
                except ValueError as error:
                    entry['last_error'] = str(error)
                self.page.wait_for_timeout(min(50, remaining() * 1000))
        except Exception as error:
            entry['error'] = repr(error)
            raise
