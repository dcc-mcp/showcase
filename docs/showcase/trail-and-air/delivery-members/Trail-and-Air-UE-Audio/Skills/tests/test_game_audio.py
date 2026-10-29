"""Isolated game-audio contract tests; no live host or existing audio is touched."""

import copy
import importlib.util
import json
import sys
import types
import wave
from pathlib import Path
from unittest.mock import Mock

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "reaper-game-audio" / "scripts"
MUTATORS = [
    "SetCurrentBPM",
    "GetSetProjectInfo",
    "GetSetProjectInfo_String",
    "InsertTrackAtIndex",
    "GetSetMediaTrackInfo_String",
    "AddMediaItemToTrack",
    "AddTakeToMediaItem",
    "PCM_Source_CreateFromFile",
    "SetMediaItemTake_Source",
    "GetSetMediaItemTakeInfo_String",
    "SetMediaItemInfo_Value",
    "AddProjectMarker2",
    "UpdateArrange",
    "Main_SaveProjectEx",
    "Main_OnCommand",
]


@pytest.fixture
def game(monkeypatch):
    api = Mock(spec=MUTATORS + ["EnumProjects", "CountTracks", "IsProjectDirty", "GetTrack", "GetAppVersion"])
    api.EnumProjects.return_value = ("project", -1, "", 4096)
    api.CountTracks.return_value = 0
    api.IsProjectDirty.return_value = False
    api.GetAppVersion.return_value = "7.82"
    api.PCM_Source_CreateFromFile.return_value = "(PCM_source*)0x0000000000000001"
    api.GetTrack.return_value = "track"
    api.AddMediaItemToTrack.return_value = "item"
    api.AddTakeToMediaItem.return_value = "take"
    client = types.ModuleType("reapy_boost")
    client.reascript_api = api
    monkeypatch.setitem(sys.modules, "reapy_boost", client)
    package_name = "game_skill_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(SCRIPTS)]
    monkeypatch.setitem(sys.modules, package_name, package)
    synthesis = types.ModuleType(package_name + ".synthesis")
    synthesis.generate = Mock()
    monkeypatch.setitem(sys.modules, synthesis.__name__, synthesis)
    modules = {}
    for name in ("generate_pack", "render_assets"):
        fullname = package_name + "." + name
        spec = importlib.util.spec_from_file_location(fullname, str(SCRIPTS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, fullname, module)
        spec.loader.exec_module(module)
        modules[name] = module
    return types.SimpleNamespace(api=api, synthesize=synthesis.generate, **modules)


def assert_no_mutations(game):
    for name in MUTATORS:
        getattr(game.api, name).assert_not_called()
    game.synthesize.assert_not_called()


def write_wav(path, frames, channels, sample_rate=48000, width=3):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(sample_rate)
        output.writeframes(b"\0" * (frames * channels * width))


def source_assets():
    return [
        {
            "id": "asset_" + str(index),
            "name": "Asset " + str(index),
            "category": "interaction",
            "surface": None,
            "wav_path": "asset_" + str(index) + ".wav",
            "path": "asset_" + str(index) + ".wav",
            "native_export_target": "asset_" + str(index) + ".wav",
            "native_export_target_name": "asset_" + str(index) + ".wav",
            "frames": 480 * index,
            "channels": index,
            "sample_rate": 48000,
            "bit_depth": 24,
            "sha256": str(index) * 64,
        }
        for index in (1, 2)
    ]


@pytest.fixture
def atlas(game, tmp_path):
    root = tmp_path / "atlas"
    media = root / "media"
    media.mkdir(parents=True)
    project = root / "Trail-and-Air.rpp"
    project.write_text("<REAPER_PROJECT\n" * 10)
    assets = source_assets()
    for asset in assets:
        write_wav(media / asset["wav_path"], asset["frames"], asset["channels"])
    metadata = {"sample_rate": 48000, "assets": assets, "tracks": copy.deepcopy(assets)}
    (media / "manifest.json").write_text(json.dumps(metadata))
    cursor = 0
    regions = []
    for asset in assets:
        regions.append(
            {
                "id": asset["id"],
                "target": asset["native_export_target_name"],
                "frames": asset["frames"],
                "channels": asset["channels"],
                "start_frame": cursor,
                "end_frame": cursor + asset["frames"],
            }
        )
        cursor += asset["frames"] + 24000
    (root / "atlas.json").write_text(json.dumps({"sample_rate": 48000, "assets": regions}))
    game.api.EnumProjects.return_value = ("project", -1, str(project), 4096)
    game.api.CountTracks.return_value = 1
    settings = {}

    def set_info(project, key, value, set_value):
        assert set_value is True
        settings[key] = value

    game.api.GetSetProjectInfo.side_effect = set_info
    game.api.GetSetProjectInfo_String.side_effect = set_info

    def render(command, flags):
        assert (command, flags) == (42230, 0)
        frames = round((settings["RENDER_ENDPOS"] - settings["RENDER_STARTPOS"]) * 48000)
        target = Path(settings["RENDER_FILE"]) / (settings["RENDER_PATTERN"] + ".wav")
        write_wav(target, frames, settings["RENDER_CHANNELS"])

    game.api.Main_OnCommand.side_effect = render
    return types.SimpleNamespace(root=root, assets=assets, regions=regions, settings=settings, render=render)


@pytest.mark.parametrize("existing", [False, True])
def test_generate_accepts_only_new_or_empty_target(game, tmp_path, existing):
    root = tmp_path / "new-pack"
    if existing:
        root.mkdir()

    def generate(media, sample_rate, seed):
        assert (sample_rate, seed) == (48000, 73)
        media.mkdir(parents=True)
        return {"assets": source_assets()}

    game.synthesize.side_effect = generate
    game.api.Main_SaveProjectEx.side_effect = lambda project, path, flags: Path(path).write_text(
        "<REAPER_PROJECT\n" * 10
    )
    result = game.generate_pack.main(output_dir=str(root))
    assert result["success"] is True
    assert result["context"]["assets"] == 2
    assert game.api.PCM_Source_CreateFromFile.call_count == 2
    game.api.Main_SaveProjectEx.assert_called_once_with("project", str(root / "Trail-and-Air.rpp"), 8)
    assert len(json.loads((root / "atlas.json").read_text())["assets"]) == 2


def test_generate_refuses_nonempty_target_before_host_mutation(game, tmp_path):
    (tmp_path / "keep.txt").write_text("existing")
    result = game.generate_pack.main(output_dir=str(tmp_path))
    assert result["success"] is False
    assert "empty output directory" in result["message"]
    assert_no_mutations(game)


@pytest.mark.parametrize("track_count,dirty", [(1, False), (0, True)])
def test_generate_refuses_nonempty_or_dirty_project(game, tmp_path, track_count, dirty):
    game.api.CountTracks.return_value = track_count
    game.api.IsProjectDirty.return_value = dirty
    result = game.generate_pack.main(output_dir=str(tmp_path / "new-pack"))
    assert result["success"] is False
    assert "empty clean" in result["message"]
    assert_no_mutations(game)


@pytest.mark.parametrize("seed", [True, -1, 2147483648, "73"])
def test_generate_rejects_invalid_seed_without_changes(game, tmp_path, seed):
    result = game.generate_pack.main(output_dir=str(tmp_path / "new-pack"), seed=seed)
    assert result["success"] is False
    assert_no_mutations(game)


def test_render_refuses_nonempty_output_directory(game, atlas):
    out = atlas.root / "renders"
    out.mkdir()
    (out / "existing.wav").write_bytes(b"existing output")
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert_no_mutations(game)


@pytest.mark.parametrize("target", ["../escape.wav", "/tmp/escape.wav", "$project.wav"])
def test_render_rejects_unsafe_target_before_any_render(game, atlas, target):
    data = json.loads((atlas.root / "atlas.json").read_text())
    data["assets"][1]["target"] = target
    (atlas.root / "atlas.json").write_text(json.dumps(data))
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert_no_mutations(game)


def test_render_invokes_native_renderer_once_per_asset(game, atlas):
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is True
    assert result["context"]["asset_count"] == 2
    assert game.api.Main_OnCommand.call_count == 2
    for asset in atlas.assets:
        with wave.open(str(atlas.root / "renders" / asset["native_export_target_name"]), "rb") as output:
            assert (output.getframerate(), output.getsampwidth(), output.getnchannels(), output.getnframes()) == (
                48000,
                3,
                asset["channels"],
                asset["frames"],
            )
    assert (atlas.root / "native-render-validation.json").is_file()


@pytest.mark.parametrize("wrong_field", ["rate", "width", "channels", "frames"])
def test_render_rejects_wrong_native_output_format(game, atlas, wrong_field):
    def render_wrong(command, flags):
        target = Path(atlas.settings["RENDER_FILE"]) / (atlas.settings["RENDER_PATTERN"] + ".wav")
        asset = atlas.assets[0]
        write_wav(
            target,
            asset["frames"] + (1 if wrong_field == "frames" else 0),
            2 if wrong_field == "channels" else asset["channels"],
            44100 if wrong_field == "rate" else 48000,
            2 if wrong_field == "width" else 3,
        )

    game.api.Main_OnCommand.side_effect = render_wrong
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert "sample format/duration mismatch" in result["message"]
    assert game.api.Main_OnCommand.call_count == 1


@pytest.mark.parametrize(
    "problem", ["empty", "count", "id", "duplicate_id", "duplicate_target", "negative", "fractional"]
)
def test_render_validates_atlas_and_manifest_before_mutating(game, atlas, problem):
    path = atlas.root / "atlas.json"
    data = json.loads(path.read_text())
    if problem == "empty":
        data["assets"] = []
    elif problem == "count":
        data["assets"].pop()
    elif problem == "id":
        data["assets"][1]["id"] = "unknown_asset"
    elif problem == "duplicate_id":
        data["assets"][1]["id"] = data["assets"][0]["id"]
    elif problem == "duplicate_target":
        data["assets"][1]["target"] = data["assets"][0]["target"]
    elif problem == "negative":
        data["assets"][0]["start_frame"] = -10
        data["assets"][0]["end_frame"] -= 10
    else:
        data["assets"][0]["start_frame"] = 0.5
        data["assets"][0]["end_frame"] += 0.5
    path.write_text(json.dumps(data))
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert_no_mutations(game)


def test_render_refuses_dirty_active_atlas(game, atlas):
    game.api.IsProjectDirty.return_value = True
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert_no_mutations(game)


def test_partial_failure_returns_completed_assets_and_failed_id(game, atlas):
    def fail_second(command, flags):
        if game.api.Main_OnCommand.call_count == 2:
            raise RuntimeError("Native renderer interrupted")
        atlas.render(command, flags)

    game.api.Main_OnCommand.side_effect = fail_second
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert result["context"]["completed_count"] == 1
    assert result["context"]["failed_asset_id"] == "asset_2"
    assert [item["id"] for item in result["context"]["results"]] == ["asset_1"]
    assert game.api.Main_OnCommand.call_count == 2
    assert not (atlas.root / "renders" / "manifest.json").exists()


def test_render_matches_metadata_by_id_instead_of_position(game, atlas):
    path = atlas.root / "media" / "manifest.json"
    data = json.loads(path.read_text())
    data["assets"].reverse()
    path.write_text(json.dumps(data))
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is True
    rendered = {asset["id"]: asset for asset in result["context"]["results"]}
    metadata = json.loads((atlas.root / "renders" / "manifest.json").read_text())
    for asset in metadata["assets"]:
        assert asset["sha256"] == rendered[asset["id"]]["sha256"]
    for asset in metadata["tracks"]:
        assert asset["sha256"] == rendered[asset["id"]]["sha256"]


@pytest.mark.parametrize(
    "problem", ["source_count", "source_id", "source_target", "source_path", "source_frames", "source_alias"]
)
def test_render_rejects_inconsistent_source_manifest_before_changes(game, atlas, problem):
    path = atlas.root / "media" / "manifest.json"
    data = json.loads(path.read_text())
    if problem == "source_count":
        data["assets"].pop()
    elif problem == "source_id":
        data["assets"][1]["id"] = "unknown"
    elif problem == "source_target":
        data["assets"][1]["native_export_target_name"] = "wrong.wav"
    elif problem == "source_path":
        data["assets"][1]["wav_path"] = "../outside.wav"
    elif problem == "source_frames":
        data["assets"][1]["frames"] += 1
    else:
        data["tracks"][1]["sha256"] = "a" * 64
    path.write_text(json.dumps(data))
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert_no_mutations(game)


@pytest.mark.parametrize("target", ["..\\escape.wav", "C:\\escape.wav", "unsafe\x00.wav"])
def test_render_rejects_cross_platform_unsafe_filenames(game, atlas, target):
    path = atlas.root / "atlas.json"
    data = json.loads(path.read_text())
    data["assets"][0]["target"] = target
    path.write_text(json.dumps(data))
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert_no_mutations(game)


def test_render_refuses_symlinked_output_directory(game, atlas, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (atlas.root / "renders").symlink_to(outside, target_is_directory=True)
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert list(outside.iterdir()) == []
    assert_no_mutations(game)


def test_partial_failure_is_journaled_and_retry_does_not_overwrite(game, atlas):
    def fail_second(command, flags):
        if game.api.Main_OnCommand.call_count == 2:
            raise RuntimeError("Native renderer interrupted")
        atlas.render(command, flags)

    game.api.Main_OnCommand.side_effect = fail_second
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    journal = json.loads((atlas.root / "native-render-validation.json").read_text())
    assert journal["status"] == "failed"
    assert journal["completed_count"] == 1
    assert journal["total_count"] == 2
    assert journal["failed_asset_id"] == "asset_2"
    assert journal["stage"] == "render"
    assert [asset["id"] for asset in journal["assets"]] == ["asset_1"]
    first_bytes = (atlas.root / "renders" / "asset_1.wav").read_bytes()
    retry = game.render_assets.main(project_dir=str(atlas.root))
    assert retry["success"] is False
    assert "empty" in retry["message"]
    assert game.api.Main_OnCommand.call_count == 2
    assert (atlas.root / "renders" / "asset_1.wav").read_bytes() == first_bytes
    assert json.loads((atlas.root / "native-render-validation.json").read_text()) == journal


def test_save_failure_reports_all_completed_renders_without_publishing_manifest(game, atlas):
    game.api.Main_SaveProjectEx.side_effect = RuntimeError("Save failed")
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is False
    assert result["context"]["completed_count"] == 2
    assert result["context"]["failed_asset_id"] is None
    assert result["context"]["stage"] == "save_project"
    assert result["context"]["remaining_asset_ids"] == []
    assert not (atlas.root / "renders" / "manifest.json").exists()
    report = json.loads((atlas.root / "native-render-validation.json").read_text())
    assert report["status"] == "failed"
    assert len(report["assets"]) == 2


def test_success_journal_is_complete_and_source_manifest_is_unchanged(game, atlas):
    source = atlas.root / "media" / "manifest.json"
    before = source.read_bytes()
    result = game.render_assets.main(project_dir=str(atlas.root))
    assert result["success"] is True
    assert source.read_bytes() == before
    report = json.loads((atlas.root / "native-render-validation.json").read_text())
    assert report["status"] == "completed"
    assert report["completed_count"] == report["total_count"] == 2
    assert report["failed_asset_id"] is None
    assert not (atlas.root / "native-render-validation.json.tmp").exists()
