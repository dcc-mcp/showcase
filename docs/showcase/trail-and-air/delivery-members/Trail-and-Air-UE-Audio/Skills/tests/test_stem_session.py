"""Hermetic guardrail and native-call tests; these never connect to REAPER."""

import importlib.util
import json
import sys
import types
import wave
from pathlib import Path
from unittest.mock import Mock, call

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "reaper-stem-session" / "scripts"
MUTATORS = [
    "SetCurrentBPM",
    "GetSetProjectInfo",
    "GetSetProjectInfo_String",
    "SetEditCurPos",
    "InsertMedia",
    "GetSetMediaTrackInfo_String",
    "SetMediaTrackInfo_Value",
    "SetTrackColor",
    "AddProjectMarker2",
    "UpdateArrange",
    "Main_SaveProjectEx",
    "Main_openProject",
    "Main_OnCommand",
]


@pytest.fixture
def skill(monkeypatch):
    api = Mock(spec=MUTATORS + ["EnumProjects", "CountTracks", "IsProjectDirty", "GetTrack", "ColorToNative"])
    api.EnumProjects.return_value = ("project", -1, "", 4096)
    api.CountTracks.return_value = 0
    api.IsProjectDirty.return_value = 0
    api.GetTrack.return_value = "track"
    api.ColorToNative.return_value = 0
    client = types.ModuleType("reapy_boost")
    client.reascript_api = api
    monkeypatch.setitem(sys.modules, "reapy_boost", client)
    package_name = "stem_skill_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(SCRIPTS)]
    monkeypatch.setitem(sys.modules, package_name, package)
    modules = {}
    for name in ("common", "create_session", "save_project", "open_project", "render_master", "audit_session"):
        fullname = package_name + "." + name
        spec = importlib.util.spec_from_file_location(fullname, str(SCRIPTS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, fullname, module)
        spec.loader.exec_module(module)
        modules[name] = module
    return types.SimpleNamespace(api=api, **modules)


@pytest.fixture
def manifest(tmp_path):
    directory = tmp_path / "stems"
    directory.mkdir()
    stem = directory / "stem.wav"
    stem.write_bytes(b"RIFF mock media")
    path = directory / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "title": "Test session",
                "bpm": 120,
                "duration_seconds": 32,
                "tracks": [{"name": "Stem", "wav_path": "stem.wav", "gain_linear": 0.7, "pan": -0.2}],
            }
        )
    )
    return path


def assert_no_mutations(api):
    for name in MUTATORS:
        getattr(api, name).assert_not_called()


def assert_error(result, fragment):
    assert result["success"] is False
    assert fragment in result["message"]


@pytest.mark.parametrize("track_count,dirty", [(1, False), (0, True)])
def test_create_refuses_nonempty_or_dirty_project(skill, manifest, tmp_path, track_count, dirty):
    skill.api.CountTracks.return_value = track_count
    skill.api.IsProjectDirty.return_value = dirty
    result = skill.create_session.main(manifest_path=str(manifest), project_path=str(tmp_path / "session.rpp"))
    assert_error(result, "empty, clean")
    assert_no_mutations(skill.api)


def test_create_refuses_existing_project(skill, manifest, tmp_path):
    target = tmp_path / "existing.rpp"
    target.write_text("existing project")
    result = skill.create_session.main(manifest_path=str(manifest), project_path=str(target))
    assert_error(result, "overwrite")
    assert target.read_text() == "existing project"
    assert_no_mutations(skill.api)


@pytest.mark.parametrize("path_kind", ["parent", "absolute", "symlink"])
def test_manifest_paths_cannot_escape_manifest_directory(skill, manifest, tmp_path, path_kind):
    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"outside media")
    if path_kind == "parent":
        wav_path = "../outside.wav"
    elif path_kind == "absolute":
        wav_path = str(outside)
    else:
        link = manifest.parent / "linked.wav"
        link.symlink_to(outside)
        wav_path = link.name
    data = json.loads(manifest.read_text())
    data["tracks"][0]["wav_path"] = wav_path
    manifest.write_text(json.dumps(data))
    result = skill.create_session.main(manifest_path=str(manifest), project_path=str(tmp_path / "session.rpp"))
    assert_error(result, "inside manifest directory")
    assert_no_mutations(skill.api)


def test_render_refuses_existing_target_without_host_mutation(skill, tmp_path):
    target = tmp_path / "master.wav"
    target.write_bytes(b"existing render")
    result = skill.render_master.main(output_path=str(target))
    assert_error(result, "overwrite")
    assert target.read_bytes() == b"existing render"
    assert_no_mutations(skill.api)


def test_open_refuses_dirty_active_project(skill, tmp_path):
    target = tmp_path / "saved.rpp"
    target.write_text("saved project")
    skill.api.IsProjectDirty.return_value = True
    result = skill.open_project.main(project_path=str(target))
    assert_error(result, "Save the active project")
    assert_no_mutations(skill.api)


def test_open_calls_native_api_and_checks_actual_path(skill, tmp_path, monkeypatch):
    target = tmp_path / "saved.rpp"
    target.write_text("saved project")
    monkeypatch.setattr(skill.open_project, "audit", lambda: {"project": str(target), "dirty": False})
    result = skill.open_project.main(project_path=str(target))
    assert result["success"] is True
    skill.api.Main_openProject.assert_called_once_with(str(target))
    assert result["context"]["project"] == str(target)


def test_save_refuses_another_existing_project(skill, tmp_path):
    target = tmp_path / "other.rpp"
    target.write_text("other session")
    skill.api.EnumProjects.return_value = ("project", -1, str(tmp_path / "current.rpp"), 4096)
    result = skill.save_project.main(project_path=str(target))
    assert_error(result, "another existing project")
    assert_no_mutations(skill.api)


def test_create_uses_native_import_and_save(skill, manifest, tmp_path, monkeypatch):
    target = tmp_path / "session.rpp"
    skill.api.CountTracks.side_effect = [0, 0, 1]
    skill.api.Main_SaveProjectEx.side_effect = lambda project, path, flags: Path(path).write_text(
        "<REAPER_PROJECT\n" * 10
    )
    monkeypatch.setattr(skill.create_session, "audit", lambda: {"project": str(target), "dirty": False})
    result = skill.create_session.main(manifest_path=str(manifest), project_path=str(target))
    assert result["success"] is True
    skill.api.SetCurrentBPM.assert_called_once_with("project", 120, True)
    skill.api.InsertMedia.assert_called_once_with(str(manifest.parent / "stem.wav"), 1)
    skill.api.GetSetMediaTrackInfo_String.assert_called_once_with("track", "P_NAME", "Stem", True)
    assert skill.api.SetMediaTrackInfo_Value.call_args_list == [
        call("track", "D_VOL", 0.7),
        call("track", "D_PAN", -0.2),
    ]
    skill.api.Main_SaveProjectEx.assert_called_once_with("project", str(target), 8)
    assert target.is_file()


def test_render_uses_native_offline_command_and_reads_wav(skill, tmp_path):
    target = tmp_path / "master.wav"
    skill.api.CountTracks.return_value = 1

    def native_render(command, flag):
        assert (command, flag) == (42230, 0)
        with wave.open(str(target), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(48000)
            output.writeframes(b"\0" * 4096)

    skill.api.Main_OnCommand.side_effect = native_render
    result = skill.render_master.main(output_path=str(target))
    assert result["success"] is True
    skill.api.Main_OnCommand.assert_called_once_with(42230, 0)
    skill.api.GetSetProjectInfo.assert_any_call("project", "RENDER_CHANNELS", 2, True)
    skill.api.GetSetProjectInfo.assert_any_call("project", "RENDER_SRATE", 48000, True)
    assert result["context"]["sample_rate"] == 48000
    assert result["context"]["channels"] == 2
    assert result["context"]["frames"] == 1024
    assert len(result["context"]["sha256"]) == 64


@pytest.mark.parametrize("invalid_field", ["later_track_name", "title"])
def test_create_validates_all_names_before_mutating(skill, manifest, tmp_path, invalid_field):
    data = json.loads(manifest.read_text())
    if invalid_field == "later_track_name":
        data["tracks"].append({"wav_path": "stem.wav"})
    else:
        data["title"] = ["invalid title"]
    manifest.write_text(json.dumps(data))
    result = skill.create_session.main(manifest_path=str(manifest), project_path=str(tmp_path / "session.rpp"))
    assert_error(result, "nonempty string")
    assert_no_mutations(skill.api)


def test_create_fails_when_native_save_does_not_create_file(skill, manifest, tmp_path, monkeypatch):
    skill.api.CountTracks.side_effect = [0, 0, 1]
    audit = Mock()
    monkeypatch.setattr(skill.create_session, "audit", audit)
    result = skill.create_session.main(manifest_path=str(manifest), project_path=str(tmp_path / "session.rpp"))
    assert_error(result, "save did not create")
    audit.assert_not_called()


@pytest.mark.parametrize("bad_readback", ["dirty", "wrong_path"])
def test_create_verifies_native_save_readback(skill, manifest, tmp_path, monkeypatch, bad_readback):
    target = tmp_path / "session.rpp"
    skill.api.CountTracks.side_effect = [0, 0, 1]
    skill.api.Main_SaveProjectEx.side_effect = lambda project, path, flags: Path(path).write_text(
        "<REAPER_PROJECT\n" * 10
    )
    result_path = str(target if bad_readback == "dirty" else tmp_path / "wrong.rpp")
    monkeypatch.setattr(
        skill.create_session, "audit", lambda: {"project": result_path, "dirty": bad_readback == "dirty"}
    )
    result = skill.create_session.main(manifest_path=str(manifest), project_path=str(target))
    assert_error(result, "save could not be verified")


def test_short_session_regions_stay_within_manifest_duration(skill, manifest, tmp_path, monkeypatch):
    data = json.loads(manifest.read_text())
    data["duration_seconds"] = 1
    manifest.write_text(json.dumps(data))
    target = tmp_path / "session.rpp"
    skill.api.CountTracks.side_effect = [0, 0, 1]
    skill.api.Main_SaveProjectEx.side_effect = lambda project, path, flags: Path(path).write_text(
        "<REAPER_PROJECT\n" * 10
    )
    monkeypatch.setattr(skill.create_session, "audit", lambda: {"project": str(target), "dirty": False})
    result = skill.create_session.main(manifest_path=str(manifest), project_path=str(target))
    assert result["success"] is True
    skill.api.AddProjectMarker2.assert_called_once_with("project", True, 0, 1, "Arrival", -1, 0)


def test_render_refuses_wildcard_filename_before_mutating(skill, tmp_path):
    result = skill.render_master.main(output_path=str(tmp_path / "$project.wav"))
    assert_error(result, "wildcards")
    assert_no_mutations(skill.api)


@pytest.mark.parametrize("channels,sample_rate", [(1, 48000), (2, 44100)])
def test_render_checks_actual_wav_format(skill, tmp_path, channels, sample_rate):
    target = tmp_path / "master.wav"
    skill.api.CountTracks.return_value = 1

    def native_render(command, flag):
        with wave.open(str(target), "wb") as output:
            output.setnchannels(channels)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(b"\0" * 4096)

    skill.api.Main_OnCommand.side_effect = native_render
    result = skill.render_master.main(output_path=str(target))
    assert_error(result, "requested stereo 48 kHz WAV")


def test_save_existing_active_project_rejects_still_dirty_readback(skill, tmp_path, monkeypatch):
    target = tmp_path / "current.rpp"
    target.write_text("<REAPER_PROJECT\n" * 10)
    skill.api.EnumProjects.return_value = ("project", -1, str(target), 4096)
    monkeypatch.setattr(skill.save_project, "audit", lambda: {"project": str(target), "dirty": True})
    result = skill.save_project.main(project_path=str(target))
    assert_error(result, "save could not be verified")
    skill.api.Main_SaveProjectEx.assert_called_once_with("project", str(target), 8)


def test_save_verifies_native_file_and_clean_active_path(skill, tmp_path, monkeypatch):
    target = tmp_path / "saved.rpp"
    skill.api.Main_SaveProjectEx.side_effect = lambda project, path, flags: Path(path).write_text(
        "<REAPER_PROJECT\n" * 10
    )
    monkeypatch.setattr(skill.save_project, "audit", lambda: {"project": str(target), "dirty": False})
    result = skill.save_project.main(project_path=str(target))
    assert result["success"] is True
    skill.api.Main_SaveProjectEx.assert_called_once_with("project", str(target), 8)
    assert result["context"]["bytes"] == target.stat().st_size
