# media/

Approved showcase artifacts, one directory per proposition:

```text
media/<YYYY-MM-DD>-<slug>/
```

Each directory holds the artifact (GIF / image / video) and a short `README.md` with:

- one sentence on what the artifact proves
- host version, adapter and core versions
- the verification level reached (in-host / gateway / real tool return / cross-host conservation)

## Publication gate

Nothing is committed here by default. Artifacts are drafted internally and land here only after explicit, per-artifact approval. An artifact can be approved, sent back for a re-shoot, or withheld — the gate is per item, not per batch.

## Media handling

- Prefer Git LFS or an external link for anything large.
- Keep GIFs loopable and small; keep stills wide enough to read but not so large that the page stalls.
- Never commit an artifact that leaks internal paths, hosts, or credentials. A sample that is safe to publish is clean before it is published.
