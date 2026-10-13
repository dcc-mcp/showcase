# Artwork-first gallery

The homepage prioritizes the already selected collection's artwork. Display order
is editorial only; it does not rank quality or change collection records. Cover,
video, audio and project bytes continue to come from the selected public manifests.
The source assets, original attribution and established routes are unchanged.

## Preview contract

- Video is assigned a source immediately on entering any part of a card with a fine pointer,
  or an explicit press of the preview control. Touch and keyboard use the button.
- Loading retains the poster with a localized status; the decoded first frame fades in.
  An idle hint makes hover discoverable without presenting a play button on hover-enabled devices.
- Preview is muted, inline and looping. At most one preview is active. Pointer exit,
  offscreen/filter visibility, hidden document and page lifecycle stop playback
  and release the source. An explicit touch press is not cancelled by touch exit.
- Reduced motion and Save-Data disable automatic previews; explicit play remains
  available. Stalled loading times out after 12 seconds with a manual retry. Errors leave the poster, localized message and work link available.
- Browser autoplay follows the [Chrome muted-playback policy](https://developer.chrome.com/blog/autoplay/)
  and [WebKit inline video policy](https://webkit.org/blog/6784/new-video-policies-for-ios/).
  Rejected playback keeps a manual retry button and ordinary detail link.
- Preview controls are separate from the work link. Without JavaScript, the
  artwork and ordinary detail links remain usable; the inactive button is hidden.
- Godot never starts from a gallery preview. Detail-page start controls and the
  existing fallback/download links remain explicit.

Media filters are derived from actual selected result files and validated playable
entries, not from a software name. Search and filters persist through the existing
EN/简中 language switch; source titles and evidence are not rewritten.

The secondary [Agent & Data view](https://dcc-mcp.github.io/showcase/agents/)
projects public workflow records. See [AGENT_DATA.md](AGENT_DATA.md) for its scoped
rights and metadata contract. Public display does not itself grant training or
evaluation rights.

## Acceptance

Run the ordinary build/localization/publication guards, plus:

```sh
python scripts/test_gallery.py
python scripts/test_agent_pages.py
node scripts/test_preview_controls.js
python scripts/gallery_browser_smoke.py --site _site --output /tmp/gallery-preview --expected-head "$(git rev-parse HEAD)"
```

The Gallery preview CI workflow records the exact candidate SHA and real Chromium
screenshots at desktop and 390 × 844 touch viewport sizes. Touch emulation is not a
physical-device test. The original whole-site Browser preview remains responsible
for resource integrity, decoding/seeking, all content routes and both locales.
CI preview evidence does not establish production hosting, MIME/compression,
WebGL availability or a physical device's behavior.
