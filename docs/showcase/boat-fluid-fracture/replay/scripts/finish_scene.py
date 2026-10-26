"""Set scene timing and branch flags, without deleting or evaluating simulation frames."""


def finish_scene(hou, stage):
    if stage == "blank":
        assert not hou.node("/obj").children(), "Open a separate empty scene; this script never clears scenes"
        for path in ("/mat/boat_split_wood", "/mat/boat_water", "/mat/boat_pool_floor",
                     "/out/boat_fluid_beauty"):
            assert hou.node(path) is None, "Reserved replay node already exists: " + path
        hou.setFps(24)
        hou.setFrame(1)
        return {"empty_object_network": True, "fps": hou.fps(), "frame": hou.frame()}
    assert stage == "finish"
    assert abs(hou.fps() - 24) < 1e-6 and abs(hou.frame() - 1) < 1e-6
    # The typed node builder does not expose node display/render flags.
    for path in ("/obj/boat_fluid_source", "/obj/boat_fluid_dop"):
        hou.node(path).setDisplayFlag(False)
    beauty = hou.node("/obj/boat_fluid_output/BEAUTY")
    beauty.setDisplayFlag(True)
    beauty.setRenderFlag(True)
    floor = hou.node("/obj/boat_pool_base/base")
    floor.setDisplayFlag(True)
    floor.setRenderFlag(True)
    output = hou.node("/obj/boat_fluid_output")
    assert output.renderNode() == beauty
    assert hou.node("/out/boat_fluid_beauty").evalParm("vobject") == "boat_fluid_output boat_pool_base"
    return {"fps": hou.fps(), "render_geometry": beauty.path(), "simulation_advanced": False}


if "hou" in globals():
    result = finish_scene(hou, context["stage"])
