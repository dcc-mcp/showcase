"""Verify and encode native Blender frames; partial evidence requires an explicit flag."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('frames', type=Path, help='Contains wide/frame_0001.png and detail/frame_0001.png')
    p.add_argument('output', type=Path)
    p.add_argument('--wide-prefix', type=int, help='Explicit partial evidence: encode only this many wide frames (1–96).')
    args = p.parse_args()
    if args.wide_prefix is not None and not 1 <= args.wide_prefix <= 96:
        p.error('--wide-prefix must be between 1 and 96')
    partial = args.wide_prefix is not None
    shots = [('wide', args.wide_prefix)] if partial else [('wide', 96), ('detail', 48)]
    total = sum(count for _, count in shots)
    duration = total / 24
    if args.output.exists():
        raise FileExistsError('Existing movie retained. Choose a new output filename.')
    records, images = [], []
    for shot, count in shots:
        for frame in range(1, count + 1):
            path = args.frames / shot / ('frame_%04d.png' % frame)
            with Image.open(path) as im:
                im.load()
                if im.format != 'PNG' or im.size != (960, 540):
                    raise ValueError('Unexpected or incomplete native frame: ' + path.name)
                rgb = im.convert('RGB').tobytes()
            records.append({'shot': shot, 'frame': frame, 'bytes': path.stat().st_size,
                            'png_sha256': digest(path.read_bytes()), 'rgb_sha256': digest(rgb)})
            images.append(path.resolve())
    if len({row['rgb_sha256'] for row in records}) != total:
        raise ValueError('Repeated native pixels detected; investigate before encoding.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Symlinks only arrange file order. Native input bytes are never modified.
    with tempfile.TemporaryDirectory(prefix='crate-film-', dir=args.output.parent) as temp:
        temp = Path(temp)
        for index, path in enumerate(images, 1):
            (temp / ('frame_%04d.png' % index)).symlink_to(path)
        command = ['ffmpeg', '-v', 'error', '-n', '-framerate', '24', '-i', str(temp / 'frame_%04d.png'),
                   '-frames:v', str(total), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
                   '-pix_fmt', 'yuv420p', '-threads', '2', '-an', '-map_metadata', '-1',
                   '-movflags', '+faststart', str(args.output)]
        subprocess.run(command, check=True)
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format',
        '-of', 'json', str(args.output)]))
    video = probe['streams']
    if (len(video) != 1 or video[0]['codec_type'] != 'video' or video[0]['codec_name'] != 'h264'
            or video[0]['width'] != 960 or video[0]['height'] != 540
            or video[0]['nb_read_frames'] != str(total) or video[0]['r_frame_rate'] != '24/1'
            or abs(float(video[0]['duration']) - duration) > 0.000002):
        raise ValueError('Encoded movie does not match the delivery contract.')
    # Decode every frame, not just the container header or first frame.
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(args.output), '-f', 'null', '-'], check=True)
    report = {'schema_version': 1, 'delivery_status': 'partial_stage_evidence' if partial else 'complete_sequence',
              'planned_frame_count': 144, 'full_planned_film_completed': not partial,
              'native_frame_count': total, 'native_unique_rgb_frames': total,
              'resolution': [960, 540], 'fps': 24, 'duration_seconds': duration,
              'container_duration_seconds': float(probe['format']['duration']),
              'cuts_after_native_frame': [] if partial else [96], 'frame_interpolation': False,
              'audio_stream_count': 0, 'full_decode': 'pass',
              'movie_bytes': args.output.stat().st_size,
              'movie_sha256': digest(args.output.read_bytes()), 'native_frames': records}
    args.output.with_suffix('.verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'native_frames'}, indent=2))


if __name__ == '__main__':
    main()
