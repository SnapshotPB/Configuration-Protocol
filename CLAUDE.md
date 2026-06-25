# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Protocol Buffers (proto3) schema defining the app-to-board configuration protocol
for SnapshotPB paintball marker boards. Compiled both for client apps and, via
[nanopb](https://github.com/nanopb/nanopb) `.options` files, for the embedded
firmware. See [README.md](README.md) for the full structure and the open
board-type model.

Core schema lives in package `snapshotpb.v1` under `snapshotpb/v1/`; each board model has
its own versioned sub-package (e.g. `snapshotpb.autococker.v1`), and shared types live in
`snapshotpb.common.v1` (paths below are relative to `snapshotpb/`):

- `v1/protocol.proto` — top-level `Message` wrapper (`oneof payload`).
- `v1/device.proto` — `Device` board-owned state and the `BoardModel` enum.
- `v1/device_config.proto` — `DeviceConfig` (the app-writable device settings) and the `ProfileId` enum.
- `v1/profile.proto` — `Profile`, `Profiles`, and the `board_config` oneof that selects a board model.
- `autococker/v1/autococker.proto` — `AutocockerConfig`, one arm of `board_config`.
- `autococker/v1/fire_mode.proto` — `AutocockerFireMode`, autococker fire modes.
- `common/v1/eye_mode.proto` — `EyeMode`, a generic eye-sensing enum reusable by any board model.
- `*.options` — nanopb field constraints (`max_size`, `max_count`) for fixed-size C structs.

## Conventions

The schema is held to buf `STANDARD` lint and `FILE`-level breaking checks
(`buf.yaml`), run on PRs by `.github/workflows/proto.yml`. When editing:

- Core files declare `package snapshotpb.v1;`; each board model uses its own versioned
  sub-package (`package snapshotpb.<model>.v1;`) and shared types live in
  `snapshotpb.common.v1`. Imports always use the full path
  (`import "snapshotpb/<...>/<file>.proto";`), and cross-package types are referenced
  fully-qualified (e.g. `snapshotpb.autococker.v1.AutocockerConfig`).
- Every enum has a zero value suffixed `_UNSPECIFIED` and all values prefixed with the
  enum name (e.g. `FIRE_MODE_UNSPECIFIED = 0`).
- `.options` keys are fully qualified with the package (e.g. `snapshotpb.v1.DeviceConfig.boot_text`).
- New board models are added as new arms of the `board_config` oneof in `profile.proto`,
  each in its own versioned sub-package (`snapshotpb/<model>/v1/`, package
  `snapshotpb.<model>.v1`), using the next unused field number, plus a matching
  `BoardModel` value in `device.proto` (see the README's "adding a board type" example).
- Bounded `bytes`/`string`/`repeated` fields must have a matching nanopb constraint in
  the corresponding `*.options` file so the firmware gets fixed-size structs.
- **`v1` is pre-release and unstable.** Until the first tagged release, fields may be
  renumbered and messages reshaped freely to keep the schema clean; `buf breaking` is
  expected to fail on these and the failure is informational (merge anyway). Once `v1` is
  tagged, this reverses: never reuse a field number, `reserve` vacated tags and names, and
  make intentional breaking changes in a new version package (`snapshotpb.v2`) rather than
  mutating `v1`.

## Rules

- **Never co-author.** Do not add `Co-Authored-By` trailers, "Generated with Claude Code"
  footers, or any other attribution to commits, pull requests, or anywhere else. This is
  also enforced via `.claude/settings.json` (`attribution` set to empty / `includeCoAuthoredBy: false`).
