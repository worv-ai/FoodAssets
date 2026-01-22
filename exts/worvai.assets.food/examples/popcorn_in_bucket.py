"""Spawn a popcorn bucket and track pieces while moving the bucket."""

from __future__ import annotations

import argparse
import logging

import numpy as np

from isaacsim import SimulationApp

_logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the demo script."""
    parser = argparse.ArgumentParser(description="Spawn popcorn bucket and track pieces.")
    parser.add_argument("--headless", action="store_true", help="Run Isaac Sim in headless mode.")
    parser.add_argument("--backend", choices=["warp", "numpy"], default="warp", help="Spawn backend.")
    parser.add_argument("--piece-count", type=int, default=100, help="Number of popcorn pieces.")
    parser.add_argument("--force", type=float, default=500.0, help="Lateral force applied to the bucket.")
    parser.add_argument("--steps", type=int, default=240, help="Total simulation steps.")
    parser.add_argument("--force-step", type=int, default=30, help="Step index to apply force.")
    parser.add_argument("--force-steps", type=int, default=10, help="Number of steps to keep the force active.")
    parser.add_argument(
        "--min-displacement",
        type=float,
        default=0.05,
        help="Minimum displacement before applying manual fallback offset.",
    )
    parser.add_argument("--no-physics", action="store_true", help="Disable physics (use point instancer only).")
    parser.add_argument("--piece-mass", type=float, default=0.001, help="Mass of each popcorn piece in kg.")
    return parser.parse_args()


def main() -> None:
    """Run the popcorn bucket demo."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = _parse_args()

    simulation_app = SimulationApp({"headless": args.headless})

    from isaacsim.core.api import World
    from isaacsim.core.prims import GeometryPrim, RigidPrim
    from isaacsim.core.utils.extensions import enable_extension
    from pxr import Gf, UsdLux

    enable_extension("worvai.assets.food")

    from worvai.assets.food.core.manager import FoodBucketManager
    from worvai.assets.food.items.edibles.popcorn import spawn_popcorn_bucket

    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    stage = world.stage
    if not stage.GetPrimAtPath("/World/Light").IsValid():
        light = UsdLux.DistantLight.Define(stage, "/World/Light")
        light.CreateIntensityAttr(3000.0)
        light.CreateAngleAttr(0.53)
        light.AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 0.0, 0.0))

    spawn_kwargs = {
        "bucket_prim_path": "/World/PopcornBucket",
        "instancer_path": "/World/PopcornPieces",
        "piece_count": args.piece_count,
        "spawn_margin": 0.02,
        "fill_ratio": 0.6,
        "backend": args.backend,
        "enable_physics": not args.no_physics,
        "piece_mass": args.piece_mass,
        "apply_bucket_physics": not args.no_physics,
    }
    try:
        bucket = spawn_popcorn_bucket(**spawn_kwargs)
    except Exception as exc:
        if args.backend == "warp":
            _logger.warning(
                "Failed to spawn with warp backend: %s. Falling back to numpy.",
                exc,
            )
            spawn_kwargs["backend"] = "numpy"
            bucket = spawn_popcorn_bucket(**spawn_kwargs)
        else:
            raise

    manager = FoodBucketManager(bucket)

    world.reset()

    # Only apply collision manually if physics wasn't enabled during spawn
    if args.no_physics:
        try:
            geometry = GeometryPrim(bucket.bucket_prim_path)
            geometry.apply_collision_apis()
            geometry.set_collision_approximations(["convexHull"])
        except Exception as exc:
            _logger.warning("Could not apply collision to bucket: %s", exc)

    rigid_bucket = RigidPrim(bucket.bucket_prim_path, name="bucket_rigid")
    rigid_bucket.initialize()

    initial_count = manager.count_pieces_in_container()
    initial_pos, _ = manager.get_container_pose()
    _logger.info(
        "Initial pieces in bucket: %d / %d",
        initial_count,
        bucket.get_piece_count(),
    )

    for step in range(args.steps):
        if args.force_step <= step < args.force_step + args.force_steps:
            force = np.array([[args.force, 0.0, 0.0]], dtype=np.float32)
            rigid_bucket.apply_forces(force, is_global=False)
        elif step == args.force_step + args.force_steps:
            rigid_bucket.apply_forces(np.zeros((1, 3), dtype=np.float32), is_global=False)
        world.step(render=not args.headless)
        if step % 60 == 0:
            count = manager.count_pieces_in_container()
            _logger.info("Step %03d: pieces in bucket = %d", step, count)

    final_pos, _ = manager.get_container_pose()
    displacement = float(np.linalg.norm(final_pos - initial_pos))
    final_count = manager.count_pieces_in_container()

    if displacement < args.min_displacement:
        _logger.info("Bucket did not move enough, applying manual offset for tracking check.")
        rigid_bucket.set_world_poses(
            positions=np.array([[initial_pos[0] + 0.5, initial_pos[1], initial_pos[2]]], dtype=np.float32)
        )
        for _ in range(60):
            world.step(render=not args.headless)
        final_count = manager.count_pieces_in_container()

    _logger.info(
        "Final pieces in bucket: %d / %d (bucket displacement %.3f m)",
        final_count,
        bucket.get_piece_count(),
        displacement,
    )

    simulation_app.close()


if __name__ == "__main__":
    main()
