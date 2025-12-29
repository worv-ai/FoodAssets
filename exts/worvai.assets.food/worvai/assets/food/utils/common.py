"""Shared helpers for food assets."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

import numpy as np
import omni.kit.app
from isaacsim.core.utils import bounds as bounds_utils
from isaacsim.core.utils import stage as stage_utils
from pxr import Gf, Usd, UsdGeom

try:
    import warp as wp
except Exception:
    wp = None


def update_app(steps: int) -> None:
    if steps <= 0:
        return
    app = omni.kit.app.get_app()
    for _ in range(steps):
        app.update()


async def update_app_async(steps: int) -> None:
    if steps <= 0:
        return
    app = omni.kit.app.get_app()
    for _ in range(steps):
        await app.next_update_async()


def compute_bucket_spawn_bounds(
    bucket_prim_path: str, spawn_margin: float, fill_ratio: float
) -> Tuple[np.ndarray, np.ndarray]:
    if spawn_margin < 0.0:
        raise ValueError("spawn_margin must be >= 0")
    if fill_ratio <= 0.0 or fill_ratio > 1.0:
        raise ValueError("fill_ratio must be in (0, 1]")

    bbox_cache = bounds_utils.create_bbox_cache()
    bounds = bounds_utils.compute_aabb(bbox_cache, bucket_prim_path, include_children=True)
    min_xyz = bounds[:3] + spawn_margin
    max_xyz = bounds[3:] - spawn_margin
    max_xyz[2] = min_xyz[2] + (max_xyz[2] - min_xyz[2]) * fill_ratio

    if np.any(min_xyz >= max_xyz):
        raise ValueError("Computed spawn bounds are invalid; reduce spawn_margin or fill_ratio.")
    return min_xyz, max_xyz


def make_orientation_quat(rotation_xyz_deg: np.ndarray) -> Gf.Quatf:
    rot = Gf.Rotation(Gf.Vec3d(1, 0, 0), float(rotation_xyz_deg[0]))
    rot = rot * Gf.Rotation(Gf.Vec3d(0, 1, 0), float(rotation_xyz_deg[1]))
    rot = rot * Gf.Rotation(Gf.Vec3d(0, 0, 1), float(rotation_xyz_deg[2]))
    return Gf.Quatf(rot.GetQuat())


def sample_rotations(
    randomize_rotation: bool,
    piece_count: int,
    backend: "SpawnBackend",
    seed: Optional[int],
) -> list[Gf.Quatf]:
    if not randomize_rotation:
        return [Gf.Quatf(1.0, 0.0, 0.0, 0.0) for _ in range(piece_count)]
    seed_val = 0 if seed is None else int(seed) + 1337
    rotations = backend.sample_euler_degrees(piece_count, seed_val)
    return [make_orientation_quat(rot) for rot in rotations]


def spawn_pieces_instancer(
    piece_count: int,
    instancer_path: str,
    usd_path: str,
    spawn_bounds: Tuple[np.ndarray, np.ndarray],
    seed: Optional[int],
    piece_scale: Optional[Sequence[float]],
    randomize_rotation: bool,
    backend: Union[str, "SpawnBackend", None] = None,
    prototype_path: Optional[str] = None,
) -> str:
    if not Path(usd_path).is_file():
        raise FileNotFoundError(f"Missing asset at {usd_path}")
    stage = stage_utils.get_current_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    if not stage.GetPrimAtPath("/World").IsValid():
        stage.DefinePrim("/World", "Xform")

    prototype_path = prototype_path or f"{instancer_path}_Prototype"

    instancer_prim = stage.GetPrimAtPath(instancer_path)
    if instancer_prim.IsValid() and not instancer_prim.IsA(UsdGeom.PointInstancer):
        raise ValueError(f"Prim at {instancer_path} is not a PointInstancer.")
    if not instancer_prim.IsValid():
        instancer_prim = stage.DefinePrim(instancer_path, "PointInstancer")

    instancer = UsdGeom.PointInstancer(instancer_prim)
    prototype_prim = stage_utils.add_reference_to_stage(usd_path, prototype_path)
    instancer.CreatePrototypesRel().SetTargets([prototype_prim.GetPath()])

    min_xyz, max_xyz = spawn_bounds
    backend_obj = get_spawn_backend(backend)
    positions = backend_obj.sample_positions(min_xyz, max_xyz, piece_count, seed)
    proto_indices = [0] * piece_count

    instancer.CreatePositionsAttr().Set([Gf.Vec3f(*pos) for pos in positions])
    instancer.CreateProtoIndicesAttr().Set(proto_indices)

    orientations = sample_rotations(randomize_rotation, piece_count, backend_obj, seed)
    instancer.CreateOrientationsAttr().Set(orientations)

    if piece_scale:
        instancer.CreateScalesAttr().Set([Gf.Vec3f(*piece_scale) for _ in range(piece_count)])

    return instancer_path


def quat_to_numpy(quat: Union[Gf.Quatf, Gf.Quatd]) -> np.ndarray:
    imag = quat.GetImaginary()
    return np.array([quat.GetReal(), imag[0], imag[1], imag[2]], dtype=np.float64)


def quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ],
        dtype=np.float64,
    )


def get_instancer_poses(instancer_path: str) -> Tuple[np.ndarray, np.ndarray]:
    stage = stage_utils.get_current_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    prim = stage.GetPrimAtPath(instancer_path)
    if not prim.IsValid():
        raise RuntimeError(f"Instancer prim not found: {instancer_path}")
    instancer = UsdGeom.PointInstancer(prim)
    positions_attr = instancer.GetPositionsAttr()
    positions = positions_attr.Get() or []

    orientations_attr = instancer.GetOrientationsAttr()
    orientations = orientations_attr.Get() if orientations_attr else []
    if orientations is None or len(orientations) == 0:
        orientations = [Gf.Quatf(1.0, 0.0, 0.0, 0.0) for _ in range(len(positions))]

    xformable = UsdGeom.Xformable(prim)
    world_matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    world_matrix_np = np.array(world_matrix)
    instancer_rotation = world_matrix.ExtractRotation().GetQuat()
    instancer_quat = quat_to_numpy(instancer_rotation)

    pos_np = np.array([[p[0], p[1], p[2]] for p in positions], dtype=np.float64)
    if len(pos_np) == 0:
        return pos_np, np.zeros((0, 4), dtype=np.float64)

    pos_h = np.concatenate([pos_np, np.ones((pos_np.shape[0], 1), dtype=np.float64)], axis=1)
    world_pos = (pos_h @ world_matrix_np.T)[:, :3]

    ori_np = np.zeros((len(orientations), 4), dtype=np.float64)
    for idx, quat in enumerate(orientations):
        local_quat = quat_to_numpy(quat)
        ori_np[idx] = quat_multiply(instancer_quat, local_quat)

    return world_pos, ori_np


class SpawnBackend:
    name = "base"

    def sample_positions(
        self, min_xyz: np.ndarray, max_xyz: np.ndarray, count: int, seed: Optional[int]
    ) -> np.ndarray:
        raise NotImplementedError

    def sample_euler_degrees(self, count: int, seed: Optional[int]) -> np.ndarray:
        raise NotImplementedError


class NumpyBackend(SpawnBackend):
    name = "numpy"

    def sample_positions(
        self, min_xyz: np.ndarray, max_xyz: np.ndarray, count: int, seed: Optional[int]
    ) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return rng.uniform(min_xyz, max_xyz, size=(count, 3))

    def sample_euler_degrees(self, count: int, seed: Optional[int]) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return rng.uniform(0.0, 360.0, size=(count, 3))


class WarpBackend(SpawnBackend):
    name = "warp"

    def __init__(self, device: Optional[str] = None):
        if wp is None:
            raise RuntimeError("Warp is not available.")
        wp.init()
        if device is None:
            device = "cuda" if wp.is_cuda_available() else "cpu"
        self._device = device

    def sample_positions(
        self, min_xyz: np.ndarray, max_xyz: np.ndarray, count: int, seed: Optional[int]
    ) -> np.ndarray:
        seed_val = 0 if seed is None else int(seed)
        out = wp.empty(shape=(count,), dtype=wp.vec3, device=self._device)
        wp.launch(
            _WARP_SAMPLE_POSITIONS,
            dim=count,
            inputs=[wp.vec3(*min_xyz), wp.vec3(*max_xyz), seed_val, out],
            device=self._device,
        )
        return out.numpy()

    def sample_euler_degrees(self, count: int, seed: Optional[int]) -> np.ndarray:
        seed_val = 0 if seed is None else int(seed)
        out = wp.empty(shape=(count,), dtype=wp.vec3, device=self._device)
        wp.launch(
            _WARP_SAMPLE_EULER,
            dim=count,
            inputs=[seed_val, out],
            device=self._device,
        )
        return out.numpy()


def get_spawn_backend(backend: Union[str, SpawnBackend, None]) -> SpawnBackend:
    if isinstance(backend, SpawnBackend):
        return backend
    if backend is None or backend == "numpy":
        return NumpyBackend()
    if backend == "warp":
        return WarpBackend()
    raise ValueError(f"Unknown backend: {backend}")


if wp is not None:

    @wp.kernel
    def _WARP_SAMPLE_POSITIONS(min_v: wp.vec3, max_v: wp.vec3, seed: int, out: wp.array(dtype=wp.vec3)):
        tid = wp.tid()
        state = wp.rand_init(seed, tid)
        out[tid] = wp.vec3(
            wp.randf(state, min_v.x, max_v.x),
            wp.randf(state, min_v.y, max_v.y),
            wp.randf(state, min_v.z, max_v.z),
        )

    @wp.kernel
    def _WARP_SAMPLE_EULER(seed: int, out: wp.array(dtype=wp.vec3)):
        tid = wp.tid()
        state = wp.rand_init(seed, tid)
        out[tid] = wp.vec3(
            wp.randf(state, 0.0, 360.0),
            wp.randf(state, 0.0, 360.0),
            wp.randf(state, 0.0, 360.0),
        )
