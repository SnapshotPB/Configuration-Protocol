# Configuration-Protocol

Protocol for app-to-board communication for SnapshotPB paintball marker boards.

The schema is defined in [Protocol Buffers](https://protobuf.dev/) (proto3) and
ships with [nanopb](https://github.com/nanopb/nanopb) `.options` files so the same
definitions can be compiled for the embedded firmware as well as client apps. It
describes how an app reads and writes a board's device state and user profiles.

## Project structure

All schema lives in package `snapshotpb.v1` under `snapshotpb/v1/`. The versioned
package (`v1`) means future incompatible revisions land in a new package (`v2`) without
breaking existing consumers.

| File | Purpose |
| --- | --- |
| `protocol.proto` | Top-level `Message` wrapper. A `oneof payload` carries exactly one of the protocol's payloads (`Device` or `Profiles`). |
| `device.proto` | `Device` — per-board state (device id, active profile, lockout, boot text) and the `ProfileId` slot enum. |
| `profile.proto` | `Profile` — a user configuration for the marker, plus the `Profiles` collection, `ProfileType`, and `ScreenBrightness`. Holds the `board_config` oneof (see below). |
| `autococker.proto` | `AutocockerConfig` — autococker-specific firing mechanics (fire mode, eye sensing, solenoid timing, ramping, trigger debounce). One arm of `board_config`. |
| `*.options` | nanopb field constraints (`max_size`, `max_count`) used to generate fixed-size C structs for the firmware. Keys are fully qualified, e.g. `snapshotpb.v1.Device.boot_text`. |

### Message model

```
Message
└── oneof payload
    ├── Device     // board state
    └── Profiles   // repeated Profile (max 4)
                   └── Profile
                       ├── generic fields (name, type, fire_rate_cap, board_auto_off, screen_brightness)
                       └── oneof board_config
                           └── AutocockerConfig   // board-model-specific firing config
```

## Open approach to board types

A `Profile` separates **generic** marker settings from **board-model-specific**
firing configuration. The generic fields live directly on `Profile`; everything
specific to a particular board model lives in its own message, selected through the
`board_config` oneof:

```proto
// profile.proto
message Profile {
    string name = 1;
    ProfileType type = 2;
    uint32 fire_rate_cap = 4;
    uint32 board_auto_off = 17;
    ScreenBrightness screen_brightness = 18;

    // Board-model-specific firing configuration. The set arm identifies the board model.
    oneof board_config {
        AutocockerConfig autococker = 19;
    }
}
```

Because the board model is encoded as the *set arm* of the oneof, the protocol is
open to new board types without disturbing existing ones:

- Each board model owns its own `*.proto` config message, so unrelated models never
  share or collide on field numbers.
- Generic settings stay in one place and are reused by every board model.
- A client/firmware switches on which arm is set to know how to interpret the
  configuration; an unset oneof means no board-specific config is present.
- Field numbers are append-only — new arms take the next unused number and old ones
  are never reused (vacated tags are `reserved`).

### Example: adding a board type

Suppose we want to support a spool-valve marker. Add a new board model in three steps.

**1. Define the board's config message in its own file** — `snapshotpb/v1/spool.proto`:

```proto
syntax = "proto3";

package snapshotpb.v1;

// Spool-valve-specific firing mechanics. Selected as a board model arm of the
// `board_config` oneof in Profile.
message SpoolConfig {
    // The amount of time in tenths of a millisecond the solenoid stays energized per shot.
    uint32 dwell = 1;

    // The amount of time in tenths of a millisecond the trigger must be pulled to fire.
    uint32 trigger_debounce_on = 2;
}
```

**2. Import it and add a new arm to the `board_config` oneof** in `profile.proto`,
using the next unused field number (`autococker` is `19`, so `spool` is `20`):

```proto
import "snapshotpb/v1/autococker.proto";
import "snapshotpb/v1/spool.proto";

// ...
    oneof board_config {
        AutocockerConfig autococker = 19;
        SpoolConfig spool = 20;
    }
```

**3. (Optional) add nanopb constraints** for any bounded `bytes`, `string`, or
`repeated` fields in a matching `snapshotpb/v1/spool.options` file, with fully
qualified keys, e.g.:

```
snapshotpb.v1.SpoolConfig.some_label max_size:10
```

That's it — existing `autococker` profiles are unaffected, and clients that don't
recognize `spool` simply see an unset `board_config`.

## Conventions

The schema follows [buf](https://buf.build) `STANDARD` lint rules. When editing:

- Every file declares `package snapshotpb.v1;` and imports by full path
  (`import "snapshotpb/v1/<file>.proto";`).
- Every enum has a zero value suffixed `_UNSPECIFIED` and all values prefixed with the
  enum name, e.g. `FIRE_MODE_UNSPECIFIED = 0; FIRE_MODE_MECHANICAL = 1;`.
- `.options` keys are fully qualified with the package.

## Validation / CI

Pull requests that touch protos are validated by the [`Proto`](.github/workflows/proto.yml)
GitHub Action, which runs:

- `buf build` — confirms the protos compile and imports resolve.
- `buf lint` — enforces the `STANDARD` ruleset above.
- `buf breaking` — compares against the PR's base branch and **fails the build on any
  source-breaking change** (field renames, type changes, deletions, renumbering).

To run the same checks locally:

```sh
buf build
buf lint
buf breaking --against '.git#branch=main'
```

Intentional breaking changes should be made in a new version package (e.g. `snapshotpb.v2`)
rather than mutating `v1`.

## License

Configuration Protocol © 2026 Snapshot PB is licensed under the
[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html)
(`GPL-3.0-only`). See [`LICENSE`](LICENSE).
