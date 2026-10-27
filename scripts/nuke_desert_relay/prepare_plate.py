"""Prepare the exact public-domain NPS excerpt. Does not launch a DCC.

Usage: python prepare_plate.py --source /path/to/nps-racetrack-720p.mp4
Requires installed ffmpeg/ffprobe; optical-flow analysis also needs OpenCV.
No dependency installation, network access, or image generation is performed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

SOURCE_SHA256 = "eb6806c70655ace293e06d94767cc9a76e561da5ba4494103ce5d0ed70cc3d08"
START_SECONDS = 13
FRAME_COUNT = 240
FPS = 30


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    source = args.source.resolve()
    actual_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual_sha != SOURCE_SHA256:
        raise SystemExit("Source hash mismatch; refusing a different plate")
    dest = assets / "plate-8s.mp4"
    if dest.exists():
        raise SystemExit("Refusing to overwrite the existing excerpt")
    source_probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)]))
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "1", "-ss", str(START_SECONDS), "-i", str(source),
         "-frames:v", str(FRAME_COUNT), "-map", "0:v:0", "-an", "-map_metadata", "-1", "-c:v", "libx264", "-threads", "1",
         "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-movflags", "+faststart", "-n", str(dest)])
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(dest)]))
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "1", "-i", str(dest), "-f", "null", "-"])
    for frame, name in [(0, "plate-first.jpg"), (120, "plate-middle.jpg"), (239, "plate-last.jpg")]:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "1", "-i", str(dest), "-vf", "select=eq(n\\,%d)" % frame,
             "-frames:v", "1", "-q:v", "2", "-n", str(assets / name)])
    for record in [source_probe, probe]:
        record.get("format", {}).pop("filename", None)
    receipt = {
        "source_sha256": actual_sha, "source_bytes": source.stat().st_size,
        "source_probe": source_probe, "source_range_seconds": [13, 21],
        "source_zero_based_video_frames": [390, 629],
        "excerpt_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "excerpt_bytes": dest.stat().st_size,
        "excerpt_probe": probe, "full_excerpt_decode": "passed",
        "audio_decision": "Intentionally omitted; source has an AAC stream although the author describes the video as silent. No listening pass is claimed.",
        "encoding": "ffmpeg H264 CRF16 yuv420p, explicit BT709 tags; no retime, one encoder/decoder thread",
        "dcc_execution": "not-run",
    }
    (root / "plate-analysis.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ["excerpt_sha256", "excerpt_bytes", "source_range_seconds", "full_excerpt_decode"]}, indent=2))


if __name__ == "__main__":
    main()
