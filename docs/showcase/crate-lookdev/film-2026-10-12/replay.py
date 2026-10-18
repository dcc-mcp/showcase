"""Rebuild the film cameras through an existing, dedicated Blender MCP host.

Requires the exact historical source and the recorded adapter skills. This is
an MCP client, not a Blender Python production script. Start the host with
automatic scene scripts disabled. --confirm-dedicated-host is mandatory because
opening the source replaces that host's current scene.
"""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

SOURCE_SHA256 = '39f113b549bfea986d064be128a242f21b288775ccc0be81784c14c01e4e9716'
SKILLS = ['blender-scene', 'blender-camera', 'blender-animation', 'blender-objects',
          'blender-render', 'blender-scripting', 'blender-validation']
PERFORMANCE_CODE = (
    "import bpy,json; s=bpy.context.scene; s.render.threads_mode='FIXED'; "
    "s.render.threads=2; s.render.use_persistent_data=True; "
    "s.cycles.max_bounces=4; s.cycles.diffuse_bounces=2; s.cycles.glossy_bounces=2; "
    "print(json.dumps({'threads':s.render.threads,'persistent_data':s.render.use_persistent_data,"
    "'max_bounces':s.cycles.max_bounces,'diffuse_bounces':s.cycles.diffuse_bounces,"
    "'glossy_bounces':s.cycles.glossy_bounces}))"
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class Mcp:
    def __init__(self, url, receipt):
        parsed = urllib.parse.urlsplit(url)
        try:
            loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            loopback = False
        if (parsed.scheme != 'http' or not loopback or parsed.path != '/mcp'
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('Use the dedicated host\'s loopback HTTP MCP endpoint.')
        self.url, self.receipt, self.next_id = url, receipt, 0

    def call(self, tool_name, allow_parent_warning=False, **arguments):
        self.next_id += 1
        request = {'jsonrpc': '2.0', 'id': self.next_id, 'method': 'tools/call',
                   'params': {'name': tool_name, 'arguments': arguments}}
        started = time.time()
        req = urllib.request.Request(self.url, data=json.dumps(request).encode(),
                                     headers={'Content-Type': 'application/json',
                                              'Accept': 'application/json, text/event-stream'})
        with urllib.request.urlopen(req, timeout=900) as response:
            body = response.read().decode()
        if body.startswith(('event:', 'data:')):
            body = '\n'.join(line[6:] for line in body.splitlines() if line.startswith('data: '))
        result = json.loads(body)
        with self.receipt.open('a') as stream:
            stream.write(json.dumps({'request': request, 'response': result,
                                     'seconds': round(time.time() - started, 3)}) + '\n')
        payload = result.get('result', {})
        value = payload.get('structuredContent')
        if value is None and payload.get('content'):
            value = json.loads(payload['content'][0]['text'])
        value = value or {}
        failed = 'error' in result or payload.get('isError') or value.get('success') is False
        if failed:
            context = value.get('context', {})
            # 0.2.16 can report a micrometre-scale matrix drift AFTER parenting.
            # Preserve the failure receipt and verify actual state before recovery.
            recoverable = (allow_parent_warning and tool_name == 'blender_objects__parent_object'
                           and context.get('parent_name') == 'Film_Orbit_Rig'
                           and context.get('child_name') == 'Camera_Reference'
                           and context.get('world_transform_preserved') is False
                           and 0 <= context.get('world_transform_delta', float('inf')) <= 0.000002)
            if not recoverable:
                raise RuntimeError(json.dumps(result))
            print('Recorded parent-transform verification warning; verifying state before recovery.')
        return value


def rebuild(mcp, source, output):
    for filename in ('crate-film-wide.blend', 'crate-film-detail.blend'):
        if (output / filename).exists():
            raise FileExistsError('Use a fresh output directory; existing native scenes are not overwritten.')
    c = mcp.call
    c('load_skill', skill_names=SKILLS)
    c('blender_scene__open_scene', filepath=str(source))
    c('blender_validation__validate_materials')
    c('blender_objects__create_object', object_type='empty', name='Film_Orbit_Rig', location=[0, 0, 0])
    c('blender_objects__parent_object', allow_parent_warning=True,
      child_name='Camera_Reference', parent_name='Film_Orbit_Rig')
    state = c('blender_objects__get_object_info', name='Camera_Reference')['context']
    if state.get('parent') != 'Film_Orbit_Rig':
        raise RuntimeError('Unexpected camera parent; stopped before pose recovery.')
    c('blender_objects__move_object', name='Camera_Reference', location=[2.3, -6, 2.73155])
    c('blender_objects__rotate_object', name='Camera_Reference', rotation=[71.339925692, 0, 20.973494328])
    recovered = c('blender_objects__get_object_info', name='Camera_Reference')['context']
    expected = {'location': [2.3, -6, 2.73155],
                'rotation_euler_degrees': [71.339925692, 0, 20.973494328],
                'scale': [1, 1, 1]}
    if recovered.get('parent') != 'Film_Orbit_Rig':
        raise RuntimeError('Camera parent changed unexpectedly during pose recovery.')
    for field, target in expected.items():
        actual = recovered.get(field, [])
        tolerance = 0.00003 if field == 'rotation_euler_degrees' else 0.000003
        if len(actual) != 3 or any(abs(a - b) > tolerance for a, b in zip(actual, target)):
            raise RuntimeError('Camera pose recovery did not match the recorded source: ' + field)
    c('blender_camera__set_camera_properties', name='Camera_Reference', lens=60)
    c('blender_render__set_render_settings', engine='CYCLES', resolution_x=960,
      resolution_y=540, resolution_percentage=100, samples=12, fps=24, file_format='PNG')
    c('blender_render__set_render_denoise', enabled=True, denoiser='OPENIMAGEDENOISE')
    # The typed render settings do not expose threads or bounce limits.
    c('blender_scripting__execute_python', code=PERFORMANCE_CODE)
    for frame, angle in ((1, -16), (97, 28)):
        c('blender_animation__set_current_frame', frame=frame)
        c('blender_objects__rotate_object', name='Film_Orbit_Rig', rotation=[0, 0, angle])
        c('blender_animation__set_keyframe', object_name='Film_Orbit_Rig', frame=frame,
          data_paths=['rotation_euler'], interpolation='LINEAR')
    c('blender_animation__set_frame_range', start=1, end=96)
    c('blender_animation__set_current_frame', frame=1)
    c('blender_scene__save_scene', filepath=str(output / 'crate-film-wide.blend'))
    c('blender_scene__open_scene', filepath=str(output / 'crate-film-wide.blend'))
    c('blender_scene__get_session_info')
    c('blender_animation__get_keyframes', object_name='Film_Orbit_Rig')
    c('blender_camera__set_active_camera', name='Detail_BrokenBatten')
    c('blender_animation__set_keyframe', object_name='Detail_BrokenBatten', frame=1,
      data_paths=['location'], interpolation='LINEAR')
    c('blender_animation__set_current_frame', frame=49)
    c('blender_objects__move_object', name='Detail_BrokenBatten', location=[1.45, -1.75, 1.61])
    c('blender_animation__set_keyframe', object_name='Detail_BrokenBatten', frame=49,
      data_paths=['location'], interpolation='LINEAR')
    c('blender_animation__set_frame_range', start=1, end=48)
    c('blender_animation__set_current_frame', frame=1)
    c('blender_scene__save_scene', filepath=str(output / 'crate-film-detail.blend'))
    c('blender_scene__open_scene', filepath=str(output / 'crate-film-detail.blend'))
    c('blender_scene__get_session_info')
    c('blender_animation__get_keyframes', object_name='Detail_BrokenBatten')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mcp-url', required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--confirm-dedicated-host', action='store_true', required=True)
    parser.add_argument('--shot', choices=('wide', 'detail'))
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=5)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if sha256(source) != SOURCE_SHA256:
        raise ValueError('The input is not the exact recorded source.')
    output.mkdir(parents=True, exist_ok=True)
    mcp = Mcp(args.mcp_url, output / 'replay-calls.private.jsonl')
    if args.shot is None:
        rebuild(mcp, source, output)
    else:
        count = 96 if args.shot == 'wide' else 48
        if not 1 <= args.start <= args.end <= count or args.end - args.start >= 5:
            raise ValueError('Request one bounded batch of at most five frames within the shot range.')
        mcp.call('load_skill', skill_names=SKILLS)
        mcp.call('blender_scene__open_scene', filepath=str(output / ('crate-film-' + args.shot + '.blend')))
        frames = output / 'frames' / args.shot
        frames.mkdir(parents=True, exist_ok=True)
        for frame in range(args.start, args.end + 1):
            target = frames / ('frame_%04d.png' % frame)
            if target.exists():
                raise FileExistsError('Existing frame retained; choose only missing frames.')
            mcp.call('blender_animation__set_current_frame', frame=frame)
            mcp.call('blender_render__render_scene', output_path=str(target))
    print('Requested MCP operations finished. Inspect files and receipts; rendering is not visual acceptance.')


if __name__ == '__main__':
    main()
