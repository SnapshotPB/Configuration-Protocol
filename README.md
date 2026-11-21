# Configuration-Protocol

Protocol for app-to-board communication for SnapshotPB paintball marker boards.

The schema is defined in [Protocol Buffers](https://protobuf.dev/) (proto3) and
ships with [nanopb](https://github.com/nanopb/nanopb) `.options` files so the same
definitions can be compiled for the embedded firmware as well as client apps. It
describes how an app reads and writes a board's device state and user profiles.

## Project structure

Core schema lives in package `snapshotpb.v1` under `snapshotpb/v1/` (file paths below are
relative to `snapshotpb/`). Each board model lives in its own versioned sub-package
(e.g. `snapshotpb.autococker.v1` under `snapshotpb/autococker/v1/`), and types shared
across models live in `snapshotpb.common.v1`. **`v1` is pre-release:** until the first
tagged release it may be renumbered and reshaped freely to keep the schema clean. Once
released, incompatible revisions land in a new version package (e.g. `v2`) instead,
leaving existing consumers untouched.

| File | Purpose |
| --- | --- |
| `v1/protocol.proto` | Documentation only. Held the top-level `Message` wrapper, which nothing ever put on the wire: the transport names the object it carries, so payloads are exchanged bare. The file records why, and why not to reintroduce one. |
| `v1/device.proto` | `Device` — board-owned, read-only board state (device id, lockout, board model, supported profile count) and the `BoardModel` enum. |
| `v1/device_config.proto` | `DeviceConfig` — the app-writable device settings (active profile, boot text, display window, menu language, screen brightness, screen-off delay, battery type, bolt mode, Bluetooth at boot) and the `ScreenBrightness`, `BatteryType`, `BoltMode`, and `BluetoothAtBoot` enums. |
| `v1/language.proto` | `Language` — the language of the board's OWN menu text, named by ISO 639-1 code (`LANGUAGE_EN`, `LANGUAGE_ES`, `LANGUAGE_DE`, `LANGUAGE_FR`). It does not constrain user text; the font pack does. |
| `v1/eye_status.proto` | `EyeStatus` — the live level and state of the breach eye, and the `EyeSensorState` enum. |
| `v1/profile.proto` | `Profile` — a user configuration for the marker, plus the `Profiles` collection. Holds the `board_config` oneof (see below). Tags 2 and 5 are reserved: `type` (the deleted `ProfileType`) described the client UI only, and `screen_brightness` moved to `DeviceConfig`. |
| `autococker/v1/autococker.proto` | `AutocockerConfig` — autococker-specific firing mechanics (fire mode, eye sensing, solenoid timing, ramping, trigger debounce). One arm of `board_config`. Package `snapshotpb.autococker.v1`. |
| `autococker/v1/fire_mode.proto` | `AutocockerFireMode` — autococker fire-mode enum (mechanical, semi, trigger-only, full-auto, NXL 2026 ramping, custom ramping). The NXL 2026 mode has no adjustable rule: `fire_rate_cap` and the `ramping_custom_*` fields do not apply in it. The `ramping_custom_*` fields apply in the custom ramping mode only. |
| `common/v1/eye_mode.proto` | `EyeMode` — generic eye-sensing enum (off, reflective, break-beam) in the shared `snapshotpb.common.v1` package, reusable by any board model. |
| `*.options` | nanopb field constraints (`max_size`, `max_count`) used to generate fixed-size C structs for the firmware. Keys are fully qualified, e.g. `snapshotpb.v1.DeviceConfig.boot_text`. |

### Message model

Each exchange carries one bare message with no envelope. For the OTS objects (`Device`,
`DeviceConfig`, and `Profiles`), the client selects each object by name over OLCP
(`device`, `profiles`, `config`). The transport names the payload type before the bytes
arrive.

`EyeStatus` is not an OTS object. The board sends `EyeStatus` as the value of a vendor
GATT characteristic. The characteristic UUID names the payload, and the value is a bare
`EyeStatus` message with no envelope.

```
Device          // board-owned, read-only (device_id, lockout, model, profile count)

DeviceConfig    // app-configurable settings (active_profile, boot_text, display_window,
                //                            language, screen_brightness, screen_off_delay,
                //                            battery_type, bolt_mode, bluetooth_at_boot)

Profiles        // repeated Profile (max 4)
└── Profile
    ├── generic fields (name, fire_rate_cap, board_auto_off)
    └── oneof board_config
        └── AutocockerConfig   // board-model-specific firing config

EyeStatus       // live status of the breach eye (GATT characteristic, not an OTS object)
```

`Device` carries board-owned state the app can only read (`device_id`,
`lockout_enabled`, `model`, `supported_profile_count`). `DeviceConfig` holds the
app-configurable settings (`active_profile`, `boot_text`, `display_window`, `language`,
`screen_brightness`, `screen_off_delay`, `battery_type`, `bolt_mode`, `bluetooth_at_boot`) and is the only device message a client writes; the
read-only fields don't exist on it, so they can't be altered.

The two screen fields belong to the **board**, not to a profile. One screen serves all four
profile slots, so a per-profile brightness asked the board to hold four answers for one piece
of glass and changed the brightness under the user at every profile switch. `screen_brightness`
therefore moved off `Profile` tag 5, which is now reserved.

## Live eye status (GATT)

| Item | Value |
| --- | --- |
| Service UUID | `00000010-5350-4221-0000-5350425f4f54` |
| Characteristic UUID | `00000011-5350-4221-0000-5350425f4f54` |
| Properties | read, notify |
| Value | a bare `snapshotpb.v1.EyeStatus` |

- A read gives the current `EyeStatus`.
- While a client has notifications on (the CCC is set), the board sends `EyeStatus` at approximately 10 Hz. The board sends no notification when no client has notifications on.
- The board sets the CCC of this characteristic back to 0 at each disconnect, also for a bonded client. A client turns notifications on again after each connect.
- A client turns notifications on only while it shows the value, because the notifications use power and radio time.
- The board does not turn on the emitter for a client. The state tells the client why there is no level.
- A board with older firmware does not have this service. In that case, a client shows no level, and all other functions work.
- These UUIDs use the same vendor base as the OTS vendor UUIDs `00000001-…` (device object type) and `00000002-…` (object data).

## Open approach to board types

A `Profile` separates **generic** marker settings from **board-model-specific**
firing configuration. The generic fields live directly on `Profile`; everything
specific to a particular board model lives in its own message, selected through the
`board_config` oneof:

```proto
// profile.proto
message Profile {
    string name = 1;
    uint32 fire_rate_cap = 3;  // tenths of a ball per second; 0 = uncapped
    uint32 board_auto_off = 4;

    reserved 2;  // was ProfileType type; it described the client UI, not the board
    reserved 5;  // was screen_brightness; the screen is a DeviceConfig setting

    // Board-model-specific firing configuration. The set arm identifies the board model.
    oneof board_config {
        snapshotpb.autococker.v1.AutocockerConfig autococker = 6;
    }
}
```

Because the board model is encoded as the *set arm* of the oneof, the protocol is
open to new board types without disturbing existing ones:

- Each board model lives in its own versioned sub-package and directory
  (`snapshotpb/<model>/v1/`, package `snapshotpb.<model>.v1`), so models version
  independently and never collide on field numbers.
- Generic settings stay in one place and are reused by every board model.
- Cross-cutting types reusable across board models (e.g. `EyeMode`) live in the shared
  `snapshotpb.common.v1` package, so any model can import them without creating a
  package import cycle.
- A client/firmware switches on which arm is set to know how to interpret the
  configuration; an unset oneof means no board-specific config is present.
- A board advertises which model it is via `Device.model` (`BoardModel` in
  `device.proto`). Each `BoardModel` value pairs one-to-one with a `board_config` arm,
  so a board's type is known without inspecting a profile, and every profile on that
  board is expected to use the matching arm.
- Field numbers are append-only — new arms take the next unused number and old ones
  are never reused (vacated tags are `reserved`).

### Example: adding a board type

Suppose we want to support a spool-valve marker. Add a new board model in four steps.

**1. Define the board's config message in its own versioned sub-package** —
`snapshotpb/spool/v1/spool.proto`:

```proto
syntax = "proto3";

package snapshotpb.spool.v1;

// Spool-valve-specific firing mechanics. Selected as a board model arm of the
// `board_config` oneof in Profile (snapshotpb.v1).
message SpoolConfig {
    // The amount of time in tenths of a millisecond the solenoid stays energized per shot.
    uint32 dwell = 1;

    // The amount of time in tenths of a millisecond the trigger must be pulled to fire.
    uint32 trigger_debounce_on = 2;
}
```

**2. Import it and add a new arm to the `board_config` oneof** in `profile.proto`,
using the next unused field number (`autococker` is `6`, so `spool` is `7`). Cross-package
types are referenced fully-qualified:

```proto
import "snapshotpb/autococker/v1/autococker.proto";
import "snapshotpb/spool/v1/spool.proto";

// ...
    oneof board_config {
        snapshotpb.autococker.v1.AutocockerConfig autococker = 6;
        snapshotpb.spool.v1.SpoolConfig spool = 7;
    }
```

**3. Add the matching `BoardModel` value** in `device.proto`, so a board can declare it
is this model. Keep it paired one-to-one with the new `board_config` arm:

```proto
// device.proto
enum BoardModel {
  BOARD_MODEL_UNSPECIFIED = 0;
  BOARD_MODEL_AUTOCOCKER = 1;
  BOARD_MODEL_SPOOL = 2;
}
```

**4. (Optional) add nanopb constraints** for any bounded `bytes`, `string`, or
`repeated` fields in a matching `snapshotpb/spool/v1/spool.options` file, with fully
qualified keys, e.g.:

```
snapshotpb.spool.v1.SpoolConfig.some_label max_size:10
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

## Golden files

The C firmware, the Rust firmware, and the client apps test their encode and decode against the golden files in `testdata/`. A real protobuf encoder (`buf convert`) creates the bytes, and all implementations agree on the wire format. `testdata/eye_status.json` holds the test cases of `EyeStatus`.

Each golden file is a JSON object with the keys `message`, `proto`, and `cases`. `message` names the protobuf message, `proto` gives the path to the `.proto` file, and `cases` holds the test cases. Each case has three keys:

- `name`: a unique non-empty case name.
- `fields`: the protojson form of the message, with `snake_case` proto field names and each enum value by its name. An absent key is a field that is not set.
- `hex`: the encoded bytes in lowercase hex, with no spaces and no `0x` prefix.

To add a case, add a new entry with `name` and `fields` to the file. Run `python3 scripts/check_golden.py --update` to write the `hex` value. Examine the new `hex` value to confirm that it matches the expected wire format.

A client test must check both directions. It must decode `hex` and compare the result with `fields`. It must also encode `fields` and compare the bytes with `hex`.

## Validation / CI

Pull requests that touch protos are validated by the [`Proto`](.github/workflows/proto.yml)
GitHub Action, which runs:

- `buf build` — confirms the protos compile and imports resolve.
- `buf lint` — enforces the `STANDARD` ruleset above.
- `python3 scripts/check_golden.py` — checks each golden file in `testdata/` against `buf convert`.
- `buf breaking` — compares against the PR's base branch and **fails the build on any
  source-breaking change** (field renames, type changes, deletions, renumbering).

To run the same checks locally:

```sh
buf build
buf lint
python3 scripts/check_golden.py
buf breaking --against '.git#branch=main'
```

While `v1` is pre-release, breaking changes are made directly in `v1` and the `buf breaking`
step is expected to fail — it is informational until the first tagged release. After `v1`
is tagged, intentional breaking changes go in a new version package (e.g. `snapshotpb.v2`)
rather than mutating `v1`.

## License

Configuration Protocol © 2026 Snapshot PB is licensed under the
[Mozilla Public License, Version 2.0](https://mozilla.org/MPL/2.0/)
(`MPL-2.0`). See [`LICENSE`](LICENSE).
