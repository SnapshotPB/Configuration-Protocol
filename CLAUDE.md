# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Protocol Buffers (proto3) schema defining the app-to-board configuration protocol
for SnapshotPB paintball marker boards. Compiled both for client apps and, via
[nanopb](https://github.com/nanopb/nanopb) `.options` files, for the embedded
firmware. See [README.md](README.md) for the full structure and the open
board-type model.

All schema lives in package `snapshotpb.v1` under `snapshotpb/v1/`:

- `protocol.proto` — top-level `Message` wrapper (`oneof payload`).
- `device.proto` — `Device` board state and the `ProfileId` enum.
- `profile.proto` — `Profile`, `Profiles`, and the `board_config` oneof that selects a board model.
- `autococker.proto` — `AutocockerConfig`, one arm of `board_config`.
- `*.options` — nanopb field constraints (`max_size`, `max_count`) for fixed-size C structs.

## Conventions

The schema is held to buf `STANDARD` lint and `FILE`-level breaking checks
(`buf.yaml`), run on PRs by `.github/workflows/proto.yml`. When editing:

- Every file declares `package snapshotpb.v1;` and imports by full path
  (`import "snapshotpb/v1/<file>.proto";`).
- Every enum has a zero value suffixed `_UNSPECIFIED` and all values prefixed with the
  enum name (e.g. `FIRE_MODE_UNSPECIFIED = 0`).
- `.options` keys are fully qualified with the package (e.g. `snapshotpb.v1.Device.boot_text`).
- New board models are added as new arms of the `board_config` oneof in `profile.proto`,
  each in its own `*.proto`, using the next unused field number. Never reuse a field
  number; reserve vacated tags and names.
- Bounded `bytes`/`string`/`repeated` fields must have a matching nanopb constraint in
  the corresponding `*.options` file so the firmware gets fixed-size structs.
- Intentional breaking changes go in a new version package (`snapshotpb.v2`), not by
  mutating `v1` — `buf breaking` will otherwise fail the build.

## Rules

- **Never co-author.** Do not add `Co-Authored-By` trailers, "Generated with Claude Code"
  footers, or any other attribution to commits, pull requests, or anywhere else. This is
  also enforced via `.claude/settings.json` (`attribution` set to empty / `includeCoAuthoredBy: false`).
