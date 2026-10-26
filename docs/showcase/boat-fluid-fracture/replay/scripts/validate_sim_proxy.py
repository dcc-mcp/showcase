"""Readback only: require preserved parts/UVs and unchanged frame-1 render shape."""


def validate(hou, check_hires=False):
    source = hou.node("/obj/boat_fluid_source/SHIP_PARTS").geometry()
    proxy = hou.node("/obj/boat_fluid_source/SIM_PARTS_4K").geometry()
    source_names = set(source.primStringAttribValues("name"))
    assert len(source_names) == 17
    assert set(proxy.primStringAttribValues("name")) == source_names
    assert set(proxy.primStringAttribValues("path")) == set(source.primStringAttribValues("path"))
    assert proxy.findVertexAttrib("uv") is not None
    assert 0 < len(proxy.prims()) <= 4000
    result = {"source_primitives": len(source.prims()), "proxy_primitives": len(proxy.prims()),
              "part_count": 17, "preserved_name_path_uv": True}
    if check_hires:
        assert abs(hou.frame() - 1) < 1e-6, "Check rest alignment at frame 1"
        transforms = hou.node("/obj/boat_fluid_output/fragment_transforms").geometry()
        assert len(transforms.points()) == 17
        assert set(transforms.pointStringAttribValues("name")) == source_names
        hires = hou.node("/obj/boat_fluid_output/solved_hires_pieces").geometry()
        assert len(hires.prims()) == len(source.prims())
        assert hires.findVertexAttrib("uv") is not None
        assert hires.boundingBox().isAlmostEqual(source.boundingBox(), 0.002), "DOP pivot/rest alignment changed"
        original_positions = source.pointFloatAttribValues("P")
        solved_positions = hires.pointFloatAttribValues("P")
        assert len(original_positions) == len(solved_positions)
        error = max(abs(a - b) for a, b in zip(original_positions, solved_positions))
        assert error < 0.002, "Frame-1 high-resolution reconstruction changed points"
        result.update(hires_primitives=len(hires.prims()), frame1_max_position_error=error)
    return result


if "hou" in globals():
    result = validate(hou, context.get("check_hires", False))
