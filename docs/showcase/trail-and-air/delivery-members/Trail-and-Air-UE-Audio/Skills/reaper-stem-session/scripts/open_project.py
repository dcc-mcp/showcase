from pathlib import Path
from dcc_mcp_core.skill import skill_entry, skill_success
from .common import R, active_project, resolve_rpp, audit
@skill_entry
def main(project_path: str):
    path=resolve_rpp(project_path)
    if not path.is_file(): raise FileNotFoundError(path)
    if R.IsProjectDirty(active_project()): raise RuntimeError('Save the active project before reopening')
    R.Main_openProject(str(path))
    result=audit()
    if Path(result['project']).resolve() != path.resolve(): raise RuntimeError('REAPER did not open requested project')
    return skill_success('Native RPP reopened in REAPER', **result)
