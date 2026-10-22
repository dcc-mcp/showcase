extends SceneTree
# Verification only: run on the actual --main-pack from an empty working project.
# Source-inputs is a separate frozen receipt, never accepted from pack contents.
func _initialize():
 var args = OS.get_cmdline_user_args()
 assert(args.size() == 2 and args[0] == "--test")
 var receipt_path = args[1]
 assert(receipt_path.is_absolute_path())
 var receipt = JSON.parse_string(FileAccess.get_file_as_string(receipt_path))
 assert(receipt is Dictionary and receipt.schema == 1)
 var expected = receipt.files
 assert(expected.size() == 5)
 var root = DirAccess.open("res://")
 assert(root != null)
 root.include_hidden = true
 var actual_names = Array(root.get_files())
 actual_names.sort()
 var expected_names = Array(expected.keys())
 expected_names.sort()
 assert(actual_names == expected_names and root.get_directories().is_empty())
 var actual = {}
 for name in expected_names:
  var path = "res://" + String(name)
  var file = FileAccess.open(path, FileAccess.READ)
  assert(file != null and file.get_length() == expected[name].bytes)
  file.close()
  var digest = FileAccess.get_sha256(path)
  assert(digest == expected[name].sha256)
  actual[name] = digest
 print("PRISM_PACK_MEMBERS " + JSON.stringify({"passed":true,"members":actual}))
 var packed = load("res://main.tscn")
 assert(packed is PackedScene)
 var game = packed.instantiate()
 # Original _ready sees --test, prints the original17 checks and requests quit.
 get_root().add_child.call_deferred(game)
