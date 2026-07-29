# ediFabric Native X12 — Python bindings

**ediFabric Native** is a self-contained, high-performance X12 EDI native shared library. It converts X12 EDI to JSON (and back),
validates transaction sets, and generates acknowledgments — callable from **any
language with a C foreign-function interface** (C, C++, Rust, Go, Python, Node.js,
Java/JNA, .NET, …). No .NET runtime, JVM, or other dependency is required on the
target machine.

- **Safe** — all operations run locally, and your data never leaves the process where the library is executed
- **Fast** — native code, zero-copy UTF‑8 buffers, streaming split/merge.
- **Portable** — a single native library per platform, no runtime install.
- **Simple ABI** — a handful of C entry points returning integer status codes.

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

- Internet access for the one-time license install and for token retrieval

## Getting started

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
python example_all_functions.py --skip-network         # authorize with set_serial only
```

The library path is resolved from `--lib`, then `EDIFABRIC_X12_LIB`, then the
module folder, its parent, and the working directory. The serial comes from
`--serial`, then `EDIFABRIC_SERIAL`, then the built-in free plan serial.

## Usage

```python
import json
import edifabric_x12 as ef

serial = "your-serial"

ef.load_library()                  # or ef.load_library(r"C:\libs\edifabric-x12-tools.dll")
ef.set_serial(serial)              # or ef.set_token(token) for offline use
ef.set_map(json.dumps({"default": serial, "maps": {}}))

edi = open("purchase-order.edi", "rb").read()
transactions, _ = ef.parse(edi, ef.ParseMode.JSON)
print(transactions)
```

Read a file from a subfolder of the script:

```python
from pathlib import Path

edi = (Path(__file__).resolve().parent / "samples" / "purchase-order.edi").read_bytes()
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
config = json.dumps({"split": {"segment_id": "ST", "segment_depth": 0, "loop_id": None}})

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

Every wrapper raises `EdiFabricError` when the native call returns a non-zero
status. Buffer growth (`InsufficientCapacity`) is retried automatically.

| Group | Functions |
| --- | --- |
| Loading | `load_library` |
| Lifecycle | `init_logger`, `shutdown_logger`, `clear_cache` |
| Licensing | `install_license`, `get_app_version`, `get_token`, `validate_token`, `set_token`, `get_token_expiration`, `set_serial` |
| Model map | `set_map` |
| Processing | `parse`, `start_split`, `split`, `build`, `start_merge`, `merge`, `get_result` |
| Errors | `get_error`, `free_error`, `check` |
| Wrappers | `iter_split`, `iter_merge` |
| Constants | `ParseMode`, `LogLevel`, `ErrorCode`, `EdiFabricError` |

`get_error` frees the native string for you. Call `free_error` only if you
invoke the raw export yourself. Builds that do not export `free_error` fall back
to the C runtime `free`.

## Licensing

Two models are supported. Tokens are recommended for containers, air-gapped
machines, and high volume; serials are simplest when always online.

```python
# Token: fetch once with internet access, cache it, set it at process start
token = ef.get_token(serial)
ef.set_token(token)
print(ef.get_token_expiration())   # .NET UTC ticks, 0 when unset

# Serial: register the machine once, then authorize per process
ef.install_license(serial)
ef.set_serial(serial)
```

The example caches its token in `.edifabric_token`. Add that file to
`.gitignore` before committing.

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

Download models in ediFabric Native format from the EdiNation Spec Library, or
build custom ones in the EdiNation Spec Builder.

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
| 629 | License not installed, run `install_license` |
| 630 | Application maximum version exceeded |
| 631 | Token expired |
| 632 | Token missing |
| 633 | Maximum licenses exceeded |
| 634 | License snapshot not found |
| 635 | License not set, call `set_token` or `set_serial` |

## Troubleshooting

**`FileNotFoundError: Could not load edifabric-x12-tools.dll`** — the library is
not on any searched path. Pass `ef.load_library("/path/to/library")` or set
`EDIFABRIC_X12_LIB`.

**Error 615 on parse** — call `set_map` before parsing or splitting. `clear_cache`
resets the map, so reload it afterwards.

**Error 635 on parse** — authorize first with `set_token` or `set_serial`.

**Error 633 on install_license** — the plan's machine quota is used up. Switch to
token authorization or contact support.

## Links

- [Documentation](https://support.edifabric.com/hc/en-us/articles/37276016388125-Introduction)
- [Product page](https://www.edifabric.com/edifabric-native.html)
- Support: support@edifabric.com
