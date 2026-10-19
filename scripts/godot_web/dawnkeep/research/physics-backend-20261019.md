# Supported physics backend repair — 2026-10-19

## Problem and scope

On `7be0530`, the actual desktop and portrait Web tests completed their input and
lifecycle checks but failed strict shutdown with a WorkerThreadPool Group
allocator error. A blank project plus exactly one awaited Group reproduced the
same error. The separate empty Node3D control exited cleanly; treating it as an
active physics-world reproduction was an incorrect diagnostic expectation.

The own-game audio cleanup already removed the former ObjectDB/resource errors.
Additional shutdown sleeps cannot address the remaining Group allocation path.

## Supported candidate

Use `physics/3d/physics_engine="Jolt Physics"` while retaining official Godot
4.6.3 and its existing hash-pinned single-thread Web export. No browser security,
threading/export mode, render threshold, collision shape, mask or gameplay rule
is changed. This is a supported full physics backend, not Dummy physics.

[Official Godot 4.6 documentation](https://docs.godotengine.org/en/4.6/tutorials/physics/using_jolt_physics.html)
describes built-in Jolt selection and differences such as collision margins.
Its [single-thread registration](https://github.com/godotengine/godot/blob/4.6.3-stable/modules/jolt_physics/register_types.cpp#L39-L58)
and [individual-task job implementation](https://github.com/godotengine/godot/blob/4.6.3-stable/modules/jolt_physics/spaces/jolt_job_system.cpp#L73-L184)
provide a reason to test this candidate. Source inspection is not Web acceptance.

The [latest official 4.7.2 release](https://godotengine.org/download/archive/4.7.2-stable/)
was also inspected. Its [Group cleanup source](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/object/worker_thread_pool.cpp#L727-L760)
still excludes cleanup in single-thread builds, so a broad engine upgrade was
not selected merely to change versions.

## Required verification

- Preserve the original Group-error reproduction and empty Node3D control.
- Compare real capsule/box collision and ray queries in active GodotPhysics3D
  and Jolt worlds using the exact Web template. Jolt must quit cleanly.
- Run the actual game's unchanged strict browser engine-error gate in both
  viewports. A successful diagnostic cannot override a game failure.
- Recheck tower collision, click steering, sold-tower collision removal, box
  blocking/sliding and the floating hero plane, plus existing combat/balance.
- Refresh actual native/Web input, rendered frames and full-campaign evidence
  separately. Physical phone and subjective listening remain distinct reviews.

The isolated one-setting candidate passed the existing complete headless suite
before adoption. New regressions and actual Web/backend comparison are required
on the committed candidate; this record alone does not claim they passed.
