CAMPAIGN EVIDENCE / PUBLIC PRIVACY DERIVATIVE

Retained: 10000 campaign records, 20 historical three-floor counterexamples, and 1362 complete independent failure replays.
Only journal header engine_pid fields are replaced by equal-length ASCII spaces. Every subsequent journal byte, line number, byte offset and byte length is preserved. Existing locators, including every present line SHA-256, were read back against public bytes.
Current journal_sha256/manifest entries identify public derivatives; source_original_* fields and SOURCE-HASHES.json retain original measured hashes. Seeds, rule fingerprints, decisions, failure counts and terminal states are retained. Private original archives/journals are not included.
The complete proof journals are stored once inside campaign-evidence.zip, not duplicated as large standalone gzip files. Small core reports and replay summaries have deterministic mtime=0 gzip copies.

The main ZIP uses standard ZIP_LZMA. Extract with: python -m zipfile -e campaign-evidence.zip destination
This is packaging of existing evidence, not a new engine/browser run, a human-playtime claim, or a deployed game. Frozen original three-floor source/docs were checked and not republished or uploaded.
