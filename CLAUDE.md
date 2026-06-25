# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Protocol Buffers (proto3) schema defining the app-to-board configuration protocol
for SnapshotPB paintball marker boards. Compiled both for client apps and, via
[nanopb](https://github.com/nanopb/nanopb) `.options` files, for the embedded
firmware. See [README.md](README.md) for the full structure and the open
board-type model.

All schema lives under `snapshotpb/`:

- `protocol.proto` — top-level `Message` wrapper (`oneof payload`).
- `device.proto` — `Device` board state and the `ProfileId` enum.
- `profile.proto` — `Profile`, `Profiles`, and the `board_config` oneof that selects a board model.
- `autococker.proto` — `AutocockerConfig`, one arm of `board_config`.
- `*.options` — nanopb field constraints (`max_size`, `max_count`) for fixed-size C structs.

## Conventions

- New board models are added as new arms of the `board_config` oneof in `profile.proto`,
  each in its own `*.proto`, using the next unused field number. Never reuse a field
  number; reserve vacated tags and names.
- Bounded `bytes`/`string`/`repeated` fields must have a matching nanopb constraint in
  the corresponding `*.options` file so the firmware gets fixed-size structs.

## Rules

- **Never co-author.** Do not add `Co-Authored-By` trailers, "Generated with Claude Code"
  footers, or any other attribution to commits, pull requests, or anywhere else. This is
  also enforced via `.claude/settings.json` (`attribution` set to empty / `includeCoAuthoredBy: false`).
