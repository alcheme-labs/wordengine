from __future__ import annotations

import base64
import math
from typing import Any, Mapping, Sequence


IMPLICIT_OBSERVATION_CHANNEL_TILE_SCHEMA = "implicit_observation_channel_tile_v1"

FORBIDDEN_OBSERVATION_KEYS = {
    "css_color",
    "viewer_shape",
    "viewer_label",
    "viewer_transform",
    "canvas_pixels",
    "mesh",
    "sprite",
    "object_asset_id",
}


def _assert_no_forbidden_keys(value: Any, *, path: str = "tile") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in FORBIDDEN_OBSERVATION_KEYS:
                raise ValueError(f"forbidden observation channel key at {path}: {key}")
            _assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def _finite_pair(values: Sequence[Any], *, name: str) -> list[float]:
    if len(values) != 2:
        raise ValueError(f"{name} must have two values")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result) or result[1] <= result[0]:
        raise ValueError(f"{name} must be finite increasing range")
    return result


def _rle_u16(values: Sequence[int]) -> str:
    raw = bytearray()
    index = 0
    while index < len(values):
        current = int(values[index])
        run = 1
        while index + run < len(values) and run < 255 and int(values[index + run]) == current:
            run += 1
        raw.append(run)
        raw.extend(current.to_bytes(2, "big"))
        index += run
    return "base64:" + base64.b64encode(bytes(raw)).decode("ascii")


def _unrle_u16(data: str, count: int) -> list[int]:
    encoded = data.removeprefix("base64:")
    raw = base64.b64decode(encoded)
    values: list[int] = []
    cursor = 0
    while cursor < len(raw):
        run = raw[cursor]
        value = int.from_bytes(raw[cursor + 1 : cursor + 3], "big")
        values.extend([value] * run)
        cursor += 3
    if len(values) != count:
        raise ValueError("decoded u16 observation channel size mismatch")
    return values


def _rle_rgba(values: Sequence[Sequence[int]]) -> str:
    raw = bytearray()
    index = 0
    while index < len(values):
        current = [int(item) for item in values[index]]
        run = 1
        while index + run < len(values) and run < 255 and [int(item) for item in values[index + run]] == current:
            run += 1
        raw.append(run)
        raw.extend(current)
        index += run
    return "base64:" + base64.b64encode(bytes(raw)).decode("ascii")


def _unrle_rgba(data: str, count: int) -> list[list[int]]:
    encoded = data.removeprefix("base64:")
    raw = base64.b64decode(encoded)
    values: list[list[int]] = []
    cursor = 0
    while cursor < len(raw):
        run = raw[cursor]
        pixel = list(raw[cursor + 1 : cursor + 5])
        values.extend([pixel] * run)
        cursor += 5
    if len(values) != count:
        raise ValueError("decoded rgb observation channel size mismatch")
    return values


def build_u16_observation_channel_tile(
    channel: str,
    tile_xy: Sequence[int],
    tile_shape: Sequence[int],
    values: Sequence[float | None],
    value_range: Sequence[float],
    source_ray_sample_record_id: str,
    source_record_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    lower, upper = _finite_pair(value_range, name="value_range")
    width, height = [int(value) for value in tile_shape]
    if width <= 0 or height <= 0 or len(values) != width * height:
        raise ValueError("observation channel tile shape mismatch")
    encoded_values: list[int] = []
    for value in values:
        if value is None:
            encoded_values.append(0)
            continue
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("observation channel value must be finite")
        clamped = min(upper, max(lower, numeric))
        scaled = 1 + round(((clamped - lower) / (upper - lower)) * 65534)
        encoded_values.append(max(1, min(65535, scaled)))
    tile = {
        "schema": IMPLICIT_OBSERVATION_CHANNEL_TILE_SCHEMA,
        "channel": str(channel),
        "tile_xy": [int(value) for value in tile_xy],
        "tile_shape": [width, height],
        "encoding": "u16_rle_base64",
        "range": [lower, upper],
        "data": _rle_u16(encoded_values),
        "source_ray_sample_record_id": str(source_ray_sample_record_id),
        "source_record_ids": [str(value) for value in (source_record_ids or [source_ray_sample_record_id])],
        "is_authority_state": False,
    }
    validate_implicit_observation_channel_tile(tile)
    return tile


def decode_u16_observation_channel_tile(tile: Mapping[str, Any]) -> list[float | None]:
    validate_implicit_observation_channel_tile(tile)
    width, height = [int(value) for value in tile["tile_shape"]]
    lower, upper = _finite_pair(tile["range"], name="range")
    decoded = _unrle_u16(str(tile["data"]), width * height)
    values: list[float | None] = []
    for encoded in decoded:
        if encoded == 0:
            values.append(None)
        else:
            values.append(lower + ((encoded - 1) / 65534.0) * (upper - lower))
    return values


def build_rgb8_observation_channel_tile(
    channel: str,
    tile_xy: Sequence[int],
    tile_shape: Sequence[int],
    values: Sequence[Sequence[float] | None],
    source_ray_sample_record_id: str,
    source_record_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    width, height = [int(value) for value in tile_shape]
    if width <= 0 or height <= 0 or len(values) != width * height:
        raise ValueError("observation channel tile shape mismatch")
    encoded_values: list[list[int]] = []
    for value in values:
        if value is None:
            encoded_values.append([0, 0, 0, 0])
            continue
        if len(value) != 3:
            raise ValueError("rgb observation channel values must have length 3")
        encoded_values.append([max(0, min(255, round(float(channel_value) * 255))) for channel_value in value] + [255])
    tile = {
        "schema": IMPLICIT_OBSERVATION_CHANNEL_TILE_SCHEMA,
        "channel": str(channel),
        "tile_xy": [int(value) for value in tile_xy],
        "tile_shape": [width, height],
        "encoding": "rgb8_rle_base64",
        "data": _rle_rgba(encoded_values),
        "source_ray_sample_record_id": str(source_ray_sample_record_id),
        "source_record_ids": [str(value) for value in (source_record_ids or [source_ray_sample_record_id])],
        "is_authority_state": False,
    }
    validate_implicit_observation_channel_tile(tile)
    return tile


def decode_rgb8_observation_channel_tile(tile: Mapping[str, Any]) -> list[tuple[float, float, float] | None]:
    validate_implicit_observation_channel_tile(tile)
    width, height = [int(value) for value in tile["tile_shape"]]
    decoded = _unrle_rgba(str(tile["data"]), width * height)
    values: list[tuple[float, float, float] | None] = []
    for red, green, blue, alpha in decoded:
        if alpha == 0:
            values.append(None)
        else:
            values.append((red / 255.0, green / 255.0, blue / 255.0))
    return values


def validate_implicit_observation_channel_tile(tile: Mapping[str, Any]) -> None:
    if tile.get("schema") != IMPLICIT_OBSERVATION_CHANNEL_TILE_SCHEMA:
        raise ValueError("implicit observation channel tile schema mismatch")
    if tile.get("is_authority_state") is not False:
        raise ValueError("implicit observation channel tile must be non-authority")
    if not tile.get("channel"):
        raise ValueError("implicit observation channel tile requires channel")
    width, height = [int(value) for value in tile.get("tile_shape", [])]
    if width <= 0 or height <= 0:
        raise ValueError("implicit observation channel tile requires positive shape")
    encoding = str(tile.get("encoding", ""))
    if encoding not in {"u16_rle_base64", "rgb8_rle_base64"}:
        raise ValueError("unsupported implicit observation channel encoding")
    if encoding == "u16_rle_base64":
        _finite_pair(tile.get("range", []), name="range")
        _unrle_u16(str(tile.get("data", "")), width * height)
    else:
        _unrle_rgba(str(tile.get("data", "")), width * height)
    if not tile.get("source_ray_sample_record_id"):
        raise ValueError("implicit observation channel requires ray sample source")
    _assert_no_forbidden_keys(tile)


def summarize_depth_channel(values: Sequence[float | None]) -> dict[str, Any]:
    known = [float(value) for value in values if value is not None]
    return {
        "known_ratio": len(known) / max(1, len(values)),
        "min_depth": min(known) if known else None,
        "max_depth": max(known) if known else None,
        "mean_depth": sum(known) / len(known) if known else None,
    }


def summarize_scalar_channel(values: Sequence[float | None], *, name: str) -> dict[str, Any]:
    known = [float(value) for value in values if value is not None]
    return {
        f"mean_{name}": sum(known) / len(known) if known else 0.0,
        f"min_{name}": min(known) if known else 0.0,
        f"max_{name}": max(known) if known else 0.0,
        "known_ratio": len(known) / max(1, len(values)),
    }
