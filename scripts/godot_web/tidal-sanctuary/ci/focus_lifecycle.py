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


def validate_focus_transition(before, after, active):
    if type(active) is not bool:
        raise ValueError('Focus expectation must be boolean')
    if before.get('overflow') is not False or after.get('overflow') is not False:
        raise ValueError('Focus event history overflow or absent')
    prior, current = before.get('records'), after.get('records')
    if not isinstance(prior, list) or not isinstance(current, list) or current[:len(prior)] != prior:
        raise ValueError('Focus event history was lost or replaced')
    if after.get('focused') is not active or after.get('visible') is not active:
        raise ValueError('Actual target activation has not changed DOM focus and visibility')
    events = current[len(prior):]
    expected = 'focus' if active else 'blur'
    if not any(item.get('type') == expected and item.get('trusted') is True for item in events):
        raise ValueError('Target transition lacks its real trusted window event')
    if not any(item.get('type') == 'visibilitychange' and item.get('trusted') is True
               and item.get('visible') is active for item in events):
        raise ValueError('Target transition lacks its real trusted visibility event')
    if any(item.get('trusted') is not True for item in events):
        raise ValueError('Synthetic focus events cannot qualify real target activation')
    return {'active':active, 'events':events, 'focused':after['focused'], 'visible':after['visible']}


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
        if value.get('focused') is active and value.get('visible') is active:
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError('Actual DOM focus/visibility state did not match target activation: ' + repr(value))
        page.wait_for_timeout(50)


class RealTargetFocus:
    def __init__(self, page, bounded_cdp, passive_evaluate):
        self.page = page
        self._passive = passive_evaluate
        self._bounded = bounded_cdp
        self._target_sessions = {}
        # Keep this session alive through all navigation and target switches.
        # Detaching a session early may discard its emulation settings.
        self.session = prepare_real_focus(page, bounded_cdp)
        self.report = {'method':'real Page.bringToFront after one-time forced-focus removal',
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

    def switch_to(self, target, active, timeout=3):
        if type(active) is not bool or type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise ValueError('Invalid bounded focus transition')
        deadline = time.monotonic() + timeout
        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError('Actual target focus transition exceeded its bounded wait')
            return value
        before = self.snapshot(timeout=remaining())
        remaining()  # A late passive reply cannot be accepted.
        entry = {'active':active, 'before':before, 'passed':False}
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
                    entry['proof'] = validate_focus_transition(before, after, active)
                    entry['passed'] = True
                    return after
                except ValueError as error:
                    entry['last_error'] = str(error)
                self.page.wait_for_timeout(min(50, remaining() * 1000))
        except Exception as error:
            entry['error'] = repr(error)
            raise
