"""
Walkthrough of every function in the ediFabric Native X12 C ABI.

Each section calls one group of entry points and prints the result, so the
output doubles as a reference for what each call returns.

Usage:
    python example_all_functions.py
    python example_all_functions.py --serial YOUR_SERIAL
    python example_all_functions.py --lib /path/to/edifabric-x12-tools.dll
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import edifabric_x12 as ef

# Free plan serial published in the ediFabric Native documentation.
DEFAULT_SERIAL = "bd96a836feca45cb91c86ee65d281f52"

ROOT = Path(__file__).resolve().parent
MAP_PATH = ROOT / "map" / "map.json"
SAMPLE_EDI_PATH = ROOT / "edi" / "837p.txt"
SAMPLE_EDI_INVALID_PATH = ROOT / "edi" / "837p_error.txt"

SAMPLE_EDI = SAMPLE_EDI_PATH.read_text(encoding="utf-8")
SAMPLE_EDI_INVALID = SAMPLE_EDI_INVALID_PATH.read_text(encoding="utf-8")

# Validation levels are 0 - no validation; 1 - syntax only; 2 - limits and codes; 3 - balancing; 4 - inter segment. The levels macth the HIPAA SNIP validation levels.
PARSE_CONFIG = {
    "validate": {
        "regex": None,
        "date_format": None,
        "time_format": None,
        "skip_seq_count": False,
        "skip_hl_seq": False,
        "snip_level": 4,
        "max_errors": 100,
    },
    "ack": {
        "supress_ta1": False,
        "ak901p": False,
        "gen_for_valid": True,
        "gen997": False,
    },
}

SPLIT_CONFIG = dict(PARSE_CONFIG, split={"segment_id": "LX", "segment_depth": 6, "loop_id": "2400"})

# .NET DateTime ticks are 100ns intervals since year 1.
TICKS_PER_SECOND = 10_000_000
DOTNET_EPOCH = datetime(1, 1, 1, tzinfo=timezone.utc)


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def preview(text: str, limit: int = 400) -> str:
    return text if len(text) <= limit else text[:limit] + " ..."


def ticks_to_utc(ticks: int) -> str:
    if not ticks:
        return "no token set"
    return (DOTNET_EPOCH + timedelta(seconds=ticks / TICKS_PER_SECOND)).isoformat()


def load_local_map() -> dict:
    """Load MAP/Map.json and point each entry at the local MAP folder."""
    model_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    map_dir = str(MAP_PATH.parent.resolve())
    for entry in model_map.get("maps", {}).values():
        entry["location"] = map_dir
    return model_map

def load_online_map() -> dict:
    """Load MAP/Map.json and point each entry at the local MAP folder."""
    model_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    model_map["default"] = DEFAULT_SERIAL
    
    return model_map


def demo_errors() -> None:
    """get_error, free_error"""
    section("Error messages: get_error, free_error")

    for code in (ef.ErrorCode.INSUFFICIENT_CAPACITY, ef.ErrorCode.MAP_NOT_SET, ef.ErrorCode.LICENSE_NOT_SET):
        print(f"  get_error({int(code):>3}) -> {ef.get_error(code)}")

    # The raw export hands back a heap pointer that the caller owns.
    lib = ef.load_library()
    pointer = lib.get_error(int(ef.ErrorCode.TOKEN_EXPIRED))
    message = ctypes.cast(pointer, ctypes.c_char_p).value.decode("utf-8")
    ef.free_error(pointer)
    print(f"  raw get_error(631) -> {message}")
    print("  free_error(pointer) released the string")


def demo_logging(log_path: Path) -> None:
    """init_logger, get_app_version"""
    section("Lifecycle: init_logger, get_app_version")

    ef.init_logger(str(log_path), ef.LogLevel.TRACE)
    print(f"  init_logger -> logging to {log_path}")
    print(f"  get_app_version -> {ef.get_app_version()}")


def demo_set_online_map() -> None:
    """set_map"""
    section("Model map: set_map online, default is the serial key")

    model_map = load_online_map()
    ef.set_map(json.dumps(model_map))
    keys = ", ".join(model_map.get("maps", {})) or "(none)"
    print(f"  set_map <- {MAP_PATH.relative_to(ROOT)}")
    print(f"  default={model_map.get('default')!r}, local maps={keys}")
    
def demo_set_local_map() -> None:
    """set_map"""
    section("Model map: set_map local, default is blank")

    model_map = load_local_map()
    ef.set_map(json.dumps(model_map))
    keys = ", ".join(model_map.get("maps", {})) or "(none)"
    print(f"  set_map <- {MAP_PATH.relative_to(ROOT)}")
    print(f"  default={model_map.get('default')!r}, local maps={keys}")


def demo_parse() -> str:
    """parse in mode 1"""
    section("Parse: parse (mode 1, JSON only)")

    output, offset = ef.parse(SAMPLE_EDI, ef.ParseMode.JSON)
    print(f"  {len(output)} bytes of JSON, offset={offset}")
    print(f"  {preview(output)}")
    return output


def demo_parse_validate() -> None:
    """parse in mode 2"""
    section("Parse: parse (mode 2, JSON + validation report)")

    config = json.dumps(PARSE_CONFIG)
    output, offset = ef.parse(SAMPLE_EDI_INVALID, ef.ParseMode.JSON_VALIDATE, config)
    print(f"  {len(output)} bytes total, validation starts at offset {offset}")
    print(f"  validation -> {preview(output[offset:])}")


def demo_parse_ack() -> None:
    """parse in mode 3"""
    section("Parse: parse (mode 3, JSON + validation + acknowledgment)")

    config = json.dumps(PARSE_CONFIG)
    output, offset = ef.parse(SAMPLE_EDI, ef.ParseMode.JSON_VALIDATE_ACK, config)
    print(f"  {len(output)} bytes total, report starts at offset {offset}")
    print(f"  report -> {preview(output[offset:], 600)}")
    
def demo_parse_ack_invalid() -> None:
    """parse in mode 3"""
    section("Parse: parse (mode 3, JSON + validation + acknowledgment)")

    config = json.dumps(PARSE_CONFIG)
    output, offset = ef.parse(SAMPLE_EDI_INVALID, ef.ParseMode.JSON_VALIDATE_ACK, config)
    print(f"  {len(output)} bytes total, report starts at offset {offset}")
    print(f"  report -> {preview(output[offset:], 600)}")


def demo_split() -> None:
    """start_split, split, get_result"""
    section("Split: start_split, split, get_result")

    ef.start_split(SAMPLE_EDI, ef.ParseMode.JSON, json.dumps(SPLIT_CONFIG))
    step = 0
    while True:
        size, offset, is_last = ef.split()
        step += 1
        payload = ef.get_result(size) if size > 0 else b""
        text = payload.decode("utf-8", errors="replace")
        print(f"  step {step}: size={size} offset={offset} last={is_last}")
        if payload:
            print(f"    {preview(text, 160)}")
        if is_last:
            break


def demo_build(parsed_json: str) -> str:
    """build"""
    section("Build: build")

    edi = ef.build(parsed_json, postfix="\r\n")
    print(f"  {len(edi)} bytes of X12")
    print("  " + edi.replace("\r\n", "\n  ").rstrip())
    return edi


def demo_merge(parsed_json: str) -> None:
    """start_merge, merge, get_result"""
    section("Merge: start_merge, merge, get_result")

    ef.start_merge(parsed_json)
    count = 0
    while True:
        size = ef.merge()
        if size == 0:
            break
        segment = ef.get_result(size).decode("utf-8", errors="replace")
        count += 1
        print(f"  segment {count:>2}: {segment}")
    print(f"  merge produced {count} segments")


def demo_iterators(parsed_json: str) -> None:
    """iter_split, iter_merge convenience wrappers"""
    section("Convenience wrappers: iter_split, iter_merge")

    parts = list(ef.iter_split(SAMPLE_EDI, ef.ParseMode.JSON, json.dumps(SPLIT_CONFIG)))
    print(f"  iter_split -> {len(parts)} payloads, sizes {[len(p) for p, _, _ in parts]}")

    segments = list(ef.iter_merge(parsed_json))
    print(f"  iter_merge -> {len(segments)} segments")


def demo_teardown() -> None:
    """clear_cache, shutdown_logger"""
    section("Teardown: clear_cache, shutdown_logger")

    ef.clear_cache()
    print("  clear_cache -> map, license, stream state and results reset")
    ef.shutdown_logger()
    print("  shutdown_logger -> logger stopped")


def main() -> int:
    parser = argparse.ArgumentParser(description="ediFabric Native X12: every ABI function")
    parser.add_argument("--serial", help="license serial (default: EDIFABRIC_SERIAL or the free plan serial)")
    parser.add_argument("--lib", help="path to edifabric-x12-tools.dll/.so/.dylib or its folder")
    parser.add_argument(
        "--skip-network",
        action="store_true",
        help="skip ensure_token and get_token, authorize with set_serial only",
    )
    args = parser.parse_args()

    serial = args.serial or os.environ.get("EDIFABRIC_SERIAL") or DEFAULT_SERIAL

    section("Load: load_library")
    library = ef.load_library(args.lib)
    print(f"  loaded {library._name}")

    demo_errors()

    exit_code = 0
   
    try:
            demo_logging("edifabric.log")

            try:
                # The free and developer licenses do not support tokens. Authenticate only with serial.
                ef.set_serial(serial)
                print("  set_serial -> ok")
                
                demo_set_local_map()

                parsed_json = demo_parse()
                
                demo_set_online_map()
                
                demo_parse_validate()
                demo_parse_ack()
                demo_parse_ack_invalid()
                demo_split()
                demo_build(parsed_json)
                demo_merge(parsed_json)
                demo_iterators(parsed_json)
            except ef.EdiFabricError as exc:
                print(f"\n{exc}", file=sys.stderr)
                print(
                    "Check that the serial is valid and that MAP/Map.json resolves the "
                    "transaction set to a local model file under MAP/.",
                    file=sys.stderr,
                )
                
                exit_code = 1
            else:
                demo_teardown()
    finally:
            # Release the log file before TemporaryDirectory deletes it (Windows).
            # On the success path demo_teardown already shut the logger down.
            try:
                ef.shutdown_logger()
            except ef.EdiFabricError:
                pass
            

    if exit_code:
        return exit_code

    section("Finished")
    print("Every entry point in c-abi-edifabric_x12_tools.h was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
