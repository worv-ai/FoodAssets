# worvai.assets.food

Isaac Sim extension that provides food assets (USD) and helpers for spawning items via point instancers.

## Quick Start
- Enable the extension in Isaac Sim.
- Use the provided assets: `popcorn-bucket.usdc`, `popcorn-piece.usdc`.
- Spawn pieces with the point instancer helpers in `worvai.assets.food.utils`.

## Notes
- Asset paths are relative to the extension root.
- Asset paths may also be `omniverse://` URLs; `file://` URIs work for local assets when staging Nucleus scenes.
- For large changes, verify bounds and transforms in a test scene.
- Container tracking supports both PointInstancer and physics pieces (when piece prim paths are available).
- Physics piece spawning respects the current sim device; CCD is disabled in GPU dynamics mode.
- GPU dynamics may fall back to CPU for some collision approximations; see Omni Physics collider compatibility.
