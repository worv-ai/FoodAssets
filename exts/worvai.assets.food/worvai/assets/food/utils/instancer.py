"""Point instancer helpers for food assets."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

import numpy as np
from isaacsim.core.utils import stage as stage_utils
from pxr import Gf, Usd, UsdGeom

from .backend import SpawnBackend, get_spawn_backend
from .orientation import quat_multiply, quat_to_numpy, sample_rotations


def spawn_pieces_instancer(
    piece_count: int,
    instancer_path: str,
    usd_path: str,
    spawn_bounds: Tuple[np.ndarray, np.ndarray],
    seed: Optional[int],
    piece_scale: Optional[Sequence[float]],
    randomize_rotation: bool,
    backend: Union[str, SpawnBackend, None] = None,
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

    if piece_scale is None:
        xformable = UsdGeom.Xformable(prototype_prim)
        if xformable:
            local_transform = xformable.GetLocalTransformation()
            scale_vec = Gf.Transform(local_transform).GetScale()
            proto_scale = (float(scale_vec[0]), float(scale_vec[1]), float(scale_vec[2]))
            if np.all(np.isfinite(proto_scale)) and not np.allclose(proto_scale, 1.0):
                piece_scale = proto_scale

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
        identity = Gf.Quath()
        orientations = [identity for _ in range(len(positions))]

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
