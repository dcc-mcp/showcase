# Methods and limits

The field has 81 × 65 × 97 points and 491,520 cells. Origin is (-2, -1.6, 0), spacing is (0.05, 0.05, 0.025), and z increases downward. The units are illustrative kilometres, seconds and milliseconds. The sampled formulas are:

- q = ((x−0.2)/0.9)² + ((y+0.1)/0.65)² + ((z−1.2)/0.30)²
- Δt = 220 exp(−q)
- t = 0.6 + 0.4z + 0.025(x²+y²) − Δt/1000

Δt is a positive scalar term subtracted from t. Neither quantity comes from a seismic solver or measured data. No velocity, travel-path, geological or engineering conclusion is supported. The slices are x=0.2, y=−0.1 and z=1.2. The line views are intersections of Δt=80 and Δt=150 with the y=−0.1 section. They use equal camera scale; their full source-domain labels do not claim that every domain edge is visible in the close view.

The VTI input was generated from these formulas by a deterministic Python data recipe. That data generation is not presented as a DCC MCP operation. The native slices, contours, camera and scalar-bar setup, state saves/reopens and image exports were performed through typed ParaView MCP tools. GIMP MCP then imported the five images into independent groups and created nineteen editable text layers.

ParaView 5.13.2, GIMP 3.0.4, Core/server/CLI 0.20.41 and MCP SDK 1.30.0 are the qualified application/runtime versions. The ParaView capability enhancements are merged in the public adapter repository. The latest case run used commit 9b9de65d64f77356eaad4709535c79c49a852eb4. Its successor 4c4939b1a6ee6785d86f74461ea97ff2a34815a9 changes one documentation line; all twenty-four packaged adapter files are identical. Source commits and wheel hashes are recorded separately because a new wheel ZIP timestamp can change an archive hash without changing its installed files. This does not claim a new PyPI release.

The current ParaView reproduction recorded 210 SDK events, 52 adapter operations and 36 completed asynchronous jobs. These are different counting units: events include discovery and polling. Independent calculation verified both scalar formulas at all 510,705 input points. Native geometry and ranges match the sampled sections. Five saved-state reopens and five relocated-state reopens preserved the recorded presentation and exact PNG bytes without reapplying camera or style settings. The original input path was unavailable during relocation and was restored afterward.

Scalar-bar thickness is measured in native points, not guaranteed pixels. CameraClippingRange is not exposed by the tested ParaView 5.13.2 RenderView schema, so presentation equality covers the recorded available properties and actual pixels only. Native MCP reopen admits trusted states saved during the same session and verified copied data; this demonstration does not enable arbitrary external PVSM import. The packaged states can also be opened through ParaView's normal native workflow.

The current GIMP full-authoring recipe recorded 202 SDK events and 45 planned authoring operations. Nineteen text-parasite records, the complete editable hierarchy, imported panel pixels and full 2560 × 1600 decoded RGBA matched after XCF save/reopen. A separate copied-XCF trial recorded 42 events while the declared original master and five image inputs were unavailable; all original files were restored with unchanged hashes. The full-authoring run reproduced the XCF byte for byte. GIMP PNG file-byte equality is not claimed because generated PNG timestamps and thumbnail metadata can differ; decoded RGBA is the image comparator.

The evidence concerns this analytic illustration and the stated versions. It does not establish physical validity, cross-machine pixel identity, every adapter tool, or every native test case.
