import hashlib
import wave
from pathlib import Path

from dcc_mcp_core.skill import skill_entry, skill_success

from .common import R, active_project


@skill_entry
def main(output_path: str):
    target = Path(output_path).resolve()
    if target.suffix.lower() != ".wav":
        raise ValueError("Render target must be WAV")
    if "$" in target.name:
        raise ValueError("Render filename must not contain REAPER wildcards")
    if target.exists():
        raise FileExistsError("Will not overwrite an existing render")
    target.parent.mkdir(parents=True, exist_ok=True)
    p = active_project()
    if R.CountTracks(p) < 1:
        raise RuntimeError("Nothing to render")
    for name, value in [
        ("RENDER_FILE", str(target.parent)),
        ("RENDER_PATTERN", target.stem),
        ("RENDER_FORMAT", "evaw"),
        ("RENDER_FORMAT2", ""),
    ]:
        R.GetSetProjectInfo_String(p, name, value, True)
    for name, value in [
        ("RENDER_SETTINGS", 0),
        ("RENDER_BOUNDSFLAG", 1),
        ("RENDER_CHANNELS", 2),
        ("RENDER_SRATE", 48000),
        ("RENDER_TAILFLAG", 0),
        ("RENDER_ADDTOPROJ", 0),
        ("RENDER_NORMALIZE", 0),
        ("RENDER_DITHER", 16),
    ]:
        R.GetSetProjectInfo(p, name, value, True)
    R.Main_OnCommand(42230, 0)
    if not target.is_file() or target.stat().st_size < 1000:
        raise RuntimeError("Native render did not produce WAV")
    with wave.open(str(target), "rb") as f:
        details = {
            "sample_rate": f.getframerate(),
            "channels": f.getnchannels(),
            "sample_width_bytes": f.getsampwidth(),
            "frames": f.getnframes(),
            "duration": f.getnframes() / f.getframerate(),
        }
    if details["sample_rate"] != 48000 or details["channels"] != 2 or details["frames"] < 1:
        raise RuntimeError("Native render did not produce the requested stereo 48 kHz WAV")
    return skill_success(
        "REAPER native offline master rendered",
        output_path=str(target),
        bytes=target.stat().st_size,
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        **details,
    )
