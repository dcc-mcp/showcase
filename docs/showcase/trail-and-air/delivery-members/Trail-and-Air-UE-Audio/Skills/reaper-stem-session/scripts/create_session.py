import json
from pathlib import Path

from dcc_mcp_core.skill import skill_entry, skill_success

from .common import R, active_project, audit, resolve_rpp


@skill_entry
def main(manifest_path: str, project_path: str):
    manifest = Path(manifest_path).resolve()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    target = resolve_rpp(project_path)
    if target.exists():
        raise FileExistsError("Destination already exists; refusing overwrite")
    project = active_project()
    if R.CountTracks(project) or R.IsProjectDirty(project):
        raise RuntimeError("Create requires an empty, clean project")
    tracks = data["tracks"]
    bpm = float(data["bpm"])
    duration = float(data["duration_seconds"])
    if not 1 <= len(tracks) <= 32 or not 30 <= bpm <= 240 or not 1 <= duration <= 600:
        raise ValueError("Manifest bounds invalid")
    title = data.get("title", "Tidal Signals")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Manifest title must be a nonempty string")
    resolved = []
    for track in tracks:
        name = track.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Each track name must be a nonempty string")
        path = (manifest.parent / track["wav_path"]).resolve()
        try:
            path.relative_to(manifest.parent)
        except ValueError:
            raise ValueError("Each WAV must exist inside manifest directory") from None
        if not path.is_file() or path.suffix.lower() != ".wav":
            raise ValueError("Each WAV must exist inside manifest directory")
        gain = float(track.get("gain_linear", 1))
        pan = float(track.get("pan", 0))
        if not 0 <= gain <= 2 or not -1 <= pan <= 1:
            raise ValueError("Invalid gain/pan")
        resolved.append((name, path, gain, pan))

    # Validate the complete manifest before the first host mutation.
    R.SetCurrentBPM(project, bpm, True)
    for key, value in [("PROJECT_SRATE", 48000), ("PROJECT_SRATE_USE", 1)]:
        R.GetSetProjectInfo(project, key, value, True)
    colors = [(67, 204, 204), (238, 172, 93), (135, 157, 255), (219, 133, 193), (165, 211, 149)]
    for index, (name, path, gain, pan) in enumerate(resolved):
        R.SetEditCurPos(0, False, False)
        count = R.CountTracks(project)
        R.InsertMedia(str(path), 1)
        if R.CountTracks(project) != count + 1:
            raise RuntimeError("REAPER did not import new stem track")
        track = R.GetTrack(project, count)
        R.GetSetMediaTrackInfo_String(track, "P_NAME", name, True)
        R.SetMediaTrackInfo_Value(track, "D_VOL", gain)
        R.SetMediaTrackInfo_Value(track, "D_PAN", pan)
        R.SetTrackColor(track, R.ColorToNative(*colors[index % len(colors)]) | 0x1000000)
    bar = 240 / bpm
    for name, start, end in [
        ("Arrival", 0, bar * 4),
        ("Current", bar * 4, bar * 8),
        ("Signal", bar * 8, bar * 12),
        ("Horizon", bar * 12, duration),
    ]:
        end = min(end, duration)
        if start < end:
            R.AddProjectMarker2(project, True, start, end, name, -1, 0)
    R.GetSetProjectInfo_String(project, "PROJECT_TITLE", title, True)
    R.GetSetProjectInfo_String(project, "PROJECT_AUTHOR", "DCC-MCP original synthesis", True)
    R.GetSetProjectInfo_String(project, "RECORD_PATH", "media", True)
    R.UpdateArrange()
    target.parent.mkdir(parents=True, exist_ok=True)
    R.Main_SaveProjectEx(project, str(target), 8)
    if not target.is_file() or target.stat().st_size < 100:
        raise RuntimeError("Native project save did not create a valid file")
    result = audit()
    if Path(result["project"]).resolve() != target or result["dirty"]:
        raise RuntimeError("Native project save could not be verified against the active project")
    return skill_success("Native stem session created and saved", manifest=str(manifest), **result)
