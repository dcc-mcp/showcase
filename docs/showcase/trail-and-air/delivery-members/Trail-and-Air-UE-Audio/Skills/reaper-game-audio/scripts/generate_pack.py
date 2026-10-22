import json
from pathlib import Path
from dcc_mcp_core.skill import skill_entry, skill_success
from reapy_boost import reascript_api as R
from .synthesis import generate

@skill_entry
def main(output_dir: str, seed: int = 73):
    root=Path(output_dir).resolve()
    if root.exists() and any(root.iterdir()):raise FileExistsError('Use a new, empty output directory')
    p=R.EnumProjects(-1,'',4096)[0]
    if R.CountTracks(p) or R.IsProjectDirty(p):raise RuntimeError('Generation requires an empty clean REAPER project')
    if not isinstance(seed,int) or isinstance(seed,bool) or not 0<=seed<=2147483647:raise ValueError('Invalid seed')
    m=generate(root/'media',sample_rate=48000,seed=seed)
    R.SetCurrentBPM(p,100,True)
    R.GetSetProjectInfo(p,'PROJECT_SRATE',48000,True)
    R.GetSetProjectInfo(p,'PROJECT_SRATE_USE',1,True)
    groups={};timeline=[];cursor=0
    for a in m['assets']:
        key=a['category']+(' / '+a['surface'] if a.get('surface') else '')
        if key not in groups:
            idx=R.CountTracks(p);R.InsertTrackAtIndex(idx,True);tr=R.GetTrack(p,idx)
            R.GetSetMediaTrackInfo_String(tr,'P_NAME',key,True);groups[key]=tr
        tr=groups[key]
        item=R.AddMediaItemToTrack(tr)
        take=R.AddTakeToMediaItem(item)
        source=R.PCM_Source_CreateFromFile(str(root/'media'/a['wav_path']))
        if not source or '0x0000000000000000' in str(source):raise RuntimeError('Native PCM source creation failed')
        R.SetMediaItemTake_Source(take,source)
        R.GetSetMediaItemTakeInfo_String(take,'P_NAME',a['id'],True)
        start=cursor/48000;length=a['frames']/48000
        for key,value in [('D_POSITION',start),('D_LENGTH',length),('D_VOL',1),('D_FADEINLEN',0),('D_FADEOUTLEN',0),('D_FADEINLEN_AUTO',-1),('D_FADEOUTLEN_AUTO',-1)]:R.SetMediaItemInfo_Value(item,key,value)
        R.AddProjectMarker2(p,True,start,start+length,a['id'],-1,0)
        timeline.append(dict(id=a['id'],start_frame=cursor,end_frame=cursor+a['frames'],frames=a['frames'],channels=a['channels'],target=a['native_export_target_name']))
        cursor+=a['frames']+24000
    R.GetSetProjectInfo_String(p,'PROJECT_TITLE','Trail & Air — original audio atlas',True)
    R.GetSetProjectInfo_String(p,'PROJECT_AUTHOR','DCC-MCP original synthesis',True)
    R.GetSetProjectInfo_String(p,'RECORD_PATH','media',True)
    R.UpdateArrange()
    project=root/'Trail-and-Air.rpp'
    R.Main_SaveProjectEx(p,str(project),8)
    if not project.is_file() or R.IsProjectDirty(p):raise RuntimeError('Native project save failed')
    (root/'atlas.json').write_text(json.dumps({'sample_rate':48000,'assets':timeline},indent=2))
    return skill_success('Original audio generated and imported into native REAPER atlas',project=str(project),source_manifest=str(root/'media/manifest.json'),assets=len(timeline),tracks=len(groups),host_version=R.GetAppVersion(),seed=seed)
