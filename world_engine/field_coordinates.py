from __future__ import annotations

import math
from typing import Any


def build_coordinate_frame(
    observer_window: dict[str, Any],
    grid_shape: tuple[int, int] | list[int] = (64, 64),
) -> dict[str, Any]:
    origin = list(observer_window.get("origin", [0.0, 0.0]))
    extent = list(observer_window.get("extent", [12.0, 9.0]))
    return {
        "world_origin": [float(origin[0]), float(origin[1])],
        "world_extent": [float(extent[0]), float(extent[1])],
        "grid_shape": [int(grid_shape[0]), int(grid_shape[1])],
        "world_to_grid": "affine_window_to_grid_v1",
        "grid_to_world": "affine_grid_to_window_v1",
        "source_observer_window": {
            "origin": [float(origin[0]), float(origin[1])],
            "extent": [float(extent[0]), float(extent[1])],
        },
    }


def world_to_grid(point: list[float], coordinate_frame: dict[str, Any]) -> list[float]:
    origin = coordinate_frame["world_origin"]
    extent = coordinate_frame["world_extent"]
    height, width = coordinate_frame["grid_shape"]
    gx = (float(point[0]) - origin[0]) / extent[0] * (width - 1)
    gy = (float(point[1]) - origin[1]) / extent[1] * (height - 1)
    return [gx, gy]


def grid_to_world(point: list[float], coordinate_frame: dict[str, Any]) -> list[float]:
    origin = coordinate_frame["world_origin"]
    extent = coordinate_frame["world_extent"]
    height, width = coordinate_frame["grid_shape"]
    x = origin[0] + float(point[0]) / (width - 1) * extent[0]
    y = origin[1] + float(point[1]) / (height - 1) * extent[1]
    return [x, y]


def image_to_world(
    image_xy: list[float],
    observer_window: dict[str, Any],
) -> list[float]:
    if len(image_xy) != 2:
        raise ValueError("image_xy must contain two normalized values")
    image_x = float(image_xy[0])
    image_y = float(image_xy[1])
    if not math.isfinite(image_x) or not math.isfinite(image_y):
        raise ValueError("image_xy must contain finite values")
    if image_x < 0.0 or image_x > 1.0 or image_y < 0.0 or image_y > 1.0:
        raise ValueError("image_xy must be inside [0.0, 1.0]")
    origin = observer_window.get("origin", [0.0, 0.0])
    extent = observer_window.get("extent", [1.0, 1.0])
    return [
        float(origin[0]) + image_x * float(extent[0]),
        float(origin[1]) + (1.0 - image_y) * float(extent[1]),
    ]


def image_vector_to_world(
    source_vector_image: list[float],
    observer_window: dict[str, Any],
) -> list[float]:
    if len(source_vector_image) != 2:
        raise ValueError("source_vector_image must contain two values")
    image_dx = float(source_vector_image[0])
    image_dy = float(source_vector_image[1])
    if not math.isfinite(image_dx) or not math.isfinite(image_dy):
        raise ValueError("source_vector_image must contain finite values")
    extent = observer_window.get("extent", [1.0, 1.0])
    return [
        image_dx * float(extent[0]),
        -image_dy * float(extent[1]),
    ]


def clamped_grid_region(
    center_grid: list[float],
    grid_shape: list[int] | tuple[int, int],
    radius_grid: int,
) -> tuple[list[int], bool]:
    if radius_grid <= 0:
        raise ValueError("radius_grid must be positive")
    height, width = int(grid_shape[0]), int(grid_shape[1])
    raw = [
        int(math.floor(float(center_grid[0]) - radius_grid)),
        int(math.floor(float(center_grid[1]) - radius_grid)),
        int(math.ceil(float(center_grid[0]) + radius_grid)),
        int(math.ceil(float(center_grid[1]) + radius_grid)),
    ]
    region = [
        max(0, raw[0]),
        max(0, raw[1]),
        min(width - 1, raw[2]),
        min(height - 1, raw[3]),
    ]
    return region, region != raw
