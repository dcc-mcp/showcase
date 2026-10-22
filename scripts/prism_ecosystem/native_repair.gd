@tool
extends RefCounted

# Candidate only. Execute through the official Godot editor-script tool after
# independent review. No OS.execute/process creation and no game source edits.
const NAMES = ["project.godot", "main.tscn", "prism_tide.gd", "prism_tide.gd.uid", "export_presets.cfg"]
const KEYS = ["editor/movie_writer/movie_file", "editor/movie_writer/fps", "editor/run/main_run_args"]

func controls() -> Dictionary:
 var root = EditorInterface.get_base_control().get_tree().root
 var dialogs = root.find_children("*", "RunInstancesDialog", true, false)
 assert(dialogs.size() == 1, "Expected exactly one native RunInstancesDialog")
 var dialog = dialogs[0]
 var checks = dialog.find_children("*", "CheckBox", true, false)
 assert(checks.size() == 1, "Native single-instance UI contract changed")
 var boxes = []
 var timers = []
 for child in dialog.get_children():
  if child is VBoxContainer: boxes.append(child)
  if child is Timer: timers.append(child)
 assert(boxes.size() == 1 and timers.size() == 2, "Native dialog structure changed")
 for timer in timers:
  assert(timer.is_stopped(), "Pending user settings timer")
 var grids = []
 for child in boxes[0].get_children():
  if child is GridContainer: grids.append(child)
 assert(grids.size() == 1, "Native arguments grid count changed")
 var edits = []
 for child in grids[0].get_children():
  if child is LineEdit: edits.append(child)
 assert(edits.size() == 2, "Native arguments grid changed")
 var main_args: LineEdit = edits[0]
 return {"single":not checks[0].button_pressed, "args":main_args.text,
  "focused":main_args.has_focus(), "feature_tags":edits[1].text, "process_frame":Engine.get_process_frames()}

func inspect(_arguments: Dictionary) -> Dictionary:
 var live = controls()
 return {"engine":Engine.get_version_info(), "pid":OS.get_process_id(),
  "display_driver":DisplayServer.get_name(), "rendering_method":RenderingServer.get_current_rendering_method(),
  "live":live, "playing":EditorInterface.is_playing_scene(),
  "movie_enabled":EditorInterface.is_movie_maker_enabled(),
  "movie_file":ProjectSettings.get_setting(KEYS[0]),
  "fps":ProjectSettings.get_setting(KEYS[1]),
  "configured_args":ProjectSettings.get_setting(KEYS[2]),
  "project_sha256":FileAccess.get_sha256("res://project.godot")}

func snapshot(_arguments: Dictionary) -> Dictionary:
 assert(not EditorInterface.is_playing_scene())
 var old = {"movie_enabled":EditorInterface.is_movie_maker_enabled(), "settings":{},
  "project_sha256":FileAccess.get_sha256("res://project.godot")}
 for key in KEYS:
  old.settings[key] = {"present":ProjectSettings.has_setting(key), "value":ProjectSettings.get_setting(key)}
 return old

# JSON transports integral values as FLOAT in Godot. Normalize only the known
# integer setting, reject fractional/non-numeric input, then retain full equality.
func normalized_before(value: Dictionary) -> Dictionary:
 var old = value.duplicate(true)
 var fps = old.settings[KEYS[1]].value
 assert(typeof(fps) == TYPE_INT or typeof(fps) == TYPE_FLOAT, "FPS snapshot must be numeric")
 assert(fps >= 1 and fps <= 300 and fps == int(fps), "FPS snapshot must be exact integral")
 old.settings[KEYS[1]].value = int(fps)
 return old

func configure(arguments: Dictionary) -> Dictionary:
 assert(not EditorInterface.is_playing_scene(), "Existing runtime is not owned")
 var live = controls()
 assert(live.single and not live.focused and String(live.feature_tags).is_empty(), "Need fresh single-instance editor with unfocused args")
 var frames = int(arguments.frames)
 assert(frames == 3 or frames == 450, "Only qualification or approved full capture")
 var output = String(arguments.movie_file)
 assert(output.is_absolute_path() and output.ends_with("/frame.png") and not ".." in output)
 assert(DirAccess.dir_exists_absolute(output.get_base_dir()))
 var directory = DirAccess.open(output.get_base_dir())
 assert(directory != null, "Cannot inspect output directory")
 directory.include_hidden = true
 assert(directory.get_files().is_empty() and directory.get_directories().is_empty(), "Output must be fresh")
 var old = normalized_before(arguments.before)
 assert(old == snapshot({}), "Caller must persist fresh snapshot before any mutation")
 var run_args = "--quit-after %d -- --demo" % frames
 ProjectSettings.set_setting(KEYS[0], output)
 ProjectSettings.set_setting(KEYS[1], 30)
 ProjectSettings.set_setting(KEYS[2], run_args)
 EditorInterface.set_movie_maker_enabled(true)
 assert(FileAccess.get_sha256("res://project.godot") == old.project_sha256)
 return {"configured":true, "before":old, "expected_args":run_args, "configured_frame":Engine.get_process_frames(),
  "note":"Caller must wait a later editor tick and inspect actual cached args before typed play_scene."}

func restore(arguments: Dictionary) -> Dictionary:
 assert(not EditorInterface.is_playing_scene(), "Never restore settings while runtime is active")
 var old = normalized_before(arguments.before)
 for key in KEYS:
  assert(old.settings.has(key))
  ProjectSettings.set_setting(key, old.settings[key].value if old.settings[key].present else null)
 EditorInterface.set_movie_maker_enabled(bool(old.movie_enabled))
 assert(FileAccess.get_sha256("res://project.godot") == old.project_sha256)
 return {"restoration_requested":true, "cached_readback_pending":true, "project_sha256":old.project_sha256}

func pack_sources(arguments: Dictionary) -> Dictionary:
 assert(not EditorInterface.is_playing_scene())
 var source_root = String(arguments.source_root)
 var destination = String(arguments.output_path)
 assert(source_root.is_absolute_path() and destination.is_absolute_path())
 assert(not ".." in source_root and not ".." in destination)
 assert(destination.ends_with(".pck") and not FileAccess.file_exists(destination))
 assert(DirAccess.dir_exists_absolute(destination.get_base_dir()))
 assert(arguments.sha256.size() == NAMES.size())
 var members = []
 for name in NAMES:
  var path = source_root.path_join(name)
  assert(FileAccess.file_exists(path))
  var file = FileAccess.open(path, FileAccess.READ)
  assert(file != null and file.get_length() <= 16384)
  file.close()
  var digest = FileAccess.get_sha256(path)
  assert(digest == String(arguments.sha256[name]))
  members.append({"path":"res://"+name,"sha256":digest})
 var packer = PCKPacker.new()
 var code = packer.pck_start(destination)
 if code != OK:
  return {"packed":false, "stage":"pck_start", "error_code":code, "output_path":destination}
 for name in NAMES:
  code = packer.add_file("res://"+name, source_root.path_join(name))
  if code != OK:
   return {"packed":false, "stage":"add_file", "member":name, "error_code":code,
    "output_path":destination, "partial_output_possible":true}
 code = packer.flush()
 if code != OK:
  return {"packed":false, "stage":"flush", "error_code":code, "output_path":destination,
   "partial_output_possible":true}
 for member in members:
  assert(FileAccess.get_sha256(source_root.path_join(String(member.path).trim_prefix("res://"))) == member.sha256)
 return {"packed":true, "route":"native PCKPacker source pack, not preset export", "members":members,
  "output_sha256":FileAccess.get_sha256(destination), "native_reopen_pending":true}
