"""
Spawn backends for food assets.

This module provides backend implementations for sampling piece positions and
orientations during spawning. Two backends are available:
- NumpyBackend: CPU-based sampling using NumPy (default)
- WarpBackend: GPU-accelerated sampling using NVIDIA Warp
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional, Union

import numpy as np

_logger = logging.getLogger(__name__)

try:
    import warp as wp
except Exception:
    wp = None


class SpawnBackend(ABC):
    """
    Abstract base class for spawn backends.

    Subclasses must implement the sampling methods for positions and rotations.
    """

    name: str = "base"

    @abstractmethod
    def sample_positions(
        self, min_xyz: np.ndarray, max_xyz: np.ndarray, count: int, seed: Optional[int]
    ) -> np.ndarray:
        """
        Sample random positions within a bounding box.

        Args:
            min_xyz: Minimum corner of the bounding box (3,).
            max_xyz: Maximum corner of the bounding box (3,).
            count: Number of positions to sample.
            seed: Random seed for reproducibility.

        Returns:
            Array of sampled positions with shape (count, 3).
        """

    @abstractmethod
    def sample_euler_degrees(self, count: int, seed: Optional[int]) -> np.ndarray:
        """
        Sample random Euler angles in degrees.

        Args:
            count: Number of orientations to sample.
            seed: Random seed for reproducibility.

        Returns:
            Array of Euler angles with shape (count, 3), each in [0, 360).
        """


class NumpyBackend(SpawnBackend):
    """CPU-based spawn backend using NumPy."""

    name: str = "numpy"

    def sample_positions(
        self, min_xyz: np.ndarray, max_xyz: np.ndarray, count: int, seed: Optional[int]
    ) -> np.ndarray:
        """Sample random positions using NumPy RNG."""
        rng = np.random.default_rng(seed)
        return rng.uniform(min_xyz, max_xyz, size=(count, 3))

    def sample_euler_degrees(self, count: int, seed: Optional[int]) -> np.ndarray:
        """Sample random Euler angles using NumPy RNG."""
        rng = np.random.default_rng(seed)
        return rng.uniform(0.0, 360.0, size=(count, 3))


class WarpBackend(SpawnBackend):
    """GPU-accelerated spawn backend using NVIDIA Warp."""

    name: str = "warp"

    def __init__(self, device: Optional[str] = None) -> None:
        """
        Initialize the Warp backend.

        Args:
            device: Compute device ("cuda" or "cpu"). Defaults to CUDA if available.

        Raises:
            RuntimeError: If Warp is not installed or unavailable.
        """
        if wp is None:
            raise RuntimeError("Warp is not available. Install with: pip install warp-lang")
        wp.init()
        if device is None:
            device = "cuda" if wp.is_cuda_available() else "cpu"
        self._device = device
        _logger.debug("WarpBackend initialized with device: %s", device)

    def sample_positions(
        self, min_xyz: np.ndarray, max_xyz: np.ndarray, count: int, seed: Optional[int]
    ) -> np.ndarray:
        """Sample random positions using Warp kernels."""
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
        """Sample random Euler angles using Warp kernels."""
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
    """
    Get or create a spawn backend instance.

    Args:
        backend: Backend specification. Can be:
            - A SpawnBackend instance (returned as-is)
            - "numpy" or None (creates NumpyBackend)
            - "warp" (creates WarpBackend)

    Returns:
        A SpawnBackend instance.

    Raises:
        ValueError: If backend string is not recognized.
    """
    if isinstance(backend, SpawnBackend):
        return backend
    if backend is None or backend == "numpy":
        return NumpyBackend()
    if backend == "warp":
        return WarpBackend()
    raise ValueError(f"Unknown backend: {backend!r}. Use 'numpy' or 'warp'.")


# -----------------------------------------------------------------------------
# Warp GPU kernels (only defined if warp is available)
# -----------------------------------------------------------------------------

if wp is not None:

    @wp.kernel
    def _WARP_SAMPLE_POSITIONS(
        min_v: wp.vec3,
        max_v: wp.vec3,
        seed: int,
        out: wp.array(dtype=wp.vec3),
    ) -> None:
        """Sample random 3D positions within bounds (GPU kernel)."""
        tid = wp.tid()
        state = wp.rand_init(seed, tid)
        out[tid] = wp.vec3(
            wp.randf(state, min_v.x, max_v.x),
            wp.randf(state, min_v.y, max_v.y),
            wp.randf(state, min_v.z, max_v.z),
        )

    @wp.kernel
    def _WARP_SAMPLE_EULER(
        seed: int,
        out: wp.array(dtype=wp.vec3),
    ) -> None:
        """Sample random Euler angles in degrees (GPU kernel)."""
        tid = wp.tid()
        state = wp.rand_init(seed, tid)
        out[tid] = wp.vec3(
            wp.randf(state, 0.0, 360.0),
            wp.randf(state, 0.0, 360.0),
            wp.randf(state, 0.0, 360.0),
        )
