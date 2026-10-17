"""Measure captured media even when streaming WebM omits container duration."""

import json
import math
import subprocess


def media_duration(source):
    metadata = json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(source)],
        text=True,
    ))
    try:
        duration = float(metadata.get('format', {}).get('duration', 'nan'))
    except (TypeError, ValueError):
        duration = math.nan
    if math.isfinite(duration) and duration > 0:
        return duration

    # MediaRecorder WebM is a stream: no finalized duration header is required.
    # Decode both required streams completely and use FFmpeg's measured end time.
    # Missing metadata must never bypass the preview's existing duration limit.
    decoded = subprocess.run(
        ['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-threads', '1',
         '-i', str(source), '-map', '0:v:0', '-map', '0:a:0',
         '-f', 'null', '-', '-progress', 'pipe:1', '-nostats'],
        check=True, capture_output=True, text=True,
    )
    progress = dict(line.split('=', 1) for line in decoded.stdout.splitlines() if '=' in line)
    try:
        duration = int(progress.get('out_time_us', '')) / 1_000_000
    except ValueError:
        duration = math.nan
    if decoded.stderr.strip() or progress.get('progress') != 'end' or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Media duration could not be verified by a complete, error-free decode')
    return duration
