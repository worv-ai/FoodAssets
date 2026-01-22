# Changelog

## [0.1.0] - 2026-01-22
### Added
- Added asset path overrides (`container_usd_path`, `piece_usd_path`) for external assets.
- Added `items/piece_spawners` for point instancing and rigid body spawning.
- Added omni.kit.test coverage for CPU/GPU CCD and collision warning scenarios.
- Added extension metadata and test configuration in `extension.toml`.
- Added `actions_api.md` generation for extension actions.
### Changed
- Moved spawner logic out of `utils` to keep helpers thin.
- Updated docs to reference new spawner locations and asset overrides.
### Fixed
- Applied collision APIs only on mesh colliders to avoid dynamic mesh warnings.
- Normalized CCD behavior when GPU dynamics is enabled.
- Fixed piece orientation authoring to use `GfQuatf` types.

## [0.0.3] - 2026-01-22
### Added
- Added physics piece tracking support in managers.
- Added expanded bucket spawn parameters and popcorn options.
- Added UI controls and validation for physics parameters.
### Changed
- Refined spawn utilities and physics instancer workflow.
- Refreshed demo logging and docs.
### Fixed
- Improved collision handling for physics pieces.

## [0.0.2] - 2026-01-22
### Added
- Added USD asset path helpers and existence checks.

## [0.0.1] - 2025-12-30
### Added
- Initial release of the Food Assets extension, including definitions for various food items placeholder assets.
- Added popcorn edible definition with `popcorn-piece.usdc` asset.
- Added popcorn bucket container definition with `popcorn-bucket.usdc` asset.

# [template] - YYYY-MM-DD
### Added
-
### Changed
-
### Fixed
-
