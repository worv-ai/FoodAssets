"""Spawn backends for food assets."""

from __future__ import annotations

from typing import Optional, Union

import numpy as np

try:
    import warp as wp
except Exception:
    wp = None


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
