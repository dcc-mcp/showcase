"""Shared native API operations. No synthetic/mock REAPER implementation."""
from pathlib import Path
import json
import reapy_boost
from reapy_boost import reascript_api as R

def active_project():
    return R.EnumProjects(-1, '', 4096)[0]

def audit():
    p = active_project()
    tracks = []
    for i in range(R.CountTracks(p)):
        t = R.GetTrack(p, i)
        items = []
        for j in range(R.CountTrackMediaItems(t)):
            item = R.GetTrackMediaItem(t, j)
            take = R.GetActiveTake(item)
            source = R.GetMediaItemTake_Source(take)
            source_path = R.GetMediaSourceFileName(source, '', 4096)[1]
            items.append({'position': R.GetMediaItemInfo_Value(item, 'D_POSITION'),
                          'length': R.GetMediaItemInfo_Value(item, 'D_LENGTH'),
                          'source': source_path, 'source_exists': Path(source_path).is_file()})
        tracks.append({'index': i, 'name': R.GetSetMediaTrackInfo_String(t, 'P_NAME', '', False)[3],
                       'guid': R.GetSetMediaTrackInfo_String(t, 'GUID', '', False)[3], 'gain': R.GetMediaTrackInfo_Value(t, 'D_VOL'),
                       'pan': R.GetMediaTrackInfo_Value(t, 'D_PAN'),
                       'muted': bool(R.GetMediaTrackInfo_Value(t, 'B_MUTE')),
                       'fx_count': R.TrackFX_GetCount(t), 'items': items})
    return {'host_version': R.GetAppVersion(), 'project': R.EnumProjects(-1, '', 4096)[2],
            'dirty': bool(R.IsProjectDirty(p)), 'tempo': R.Master_GetTempo(),
            'duration': R.GetProjectLength(p), 'tracks': tracks,
            'track_count': len(tracks), 'media_item_count': sum(len(t['items']) for t in tracks)}

def resolve_rpp(value):
    path = Path(value).resolve()
    if path.suffix.lower() != '.rpp': raise ValueError('Expected a .rpp project path')
    return path
