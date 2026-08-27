# ediFabric Native X12 — Python bindings

**ediFabric Native** is a self-contained, high-performance X12 EDI native shared library. It converts X12 EDI to JSON (and back),
validates transaction sets, and generates acknowledgments — callable from **any
language with a C foreign-function interface** (C, C++, Rust, Go, Python, Node.js,
Java/JNA, .NET, …). No .NET runtime, JVM, or other dependency is required on the
target machine.

Python `ctypes` bindings for [ediFabric Native](https://www.edifabric.com/edifabric-native.html).

| File | Purpose |
| --- | --- |
| `edifabric_x12.py` | ctypes bindings for the complete C ABI |
| `example_all_functions.py` | runnable walkthrough of every entry point |
| `c-abi-edifabric_x12_tools.h` | the C header these bindings mirror |

## Requirements

- Python 3.8 or later (standard library only)
- 64-bit Windows, Linux, or macOS
- The native library for your platform:

| Platform | File |
| --- | --- |
| Windows | `edifabric-x12-tools.dll` |
| Linux | `edifabric-x12-tools.so` |
| macOS | `edifabric-x12-tools.dylib` |

[Download **ediFabric Native** Library](https://support.edifabric.com/hc/en-us/articles/37289848931869-Download)

Plus your **model files** (per transaction set) and a **map file** that tells the
engine where to find them. See [Model map](#model-map) for details.

## Getting started

**Download the library** from [here](https://support.edifabric.com/hc/en-us/articles/37289848931869-Download).
Put the native library beside `edifabric_x12.py`, then run the walkthrough:

```bash
python example_all_functions.py
```

It authorizes with the free plan serial, loads the model map, and calls every
function in the ABI, printing what each one returns.

```
Parse: parse (mode 2, JSON + validation report)
  1754 bytes total, validation starts at offset 1708
  validation -> {"errors":[],"errors_count":0,"data_count":10}
```

Options:

```bash
python example_all_functions.py --serial YOUR_SERIAL   # use your own license
python example_all_functions.py --lib /opt/edifabric   # library file or folder
```

The library path is resolved from `--lib`, then `EDIFABRIC_X12_LIB`, then the
module folder, its parent, and the working directory. The serial comes from
`--serial`, then `EDIFABRIC_SERIAL`, then the built-in free plan serial.

All strings and payloads cross the boundary as **UTF‑8 byte buffers**
(`pointer + length`). Every function returns `0` on success or a non-zero
[error code](#error-codes).

## Usage

```python
import json
import edifabric_x12 as ef

serial = "your-serial"

ef.load_library()                  # or ef.load_library(r"C:\libs\edifabric-x12-tools.dll")
ef.set_serial(serial)              # or ef.set_token(token) for offline use (only available for the Enterprise license)
ef.set_map(json.dumps({"default": serial, "maps": {}}))

edi = open("purchase-order.edi", "rb").read()
transactions, _ = ef.parse(edi, ef.ParseMode.JSON)
print(transactions)
```

Read a file from a subfolder of the script:

```python
from pathlib import Path

edi = (Path(__file__).resolve().parent / "edi" / "838p.txt").read_bytes()
```

### Validation and acknowledgments

`parse` returns `(output, offset)`. In modes 2 and 3, `offset` marks where the
validation and acknowledgment JSON starts inside the output.

```python
config = json.dumps({
    "validate": {"snip_level": 2, "max_errors": 0},
    "ack": {"gen997": False, "supress_ta1": False},
})

output, offset = ef.parse(edi, ef.ParseMode.JSON_VALIDATE_ACK, config)
transactions = output[:offset]
report = json.loads(output[offset:])
print(report["errors_count"], report["ack"])
```

| Mode | Constant | Output |
| --- | --- | --- |
| 1 | `ParseMode.JSON` | transaction-set JSON |
| 2 | `ParseMode.JSON_VALIDATE` | JSON plus a validation report |
| 3 | `ParseMode.JSON_VALIDATE_ACK` | JSON plus validation and a 999/997/TA1 acknowledgment |

### Streaming large interchanges

`iter_split` streams one transaction set (or repeating loop) at a time with flat
memory use. `segment_id` must be `ST` or the first segment of a repeating loop.

```python
config = json.dumps({"split": {"segment_id": "LX", "segment_depth": 6, "loop_id": "2400"}})

for payload, offset, is_last in ef.iter_split(edi, ef.ParseMode.JSON, config):
    handle(json.loads(payload))
```

`iter_merge` streams a full interchange JSON document back out one segment at a time:

```python
with open("out.edi", "wb") as f:
    for segment in ef.iter_merge(transactions):
        f.write(segment + b"\r\n")
```

Both wrap the underlying `start_split`/`split`/`get_result` and
`start_merge`/`merge`/`get_result` sequences, which you can also drive directly.

### Building EDI

```python
edi_text = ef.build(transactions, postfix="\r\n")   # postfix=None for compact output
```

## API reference

Conventions used by every function:

- Returns `int`: `0` = success, non-zero = [error code](#error-codes).
- Inputs are UTF‑8 `byte*` + `int length`.
- Output functions use **grow-and-retry**: if the buffer is too small the call
  returns `1` (`InsufficientCapacity`) and writes the required size into the
  length out-parameter; reallocate and call again.
- Exceptions never cross the boundary.

Every wrapper raises `EdiFabricError` when the native call returns a non-zero
status. Buffer growth (`InsufficientCapacity`) is retried automatically.

| Group | Functions |
| --- | --- |
| Loading | `load_library` |
| Lifecycle | `init_logger`, `shutdown_logger`, `clear_cache` |
| Licensing | `ensure_token`, `get_app_version`, `get_token`, `validate_token`, `set_token`, `get_token_expiration`, `set_serial` |
| Model map | `set_map` |
| Processing | `parse`, `start_split`, `split`, `build`, `start_merge`, `merge`, `get_result` |
| Errors | `get_error`, `free_error`, `check` |
| Wrappers | `iter_split`, `iter_merge` |
| Constants | `ParseMode`, `LogLevel`, `ErrorCode`, `EdiFabricError` |

`get_error` frees the native string for you. Call `free_error` only if you
invoke the raw export yourself. Builds that do not export `free_error` fall back
to the C runtime `free`.

## Licensing

> [!NOTE]
> The examples are available with a free plan which can be used only with Serial model validation. 
> You don't need to call `ensure_token` with the free plan, and the only licensing call must be `set_serial`.

The serial key for the free plan is:
```
bd96a836feca45cb91c86ee65d281f52
```

Two models are supported. Tokens are recommended for containers, air-gapped
machines, and high volume; serials are simplest when always online.

```python
# Token: cache a token, refreshing it if it expires within N seconds
ef.ensure_token(serial, 3600)
print(ef.get_token_expiration())   # .NET UTC ticks, 0 when unset

# Serial: authorize per process against the license server
ef.set_serial(serial)
```

## Model map

`set_map` tells the engine where to find transaction-set models. Keys are
`message:version`. Set `default` to your serial to resolve unmapped transaction
sets through the online spec service, or leave it `null` and map everything locally.

```json
{
  "default": null,
  "maps": {
    "837:005010X222A1": { "type": 1, "name": "837P.json", "location": "/opt/models" },
    "850:005010":       { "type": 1, "name": "850.json",  "location": "/opt/models" }
  }
}
```

All X12 transactions, such as 837P, 834, 850, etc. are represented as proprietary JSON. 
Download a standard model from [EdiNation Spec Library](https://edination.edifabric.com/edi-spec-library.html), 
or a custom model from [EdiNation Spec Builder](https://edination.edifabric.com/edi-spec-builder.html). 
Create/modify models in OpenEDI format, upload them in EdiNation Spec Builder and download them as JSON for use in ediFabric Native.

To download a model in either EdiNation Spec Library or EdiNation Spec Builder, 
select the model first, then in the JSON view 
select the Download button in the top right corner.

![Model Img](https://github.com/EdiFabric/native-python-examples/blob/main/model.png)

Choose to download as **ediFabric Native**.

## Configuration JSON

All JSON uses **`snake_case`** keys and is case-insensitive.

### ParseConfig (`parse`)

```json
{
  "validate": { "regex": null, "date_format": null, "time_format": null,
                "skip_seq_count": false, "skip_hl_seq": false,
                "snip_level": 0, "max_errors": 0 },
  "ack":      { "supress_ta1": false, "ak901p": false,
                "gen_for_valid": false, "gen997": false }
}
```

- `validate` — applied when `mode ≥ 2`; `snip_level` is `1`–`4`.
- `ack` — applied when `mode == 3`.

All sections are optional for `parse`.

### SplitConfig (`start_split`)

```json
{
  "split":    { "segment_id": "ST", "segment_depth": 0, "loop_id": null }
}
```

- `split` — required for `start_split`.

Splitting is possible for the following boundaries:

- Transaction - for files that contain batches of transactions.
- Repeating loop - for files that contain batches of loops, such as order lines, claims or benefit enrollments.

The splitter must be configured as follows:

- `segment_id`  — the name of the segment to split by. It must be either ST or the first segment in the repeatable loop (Mandatory).
- `segment_depth` — the depth of the segment in the model hierarchy (Mandatory).
- `loop_id` — the name of the loop for the segment specified in segment_id (Optional).

The values for the splitter can be found in EdiNation by loading a sample file. For example, if you want to split by loop 2000A in 837P, load an 837P file in EdiNation (or use the example one), click on the first segment in that loop, e.g., HL. `segment_id` is **CODE**,  `loop_id` is the last item in **PATH**, and `segment_depth` is **DEPTH**.

> [!NOTE]
> If a segment does not show a SPLITTER copy button, than splitting is not possible by that segment.

The easiest way to get the splitter configuration is to click on the copy button under SPLITTER that has the full splitter JSON pre-configured.

![Model Img](https://github.com/EdiFabric/native-python-examples/blob/main/splitter.png)

## Threading

The library holds process-global state (model map, active split reader, active
merge writer, last result, license) behind an internal lock. `parse` and `build`
are independent per call, but each split or merge sequence must run to
completion without another split or merge interleaving from a different thread.

## Error codes

`0` is success and `1` means the output buffer was too small. Library-level codes
are exposed as `ErrorCode`, and `get_error(code)` returns the message.

| Code | Meaning |
| --- | --- |
| 501 | Unknown |
| 502 | No internet access to the authentication API |
| 503 | Local map file has invalid paths or file names |
| 611 | Incorrect or empty input |
| 612 | Logger initialization failed |
| 613 | Map JSON could not be deserialized |
| 614 | Negative output capacity |
| 615 | Model map not set, call `set_map` first |
| 616 | Mode must be 1, 2, or 3 |
| 617 | No JSON produced |
| 618 | Validation result unavailable |
| 619 | Validation report serialization failed |
| 620 | Incorrect token |
| 621 | Config JSON could not be deserialized |
| 622 | Split `segment_id` missing or empty |
| 623 | `split` called before `start_split` |
| 624 | No result available for `get_result` |
| 625 | `get_result` buffer size mismatch |
| 626 | `merge` called before `start_merge` |
| 627 | Incorrect or null output pointer |
| 628 | Incorrect serial |
| 629 | License not installed |
| 630 | Application maximum version exceeded |
| 631 | Token expired |
| 632 | Token missing |
| 633 | Maximum licenses exceeded |
| 634 | License snapshot not found |
| 635 | License not set, call `set_token` or `set_serial` |
| 636 | Rate exceeded |
| 637 | Invalid JSON |
| 638 | Incorrect license |

## Troubleshooting

**`FileNotFoundError: Could not load edifabric-x12-tools.dll`** — the library is
not on any searched path. Pass `ef.load_library("/path/to/library")` or set
`EDIFABRIC_X12_LIB`.

**Error 615 on parse** — call `set_map` before parsing or splitting. `clear_cache`
resets the map, so reload it afterwards.

**Error 635 on parse** — authorize first with `set_token` or `set_serial`.

**Error 633 on ensure_token** — the plan's machine quota is used up. Switch to
token authorization or contact support.

## Links

- [Documentation](https://support.edifabric.com/hc/en-us/articles/37276016388125-Introduction)
- [Product page](https://www.edifabric.com/edifabric-native.html)
- Support: support@edifabric.com
