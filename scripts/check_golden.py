#!/usr/bin/env python3
"""Check or update protobuf golden files in testdata/.

Each golden file is a JSON object with the keys `message`, `proto`, and
`cases`. Each case holds a unique `name`, a protojson `fields` object, and
(outside `--update`) a lowercase even-length `hex` string.

Usage:
    python3 scripts/check_golden.py [--update] [--buf PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HEX_RE = re.compile(r"^[0-9a-f]*$")


def find_repo_root() -> Path:
    """Return the repository root from the path of this script."""
    return Path(__file__).resolve().parent.parent


def format_one_line_object(obj: dict) -> str:
    """Format a JSON object on one line with spaces inside the braces."""
    if not obj:
        return "{}"
    parts = [f"{json.dumps(k)}: {json.dumps(v)}" for k, v in obj.items()]
    return "{ " + ", ".join(parts) + " }"


def format_golden_json(data: dict) -> str:
    """Format golden file JSON with 2-space indent and one-line fields."""
    placeholders: dict[str, str] = {}
    copied = dict(data)
    formatted_cases = []
    for idx, case in enumerate(data["cases"]):
        token = f"__GOLDEN_FIELDS_PLACEHOLDER_{idx}__"
        placeholders[json.dumps(token)] = format_one_line_object(case["fields"])
        new_case = {
            "name": case["name"],
            "fields": token,
            "hex": case["hex"],
        }
        for key, value in case.items():
            if key not in new_case:
                new_case[key] = value
        formatted_cases.append(new_case)
    copied["cases"] = formatted_cases
    text = json.dumps(copied, indent=2) + "\n"
    for quoted_token, replacement in placeholders.items():
        text = text.replace(quoted_token, replacement, 1)
    return text


def validate_structure(
    data: object,
    rel_path: str,
    repo_root: Path,
    update: bool,
) -> list[str]:
    """Check the structure of one golden file and return error lines."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"ERROR {rel_path}: top-level JSON must be an object"]

    for key in ("message", "proto", "cases"):
        if key not in data:
            errors.append(f"ERROR {rel_path}: key `{key}` is absent")
    if errors:
        return errors

    message = data["message"]
    if not isinstance(message, str) or not message.strip():
        errors.append(f"ERROR {rel_path}: `message` must be a non-empty string")

    proto = data["proto"]
    if not isinstance(proto, str) or not proto.strip():
        errors.append(f"ERROR {rel_path}: `proto` must be a non-empty string")
    elif not (repo_root / proto).is_file():
        errors.append(f"ERROR {rel_path}: proto file does not exist: {proto}")

    cases = data["cases"]
    if not isinstance(cases, list):
        errors.append(f"ERROR {rel_path}: `cases` must be a list")
        return errors

    seen_names: set[str] = set()
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"ERROR {rel_path}: case {idx} must be an object")
            continue

        name = case.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(
                f"ERROR {rel_path}: case {idx} must have a non-empty `name`"
            )
            case_label = f"#{idx}"
        else:
            case_label = name
            if name in seen_names:
                errors.append(f"ERROR {rel_path}: duplicate case name `{name}`")
            seen_names.add(name)

        fields = case.get("fields")
        if not isinstance(fields, dict):
            errors.append(
                f"ERROR {rel_path} [{case_label}]: `fields` must be an object"
            )

        if not update:
            hex_val = case.get("hex")
            if not isinstance(hex_val, str):
                errors.append(
                    f"ERROR {rel_path} [{case_label}]: `hex` must be a string"
                )
            elif len(hex_val) % 2 != 0 or HEX_RE.fullmatch(hex_val) is None:
                errors.append(
                    f"ERROR {rel_path} [{case_label}]: `hex` must hold even-length lowercase hex digits"
                )

    return errors


def encode_case(
    buf_path: str,
    repo_root: Path,
    message: str,
    fields: dict,
) -> tuple[str | None, str | None]:
    """Encode one protojson fields object with buf convert."""
    payload = json.dumps(fields).encode("utf-8")
    cmd = [
        buf_path,
        "convert",
        ".",
        "--type",
        message,
        "--from",
        "-#format=json",
        "--to",
        "-#format=binpb",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=payload,
            cwd=repo_root,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except FileNotFoundError:
        return None, f"buf command not found: {buf_path}"
    except subprocess.TimeoutExpired:
        return None, "buf convert reached the 60-second time limit"
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        return None, f"buf convert failed (exit {proc.returncode}): {err}"
    return proc.stdout.hex(), None


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Check or update protobuf golden files in testdata/."
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Encode each case and write the hex values to the golden files.",
    )
    parser.add_argument(
        "--buf",
        default="buf",
        metavar="PATH",
        help="Path to the buf executable (default: buf).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Run the golden file check or update."""
    args = parse_args(argv)
    repo_root = find_repo_root()
    testdata_dir = repo_root / "testdata"
    golden_files = sorted(testdata_dir.glob("*.json"))

    if not golden_files:
        print("ERROR: no golden files exist in testdata/", file=sys.stderr)
        return 1

    total_files = 0
    total_cases = 0
    failures = 0

    for path in golden_files:
        total_files += 1
        rel_path = path.relative_to(repo_root).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR {rel_path}: {exc}", file=sys.stderr)
            failures += 1
            continue

        struct_errors = validate_structure(data, rel_path, repo_root, args.update)
        if struct_errors:
            for err in struct_errors:
                print(err, file=sys.stderr)
            failures += len(struct_errors)
            continue

        message = data["message"]
        file_failed = False

        for case in data["cases"]:
            total_cases += 1
            name = case["name"]
            actual_hex, err = encode_case(args.buf, repo_root, message, case["fields"])
            if err is not None:
                print(f"ERROR {rel_path} [{name}]: {err}", file=sys.stderr)
                failures += 1
                file_failed = True
                continue

            if args.update:
                case["hex"] = actual_hex
            else:
                expected_hex = case["hex"]
                if actual_hex != expected_hex:
                    print(
                        f"FAIL {rel_path} [{name}]: expected {expected_hex}, actual {actual_hex}",
                        file=sys.stderr,
                    )
                    failures += 1

        if args.update and not file_failed:
            path.write_text(format_golden_json(data), encoding="utf-8")

    file_word = "file" if total_files == 1 else "files"
    case_word = "case" if total_cases == 1 else "cases"

    if failures > 0:
        print(
            f"Checked {total_files} {file_word} and {total_cases} {case_word}: {failures} failed."
        )
        return 1

    if args.update:
        print(f"Updated {total_files} {file_word} and {total_cases} {case_word}.")
    else:
        print(f"Checked {total_files} {file_word} and {total_cases} {case_word}: all passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
