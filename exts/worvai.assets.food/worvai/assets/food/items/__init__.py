"""Concrete food items and containers."""

from .containers import FoodBucket
from .definitions import (
    CONTAINERS,
    EDIBLES,
    BaseItemDefinition,
    ContainerDefinition,
    EdibleDefinition,
    POPCORN_CONTAINER,
    POPCORN_CONTAINER_USD,
    POPCORN_EDIBLE,
    POPCORN_PIECE_USD,
    TACO_EDIBLE,
    TACO_PIECE_USD,
)

__all__ = [
    "FoodBucket",
    "CONTAINERS",
    "EDIBLES",
    "BaseItemDefinition",
    "ContainerDefinition",
    "EdibleDefinition",
    "POPCORN_CONTAINER",
    "POPCORN_CONTAINER_USD",
    "POPCORN_EDIBLE",
    "POPCORN_PIECE_USD",
    "PopcornAsset",
    "PopcornBucket",
    "PopcornBucketManager",
    "TACO_EDIBLE",
    "TACO_PIECE_USD",
    "spawn_popcorn_bucket",
]


def __getattr__(name: str):
    if name in {
        "PopcornAsset",
        "PopcornBucket",
        "PopcornBucketManager",
        "spawn_popcorn_bucket",
    }:
        from .edibles import (
            PopcornAsset,
            PopcornBucket,
            PopcornBucketManager,
            spawn_popcorn_bucket,
        )

        return {
            "PopcornAsset": PopcornAsset,
            "PopcornBucket": PopcornBucket,
            "PopcornBucketManager": PopcornBucketManager,
            "spawn_popcorn_bucket": spawn_popcorn_bucket,
        }[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
