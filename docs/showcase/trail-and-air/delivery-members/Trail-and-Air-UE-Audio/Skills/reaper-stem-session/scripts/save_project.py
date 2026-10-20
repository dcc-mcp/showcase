from pathlib import Path

from dcc_mcp_core.skill import skill_entry, skill_success

from .common import R, active_project, audit, resolve_rpp


@skill_entry
def main(project_path: str):
    path = resolve_rpp(project_path)
    current = R.EnumProjects(-1, "", 4096)[2]
    if path.exists() and str(path) != current:
        raise FileExistsError("Will not overwrite another existing project")
    path.parent.mkdir(parents=True, exist_ok=True)
    R.GetSetProjectInfo_String(active_project(), "RENDER_FILE", "renders", True)
    R.Main_SaveProjectEx(active_project(), str(path), 8)
    if not path.is_file() or path.stat().st_size < 100:
        raise RuntimeError("Native project save did not create a valid file")
    result = audit()
    if Path(result["project"]).resolve() != path or result["dirty"]:
        raise RuntimeError("Native project save could not be verified against the active project")
    return skill_success("Native RPP saved", bytes=path.stat().st_size, **result)
