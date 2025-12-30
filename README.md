# FoodAssets

Collection of Isaac Sim assets and extensions. This repo includes the `worvai.assets.food` extension with USD food assets and helpers for spawning instanced pieces.

- Extension path: `FoodAssets/exts/worvai.assets.food`
- Docs: `FoodAssets/exts/worvai.assets.food/docs/README.md`

## Example

Run the popcorn bucket demo:

```bash
cd /path/to/isaac-sim
./python.sh ./extsUser/worvai.assets.food/examples/popcorn_in_bucket.py --headless
```

Args:
- `--headless`: run without UI
- `--backend`: spawn backend (`warp` or `numpy`)
- `--piece-count`: number of popcorn pieces
- `--force`: lateral force applied to the bucket
- `--steps`: total simulation steps
- `--force-step`: step index to start applying force
- `--force-steps`: number of steps to keep force active
- `--min-displacement`: minimum bucket displacement before applying fallback offset
