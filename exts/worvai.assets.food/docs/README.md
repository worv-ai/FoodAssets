# worvai.assets.food

Isaac Sim extension that provides food assets (USD) and helpers for spawning items via point instancers.

## Quick Start
- Enable the extension in Isaac Sim.
- Use the provided assets: `popcorn-bucket.usdc`, `popcorn-piece.usdc`.
- Spawn pieces with `worvai.assets.food.items.piece_spawners` (visual or physics).
- Run tests: `./kit/kit --empty --enable omni.kit.test --/exts/omni.kit.test/runTestsAndQuit=true --/exts/omni.kit.test/testExts/0='worvai.assets.food' --ext-folder ./exts --ext-folder ./extscache --ext-folder ./extsDeprecated --ext-folder ./apps --/app/enableStdoutOutput=0 --no-window --allow-root`.

## Notes
- Asset paths are relative to the extension root.
- Asset paths may also be `omniverse://` URLs; `file://` URIs work for local assets when staging Nucleus scenes.
- Spawn APIs accept `container_usd_path` and `piece_usd_path` overrides for external assets.
- For large changes, verify bounds and transforms in a test scene.
- Spawn placement uses collision mesh bounds for spacing to reduce initial overlaps.
- Spawn APIs accept `separation_scale` to tune minimum spacing between pieces.
- Container tracking supports both PointInstancer and physics pieces (when piece prim paths are available).
- Physics piece spawning respects the current sim device; CCD is disabled in GPU dynamics mode.
- GPU dynamics may fall back to CPU for some collision approximations; see Omni Physics collider compatibility.
