"""Rotation helpers for food assets."""

from __future__ import annotations

from typing import Optional, Union

import numpy as np
from pxr import Gf


def to_quath(quat: Union[Gf.Quath, Gf.Quatf, Gf.Quatd]) -> Gf.Quath:
    if isinstance(quat, Gf.Quath):
        return quat
    try:
        return Gf.Quath(quat)
    except Exception:
        imag = quat.GetImaginary()
        return Gf.Quath(quat.GetReal(), imag[0], imag[1], imag[2])


def make_orientation_quat(rotation_xyz_deg: np.ndarray) -> Gf.Quath:
    rot = Gf.Rotation(Gf.Vec3d(1, 0, 0), float(rotation_xyz_deg[0]))
    rot = rot * Gf.Rotation(Gf.Vec3d(0, 1, 0), float(rotation_xyz_deg[1]))
    rot = rot * Gf.Rotation(Gf.Vec3d(0, 0, 1), float(rotation_xyz_deg[2]))
    return to_quath(rot.GetQuat())


def sample_rotations(
    randomize_rotation: bool,
    piece_count: int,
    backend: "SpawnBackend",
    seed: Optional[int],
) -> list[Gf.Quath]:
    if not randomize_rotation:
        identity = Gf.Quath()
        return [identity for _ in range(piece_count)]
    seed_val = 0 if seed is None else int(seed) + 1337
    rotations = backend.sample_euler_degrees(piece_count, seed_val)
    return [make_orientation_quat(rot) for rot in rotations]


def quat_to_numpy(quat: Union[Gf.Quath, Gf.Quatf, Gf.Quatd]) -> np.ndarray:
    imag = quat.GetImaginary()
    return np.array([quat.GetReal(), imag[0], imag[1], imag[2]], dtype=np.float32)


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
        dtype=np.float32,
    )
