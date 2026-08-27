"""
Python ctypes bindings for ediFabric Native X12 (see c-abi-edifabric_x12_tools.h).

Load the platform shared library (edifabric-x12-tools.dll / .so / .dylib) and call
the wrappers below. All payloads cross the boundary as UTF-8 byte buffers.
Native return codes: 0 = success, 1 = InsufficientCapacity (grow-and-retry),
anything else is an error whose message comes from get_error.

The wrappers handle grow-and-retry internally and raise EdiFabricError on failure.
"""

from __future__ import annotations

import ctypes
import os
import sys
from enum import IntEnum
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Tuple, Union

BytesLike = Union[bytes, bytearray, memoryview, str]

SUCCESS = 0
INSUFFICIENT_CAPACITY = 1


class ParseMode(IntEnum):
    """mode argument for parse / start_split."""

    JSON = 1
    JSON_VALIDATE = 2
    JSON_VALIDATE_ACK = 3

class LogLevel(IntEnum):
    """min_level argument for init_logger."""

    TRACE = 0
    DEBUG = 1
    INFORMATION = 2
    WARNING = 3
    ERROR = 4
    ALL = 5


class ErrorCode(IntEnum):
    """Library-level error codes. Validation codes come from the engine."""

    INSUFFICIENT_CAPACITY = 1
    UNKNOWN = 501
    NO_CONNECTION = 502
    INVALID_MAP = 503
    INCORRECT_INPUT = 611
    LOGGER_INIT = 612
    MAP_DESERIALIZE = 613
    INCORRECT_CAPACITY = 614
    MAP_NOT_SET = 615
    INCORRECT_MODE = 616
    NO_JSON = 617
    VALIDATION_UNAVAILABLE = 618
    VALIDATION_SERIALIZE = 619
    INCORRECT_TOKEN = 620
    CONFIG_DESERIALIZE = 621
    SPLIT_SEGMENT_ID_MISSING = 622
    SPLIT_NOT_STARTED = 623
    NO_RESULT = 624
    RESULT_SIZE_MISMATCH = 625
    MERGE_NOT_STARTED = 626
    INCORRECT_OUTPUT_POINTER = 627
    INCORRECT_SERIAL = 628
    LICENSE_NOT_INSTALLED = 629
    APP_VERSION_EXCEEDED = 630
    TOKEN_EXPIRED = 631
    TOKEN_MISSING = 632
    MAX_LICENSES_EXCEEDED = 633
    LICENSE_SNAPSHOT_MISSING = 634
    LICENSE_NOT_SET = 635
    RATE_EXCEEDED = 636
    INVALID_JSON = 637
    INCORRECT_LICENSE = 638


class EdiFabricError(RuntimeError):
    """Raised when a native call returns a non-zero status code."""

    def __init__(self, code: int, message: str, api: str = "") -> None:
        self.code = code
        self.message = message
        self.api = api
        prefix = f"{api}: " if api else ""
        super().__init__(f"{prefix}error {code}: {message}")


_LIB: Optional[ctypes.CDLL] = None
_HAS_FREE_ERROR = False


# ---------------------------------------------------------------------------
# Library loading
# ---------------------------------------------------------------------------

def _library_filename() -> str:
    if sys.platform.startswith("win"):
        return "edifabric-x12-tools.dll"
    if sys.platform == "darwin":
        return "edifabric-x12-tools.dylib"
    return "edifabric-x12-tools.so"


def _candidates(explicit: Optional[Union[str, Path]]) -> List[Path]:
    name = _library_filename()
    found: List[Path] = []
    env = os.environ.get("EDIFABRIC_X12_LIB")
    if explicit:
        path = Path(explicit)
        found.append(path / name if path.is_dir() else path)
    if env:
        path = Path(env)
        found.append(path / name if path.is_dir() else path)
    here = Path(__file__).resolve().parent
    found.extend([here / name, here.parent / name, Path.cwd() / name])
    return found


def _bind(lib: ctypes.CDLL) -> None:
    global _HAS_FREE_ERROR

    c_int_p = ctypes.POINTER(ctypes.c_int)
    c_int64_p = ctypes.POINTER(ctypes.c_int64)
    c_ubyte_p = ctypes.POINTER(ctypes.c_ubyte)
    # Buffers are declared as c_void_p so both string buffers and None are accepted.
    buf = ctypes.c_void_p

    signatures = {
        "init_logger": ([buf, ctypes.c_int, ctypes.c_int], ctypes.c_int),
        "shutdown_logger": ([], ctypes.c_int),
        "clear_cache": ([], ctypes.c_int),
        "ensure_token": ([buf, ctypes.c_int, ctypes.c_int], ctypes.c_int),
        "get_app_version": ([c_int_p], ctypes.c_int),
        "get_token": ([buf, ctypes.c_int, buf, ctypes.c_int, c_int_p], ctypes.c_int),
        "validate_token": ([buf, ctypes.c_int], ctypes.c_int),
        "set_token": ([buf, ctypes.c_int], ctypes.c_int),
        "get_token_expiration": ([c_int64_p], ctypes.c_int),
        "set_serial": ([buf, ctypes.c_int], ctypes.c_int),
        "set_map": ([buf, ctypes.c_int], ctypes.c_int),
        "parse": (
            [buf, ctypes.c_int, ctypes.c_int, buf, ctypes.c_int, buf, ctypes.c_int, c_int_p, c_int_p],
            ctypes.c_int,
        ),
        "start_split": ([buf, ctypes.c_int, ctypes.c_int, buf, ctypes.c_int], ctypes.c_int),
        "split": ([c_int_p, c_int_p, c_ubyte_p], ctypes.c_int),
        "build": ([buf, ctypes.c_int, ctypes.c_char_p, buf, ctypes.c_int, c_int_p], ctypes.c_int),
        "start_merge": ([buf, ctypes.c_int], ctypes.c_int),
        "merge": ([c_int_p], ctypes.c_int),
        "get_result": ([buf, ctypes.c_int], ctypes.c_int),
        "get_error": ([ctypes.c_int], ctypes.c_void_p),
    }
    for name, (argtypes, restype) in signatures.items():
        fn = getattr(lib, name)
        fn.argtypes = argtypes
        fn.restype = restype

    _HAS_FREE_ERROR = hasattr(lib, "free_error")
    if _HAS_FREE_ERROR:
        lib.free_error.argtypes = [ctypes.c_void_p]
        lib.free_error.restype = None


def load_library(path: Optional[Union[str, Path]] = None) -> ctypes.CDLL:
    """
    Load and bind the native library.

    path may be the library file or the folder containing it. When omitted, the
    EDIFABRIC_X12_LIB variable, this module's folder, its parent, and the current
    working directory are tried in that order. Cached after the first success.
    """
    global _LIB
    if _LIB is not None and path is None:
        return _LIB

    last_error: Optional[OSError] = None
    for candidate in _candidates(path):
        if not candidate.is_file():
            continue
        try:
            lib = ctypes.CDLL(str(candidate))
        except OSError as exc:
            last_error = exc
            continue
        _bind(lib)
        _LIB = lib
        return lib

    tried = ", ".join(str(p) for p in _candidates(path))
    raise FileNotFoundError(
        f"Could not load {_library_filename()}. Tried: {tried}. Last error: {last_error}"
    )


def _lib() -> ctypes.CDLL:
    return _LIB if _LIB is not None else load_library()


# ---------------------------------------------------------------------------
# Buffer / error helpers
# ---------------------------------------------------------------------------

def _utf8(data: Optional[BytesLike]) -> Tuple[Optional[ctypes.Array], int]:
    """Return (buffer, length); (None, 0) for None so the ABI receives a null pointer."""
    if data is None:
        return None, 0
    if isinstance(data, str):
        raw = data.encode("utf-8")
    elif isinstance(data, (bytearray, memoryview)):
        raw = bytes(data)
    else:
        raw = data
    return ctypes.create_string_buffer(raw, len(raw)), len(raw)


def _crt_free(pointer: int) -> None:
    """Fallback for builds that do not export free_error."""
    names = ("ucrtbase", "msvcrt") if sys.platform.startswith("win") else (None,)
    for name in names:
        try:
            crt = ctypes.CDLL(name)
        except OSError:
            continue
        crt.free.argtypes = [ctypes.c_void_p]
        crt.free.restype = None
        crt.free(pointer)
        return


def free_error(pointer: int) -> None:
    """
    Release a string returned by the raw get_error export.

    get_error() below already does this; call free_error only when you invoke the
    raw export yourself.
    """
    if not pointer:
        return
    if _HAS_FREE_ERROR:
        _lib().free_error(pointer)
    else:
        _crt_free(pointer)


def get_error(error_code: int) -> str:
    """Return the message for an error code, releasing the native string."""
    pointer = _lib().get_error(int(error_code))
    if not pointer:
        return f"Unknown error {error_code}"
    try:
        value = ctypes.cast(pointer, ctypes.c_char_p).value
        return value.decode("utf-8", errors="replace") if value else f"Unknown error {error_code}"
    finally:
        free_error(pointer)


def check(rc: int, api: str = "") -> None:
    """Raise EdiFabricError unless rc is SUCCESS."""
    if rc != SUCCESS:
        raise EdiFabricError(rc, get_error(rc), api)


def _with_growth(capacity: int, api: str, call: Callable[[ctypes.Array, int, ctypes.c_int], int]) -> bytes:
    """Run a grow-and-retry output call; call(buffer, capacity, out_length) -> rc."""
    capacity = max(1, int(capacity))
    out_length = ctypes.c_int(0)
    while True:
        buffer = ctypes.create_string_buffer(capacity)
        rc = call(buffer, capacity, out_length)
        if rc == INSUFFICIENT_CAPACITY:
            capacity = out_length.value if out_length.value > capacity else capacity * 2
            continue
        check(rc, api)
        return buffer.raw[: out_length.value]


# ---------------------------------------------------------------------------
# Lifecycle and logging
# ---------------------------------------------------------------------------

def init_logger(path: BytesLike, min_level: int = LogLevel.INFORMATION) -> None:
    """Write a log file at path; min_level is 0=Trace through 4=Error."""
    buffer, length = _utf8(path)
    check(_lib().init_logger(buffer, length, int(min_level)), "init_logger")


def shutdown_logger() -> None:
    """Flush and stop the logger."""
    check(_lib().shutdown_logger(), "shutdown_logger")


def clear_cache() -> None:
    """Reset the model map, split/merge state, last result, license, and logger."""
    check(_lib().clear_cache(), "clear_cache")


# ---------------------------------------------------------------------------
# Licensing
# ---------------------------------------------------------------------------

def ensure_token(serial: BytesLike, seconds: int) -> None:
    """
    Cache a token for runtime authorization against the license server.

    Retrieves a new token if the cached token expires within the specified
    number of seconds.
    """
    buffer, length = _utf8(serial)
    check(_lib().ensure_token(buffer, length, int(seconds)), "ensure_token")


def get_app_version() -> int:
    """Return the library application version."""
    version = ctypes.c_int(0)
    check(_lib().get_app_version(ctypes.byref(version)), "get_app_version")
    return version.value


def get_token(serial: BytesLike, capacity: int = 4096) -> str:
    """Fetch a signed license token for the serial. Requires internet access."""
    serial_buffer, serial_length = _utf8(serial)

    def call(buffer: ctypes.Array, cap: int, out_length: ctypes.c_int) -> int:
        return _lib().get_token(serial_buffer, serial_length, buffer, cap, ctypes.byref(out_length))

    return _with_growth(capacity, "get_token", call).decode("utf-8")


def validate_token(token: BytesLike) -> None:
    """Validate a token without caching it."""
    buffer, length = _utf8(token)
    check(_lib().validate_token(buffer, length), "validate_token")


def set_token(token: BytesLike) -> None:
    """Cache a token for this process."""
    buffer, length = _utf8(token)
    check(_lib().set_token(buffer, length), "set_token")


def get_token_expiration() -> int:
    """Return token expiry as .NET UTC ticks; 0 when no token is set."""
    expiration = ctypes.c_int64(0)
    check(_lib().get_token_expiration(ctypes.byref(expiration)), "get_token_expiration")
    return int(expiration.value)


def set_serial(serial: BytesLike) -> None:
    """Cache a serial for runtime authorization against the license server."""
    buffer, length = _utf8(serial)
    check(_lib().set_serial(buffer, length), "set_serial")


# ---------------------------------------------------------------------------
# Model map
# ---------------------------------------------------------------------------

def set_map(map_json: BytesLike) -> None:
    """Load the template map JSON. Call once before parse or start_split."""
    buffer, length = _utf8(map_json)
    check(_lib().set_map(buffer, length), "set_map")


# ---------------------------------------------------------------------------
# Parse, split, build, merge
# ---------------------------------------------------------------------------

def parse(
    edi: BytesLike,
    mode: int = ParseMode.JSON,
    config: Optional[BytesLike] = None,
    capacity: Optional[int] = None,
) -> Tuple[str, int]:
    """
    Parse a whole interchange and return (output, offset).

    offset is 0 for mode 1; for modes 2 and 3 it marks where the validation and
    acknowledgment section begins inside output.
    """
    input_buffer, input_length = _utf8(edi)
    config_buffer, config_length = _utf8(config)
    cap = capacity if capacity is not None else max(4096, input_length * 12)
    out_length = ctypes.c_int(0)
    out_offset = ctypes.c_int(0)

    while True:
        buffer = ctypes.create_string_buffer(cap)
        rc = _lib().parse(
            input_buffer,
            input_length,
            int(mode),
            config_buffer,
            config_length,
            buffer,
            cap,
            ctypes.byref(out_length),
            ctypes.byref(out_offset),
        )
        if rc == INSUFFICIENT_CAPACITY:
            cap = out_length.value if out_length.value > cap else cap * 2
            continue
        check(rc, "parse")
        return buffer.raw[: out_length.value].decode("utf-8"), out_offset.value


def start_split(
    edi: BytesLike,
    mode: int = ParseMode.JSON,
    config: Optional[BytesLike] = None,
) -> None:
    """Begin a streaming split. config must contain a split section with segment_id."""
    input_buffer, input_length = _utf8(edi)
    config_buffer, config_length = _utf8(config)
    check(
        _lib().start_split(input_buffer, input_length, int(mode), config_buffer, config_length),
        "start_split",
    )


def split() -> Tuple[int, int, bool]:
    """
    Advance the split stream and return (size, offset, is_last).

    Fetch the payload with get_result(size) whenever size is greater than zero.
    """
    size = ctypes.c_int(0)
    offset = ctypes.c_int(0)
    last = ctypes.c_ubyte(0)
    check(
        _lib().split(ctypes.byref(size), ctypes.byref(offset), ctypes.byref(last)),
        "split",
    )
    return size.value, offset.value, bool(last.value)


def build(
    json_text: BytesLike,
    postfix: Optional[str] = None,
    capacity: Optional[int] = None,
) -> str:
    """
    Build X12 EDI from transaction-set JSON.

    postfix is appended after each segment terminator, for example "\\r\\n".
    Pass None for compact single-line output.
    """
    input_buffer, input_length = _utf8(json_text)
    postfix_bytes = postfix.encode("utf-8") if postfix is not None else None
    cap = capacity if capacity is not None else max(4096, input_length)

    def call(buffer: ctypes.Array, current: int, out_length: ctypes.c_int) -> int:
        return _lib().build(
            input_buffer, input_length, postfix_bytes, buffer, current, ctypes.byref(out_length)
        )

    return _with_growth(cap, "build", call).decode("utf-8")


def start_merge(json_text: BytesLike) -> None:
    """Begin a streaming merge from a full interchange JSON document."""
    buffer, length = _utf8(json_text)
    check(_lib().start_merge(buffer, length), "start_merge")


def merge() -> int:
    """Return the size of the next segment, or 0 at the end of the stream."""
    size = ctypes.c_int(0)
    check(_lib().merge(ctypes.byref(size)), "merge")
    return size.value


def get_result(size: int) -> bytes:
    """Copy the last split or merge result. size must match the reported size."""
    if size < 0:
        raise ValueError("size must be zero or greater")
    buffer = ctypes.create_string_buffer(size)
    check(_lib().get_result(buffer, size), "get_result")
    return buffer.raw[:size]


# ---------------------------------------------------------------------------
# Convenience iterators
# ---------------------------------------------------------------------------

def iter_split(
    edi: BytesLike,
    mode: int = ParseMode.JSON,
    config: Optional[BytesLike] = None,
) -> Iterator[Tuple[bytes, int, bool]]:
    """Yield (payload, offset, is_last) for every split step that produces data."""
    start_split(edi, mode, config)
    while True:
        size, offset, is_last = split()
        if size > 0:
            yield get_result(size), offset, is_last
        if is_last:
            break


def iter_merge(json_text: BytesLike) -> Iterator[bytes]:
    """Yield each X12 segment produced by a merge stream."""
    start_merge(json_text)
    while True:
        size = merge()
        if size == 0:
            break
        yield get_result(size)
