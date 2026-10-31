"""Small source contract for the first-chapter readability revision."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORLD = (ROOT / "overlay/fifty/view/experience_world.gd").read_text(encoding="utf-8")
PREVIEW = (ROOT / "overlay/fifty/view/preview.gd").read_text(encoding="utf-8")


def test_walkable_guides_are_built_above_the_floor():
    assert 'name = "WalkableTileGuides"' in WORLD
    assert "_draw_walkable_guides()" in WORLD
    assert "if not _rules.walkable([x, y]):" in WORLD
    assert "line.position = _center([x, y])" in WORLD


def test_shop_entry_and_purchase_are_distinct():
    assert "每件商品都有独立购买按钮" in PREVIEW
    assert "E / 空格只负责前往商店，不会自动购买" in PREVIEW


if __name__ == "__main__":
    test_walkable_guides_are_built_above_the_floor()
    test_shop_entry_and_purchase_are_distinct()
    print("readability contract: 2 passed")
