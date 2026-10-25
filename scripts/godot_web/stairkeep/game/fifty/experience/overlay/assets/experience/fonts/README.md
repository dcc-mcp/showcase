# First chapter CJK font

`cjk-ui.otf` is the complete, byte-identical pre-existing Noto Sans SC Regular
font, version 2.002, licensed under SIL OFL 1.1. It is not a commercial system
font. Original naming, copyright and embedded license metadata are preserved.
The source and output SHA256 are both
`a2b93e6c2db05d6bbbf6f27d413ec73269735b7b679019c8a5aa9670ff0ffbf2`.

The existing house subsets were inspected first. They lack 209, 255 and 260
codepoints respectively from the initial first-chapter source corpus. The full
8.48 MB font is used for this urgent candidate so concurrent Chinese copy edits
do not immediately break a narrow subset. No font software was installed or
downloaded. A later subset should use the house FontTools workflow, preserve OFL
and copyright metadata, rename any modified family appropriately, and recheck
the final text union.

The source files decode as UTF-8, with no malformed byte sequence or U+FFFD
detected initially. The previous preview Theme set a size without explicitly
bundling and binding a CJK font. This is evidence of a font coverage/loading
gap; it does not prove all reported text problems were encoding errors or rule
out clipping. FontTools cmap success is not a rendered-glyph acceptance claim.

The presenter must set:

```gdscript
theme.default_font = preload("res://assets/experience/fonts/cjk-ui.otf")
```

Labels outside that Theme subtree need the same font assigned explicitly.
Run `python assets/experience/fonts/audit_font.py` from any working directory
after final presenter edits. It updates `cmap-report.json` using a printable
source-text superset including ASCII and punctuation. The script starts no
Godot, browser, server or other application.

See `SOURCE.json`, `FONT-LICENSE.txt` and the unmodified house license reference.
The [official Noto Sans license](https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE)
was checked on 2026-10-25. Actual import, rendered Chinese, long-text clipping and
Web glyph behavior remain pending the root task's authorized acceptance.
