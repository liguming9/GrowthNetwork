#!/usr/bin/env python3
"""Convert GrowthNetwork's Blender JSON into a compact browser animation file.

The converter intentionally reads the existing exported geometry instead of
running the growth model again. This guarantees that pygame, Blender, and the
browser share the same fixed nodes, centrelines, branch hierarchy, and widths.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Sequence


PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_PATH = PROJECT_DIR / "growth_network_curves.json"
EXPORT_PATH = PROJECT_DIR / "export" / "web_network.json"
WEB_DATA_PATH = PROJECT_DIR / "web" / "data" / "web_network.json"

# Browser-only artwork presentation.  The geometry and node coordinates still
# come from the existing Blender export; these values only describe how the
# supplied organ images replace the former circular node markers.
ORGAN_SPECS: dict[str, dict[str, Any]] = {
    "Brain": {
        "image": "./assets/brain.png",
        "displayWidth": 138.0,
        "vesselOrigin": [0.50, 0.54],
        "vesselRoots": 7,
    },
    "Eye": {
        "image": "./assets/eye.png",
        "displayWidth": 124.0,
        "vesselOrigin": [0.50, 0.52],
        "vesselRoots": 6,
    },
    "Heart": {
        "image": "./assets/heart.png",
        "displayWidth": 104.0,
        "vesselOrigin": [0.51, 0.42],
        "vesselRoots": 8,
    },
    "Lung": {
        "image": "./assets/lung.png",
        "displayWidth": 148.0,
        "vesselOrigin": [0.50, 0.51],
        "vesselRoots": 8,
    },
}


class WebExportError(RuntimeError):
    """Raised when the existing Blender export cannot form a web dataset."""


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance(first: Sequence[float], second: Sequence[float]) -> float:
    return math.hypot(second[0] - first[0], second[1] - first[1])


def polyline_length(points: Sequence[Sequence[float]]) -> float:
    return sum(distance(first, second) for first, second in zip(points, points[1:]))


def artery_width_profile(fraction: float) -> float:
    """Mirror the flat artery profile used by PygameGrowthRenderer."""

    t = clamp(fraction, 0.0, 1.0)
    edge_distance = abs(2.0 * t - 1.0)
    smooth_edge = edge_distance * edge_distance * (3.0 - 2.0 * edge_distance)
    return 0.68 + smooth_edge * (0.34 + 0.03 * t)


def point_widths(curve_type: str, thickness: float, point_count: int) -> list[float]:
    """Reproduce the current renderer's main and dendrite tapering rules."""

    denominator = max(1, point_count - 1)
    widths: list[float] = []
    for index in range(point_count):
        fraction = index / denominator
        if curve_type == "artery":
            width = thickness * artery_width_profile(fraction)
        else:
            width_factor = max(0.10, (1.0 - fraction) ** 0.68)
            width = max(1.0, math.ceil(thickness * width_factor - 0.25))
        widths.append(round(width, 3))
    return widths


def attachment_progress(
    parent_points: Sequence[Sequence[float]],
    child_start: Sequence[float],
) -> float:
    """Return the distance fraction where a child touches its parent polyline."""

    if len(parent_points) < 2:
        return 1.0
    total = polyline_length(parent_points)
    if total <= 1e-9:
        return 1.0

    best_distance = math.inf
    best_along = total
    traversed = 0.0
    for first, second in zip(parent_points, parent_points[1:]):
        dx = second[0] - first[0]
        dy = second[1] - first[1]
        segment_length_squared = dx * dx + dy * dy
        segment_length = math.sqrt(segment_length_squared)
        if segment_length_squared <= 1e-12:
            continue
        projection = (
            (child_start[0] - first[0]) * dx
            + (child_start[1] - first[1]) * dy
        ) / segment_length_squared
        projection = clamp(projection, 0.0, 1.0)
        projected = (
            first[0] + dx * projection,
            first[1] + dy * projection,
        )
        separation = distance(projected, child_start)
        if separation < best_distance:
            best_distance = separation
            best_along = traversed + segment_length * projection
        traversed += segment_length
    return clamp(best_along / total, 0.0, 1.0)


def distance_to_polyline(
    points: Sequence[Sequence[float]],
    candidate: Sequence[float],
) -> float:
    """Return the shortest distance from a point to a polyline."""

    if len(points) < 2:
        return distance(points[0], candidate) if points else math.inf
    best = math.inf
    for first, second in zip(points, points[1:]):
        dx = second[0] - first[0]
        dy = second[1] - first[1]
        segment_length_squared = dx * dx + dy * dy
        if segment_length_squared <= 1e-12:
            best = min(best, distance(first, candidate))
            continue
        projection = clamp(
            (
                (candidate[0] - first[0]) * dx
                + (candidate[1] - first[1]) * dy
            ) / segment_length_squared,
            0.0,
            1.0,
        )
        projected = (
            first[0] + dx * projection,
            first[1] + dy * projection,
        )
        best = min(best, distance(projected, candidate))
    return best


def require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WebExportError(f"{name} must be a JSON object")
    return value


def require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise WebExportError(f"{name} must be a JSON array")
    return value


def load_source() -> dict[str, Any]:
    try:
        payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WebExportError(f"Blender JSON not found: {SOURCE_PATH}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise WebExportError(f"Cannot read Blender JSON: {exc}") from exc

    require_mapping(payload, "root")
    require_mapping(payload.get("canvas"), "canvas")
    graph = require_mapping(payload.get("graph"), "graph")
    require_list(graph.get("nodes"), "graph.nodes")
    require_list(payload.get("curves"), "curves")
    return payload


def simplify_branches(source: dict[str, Any]) -> list[dict[str, Any]]:
    simplified: list[dict[str, Any]] = []
    for item in source["curves"]:
        points = require_list(item.get("screen_points"), f"curve {item.get('id')} points")
        if len(points) < 2:
            continue
        curve_id = str(item["id"])
        curve_type = str(item["type"])
        thickness = float(item["thickness_pixels"])
        order = int(item.get("order", 0))
        metrics = require_mapping(item.get("metrics", {}), f"curve {curve_id} metrics")
        timing = require_mapping(item.get("timing", {}), f"curve {curve_id} timing")
        visitor_route = require_mapping(
            item.get("visitor_route", {}),
            f"curve {curve_id} visitor_route",
        )
        brightness = clamp(float(metrics.get("brightness", 1.0)), 0.0, 1.0)
        clean_points = [
            [round(float(point[0]), 3), round(float(point[1]), 3)]
            for point in points
        ]
        is_main = curve_type == "artery"
        forward_count = int(visitor_route.get("forward_traversal_count", 0))
        reverse_count = int(visitor_route.get("reverse_traversal_count", 0))
        traversal_events: list[dict[str, Any]] = []
        for event in require_list(
            timing.get("traversal_events", []),
            f"curve {curve_id} timing.traversal_events",
        ):
            event_data = require_mapping(event, f"curve {curve_id} traversal event")
            direction = str(event_data.get("direction", "forward"))
            traversal_events.append({
                "startTime": round(float(event_data.get("start_seconds", 0.0)), 4),
                "duration": round(
                    max(0.18, float(event_data.get("duration_seconds", 0.5))),
                    4,
                ),
                "direction": "reverse" if direction == "reverse" else "forward",
                "sourceNode": event_data.get("source"),
                "targetNode": event_data.get("target"),
                "visitorId": str(event_data.get("visitor_id", "")),
            })
        simplified.append({
            "id": curve_id,
            "parentId": item.get("parent_id") or None,
            "level": 0 if is_main else max(1, order - 2),
            "type": curve_type,
            "sourceNode": item.get("source"),
            "targetNode": item.get("target"),
            "forwardCount": forward_count if is_main else 0,
            "reverseCount": reverse_count if is_main else 0,
            "traversals": traversal_events if is_main else [],
            "width": round(thickness, 3),
            "widths": point_widths(curve_type, thickness, len(clean_points)),
            "opacity": round(
                0.92 + 0.08 * brightness
                if is_main
                else 0.46 + 0.44 * brightness,
                4,
            ),
            "birthTime": 0.0,
            "duration": round(
                max(0.18, float(timing.get("baseline_growth_duration_seconds", 0.5))),
                4,
            ),
            "attachmentProgress": None,
            "growthDirection": "root-to-tip",
            "length": round(polyline_length(clean_points), 3),
            "points": clean_points,
            "_sourceBirth": float(timing.get("start_seconds", 0.0)),
        })
    if not simplified:
        raise WebExportError("The Blender JSON contains no drawable curves")
    return simplified


def populate_traversal_events(
    source: dict[str, Any],
    branches: list[dict[str, Any]],
) -> None:
    """Backfill exact timed directions from the exported visitor routes.

    GrowthNetwork 2.3 exports visitor routes and the animation configuration in
    the Blender JSON. Replaying the same deterministic timing formula keeps the
    web export compatible with older JSON files that predate the explicit
    ``traversal_events`` field, without loading or changing any CSV schema.
    """

    mains = [branch for branch in branches if branch["level"] == 0]
    if not mains or all(branch["traversals"] for branch in mains):
        return
    graph = require_mapping(source.get("graph"), "graph")
    visitor_routes = require_list(graph.get("visitor_routes", []), "graph.visitor_routes")
    generation = require_mapping(source.get("generation", {}), "generation")
    config = require_mapping(generation.get("config", {}), "generation.config")
    trace_stage_delay = float(config.get("trace_stage_delay", 2.2))
    seconds_per_animation_second = max(
        0.001,
        float(config.get("visitor_seconds_per_animation_second", 18.0)),
    )
    duration_scale = float(config.get("main_route_duration_scale", 3.0))
    by_corridor = {
        tuple(sorted((str(branch["sourceNode"]), str(branch["targetNode"])))): branch
        for branch in mains
    }

    for route_index, route in enumerate(visitor_routes):
        route_data = require_mapping(route, f"graph.visitor_routes[{route_index}]")
        visitor_id = str(route_data.get("visitor_id", route_index + 1))
        events = require_list(
            route_data.get("events", []),
            f"graph.visitor_routes[{route_index}].events",
        )
        route_elapsed = 0.0
        for current, following in zip(events, events[1:]):
            current_data = require_mapping(current, "visitor route event")
            following_data = require_mapping(following, "visitor route event")
            source_node = str(current_data["artwork_id"])
            target_node = str(following_data["artwork_id"])
            corridor = tuple(sorted((source_node, target_node)))
            branch = by_corridor.get(corridor)
            if branch is None:
                continue
            dwell = (
                float(current_data["dwell_time"])
                + float(following_data["dwell_time"])
            ) / 2.0
            duration = max(
                1.0,
                dwell / seconds_per_animation_second * duration_scale,
            )
            start_time = (
                trace_stage_delay
                + 0.40
                + route_index * 0.32
                + route_elapsed
            )
            route_elapsed += duration * 0.64
            branch["traversals"].append({
                "startTime": round(start_time, 4),
                "duration": round(duration, 4),
                "direction": (
                    "forward"
                    if source_node == str(branch["sourceNode"])
                    else "reverse"
                ),
                "sourceNode": source_node,
                "targetNode": target_node,
                "visitorId": visitor_id,
            })

    for branch in mains:
        branch["traversals"].sort(
            key=lambda event: (
                event["startTime"],
                event["visitorId"],
                event["direction"],
            )
        )


def schedule_animation(
    branches: list[dict[str, Any]],
    source_nodes: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    by_id = {branch["id"]: branch for branch in branches}
    if len(by_id) != len(branches):
        raise WebExportError("Curve identifiers must be unique")

    # Defensive orientation pass: every dwell branch must store its connected
    # root as points[0]. This preserves root-to-tip growth even when a future
    # Blender export reverses a spline's point order.
    source_node_points = {
        str(node["id"]): require_list(
            node.get("screen_point"),
            f"node {node.get('id')} screen_point",
        )
        for node in source_nodes
    }
    for branch in sorted(branches, key=lambda item: (item["level"], item["id"])):
        if branch["level"] == 0:
            continue
        parent_id = branch["parentId"]
        if parent_id is not None and parent_id in by_id:
            root_geometry = by_id[parent_id]["points"]
        else:
            node_point = source_node_points.get(str(branch["sourceNode"]))
            root_geometry = [node_point] if node_point is not None else []
        if not root_geometry:
            continue
        first_distance = distance_to_polyline(root_geometry, branch["points"][0])
        last_distance = distance_to_polyline(root_geometry, branch["points"][-1])
        if last_distance + 1e-6 < first_distance:
            branch["points"].reverse()
            branch["widths"].reverse()

    mains = [branch for branch in branches if branch["level"] == 0]
    if not mains:
        raise WebExportError("At least one artery is required")
    traversal_starts = [
        event["startTime"]
        for branch in mains
        for event in branch["traversals"]
    ]
    # The first real visitor movement defines zero. Later visitor routes retain
    # their data-derived spacing, so the collective artery accumulates over time
    # instead of appearing as one simultaneous reveal.
    main_offset = (
        min(traversal_starts)
        if traversal_starts
        else min(branch["_sourceBirth"] for branch in mains)
    )
    for branch in mains:
        for event in branch["traversals"]:
            event["startTime"] = round(
                max(0.0, event["startTime"] - main_offset),
                4,
            )
        if branch["traversals"]:
            branch["birthTime"] = min(
                event["startTime"] for event in branch["traversals"]
            )
        else:
            branch["birthTime"] = round(
                max(0.0, branch["_sourceBirth"] - main_offset),
                4,
            )

    node_birth = {str(node["id"]): math.inf for node in source_nodes}
    node_connections: dict[str, list[str]] = {node_id: [] for node_id in node_birth}
    for main in mains:
        source_id = str(main["sourceNode"])
        target_id = str(main["targetNode"])
        node_connections[source_id].append(main["id"])
        node_connections[target_id].append(main["id"])
        if main["traversals"]:
            for event in main["traversals"]:
                event_source = str(event["sourceNode"])
                event_target = str(event["targetNode"])
                if event_source in node_birth:
                    node_birth[event_source] = min(
                        node_birth[event_source], event["startTime"]
                    )
                if event_target in node_birth:
                    node_birth[event_target] = min(
                        node_birth[event_target],
                        event["startTime"] + event["duration"],
                    )
        else:
            if source_id in node_birth:
                node_birth[source_id] = min(node_birth[source_id], main["birthTime"])
            if target_id in node_birth:
                node_birth[target_id] = min(
                    node_birth[target_id],
                    main["birthTime"] + main["duration"],
                )

    for branch in sorted(branches, key=lambda item: (item["level"], item["id"])):
        if branch["level"] == 0:
            continue
        parent_id = branch["parentId"]
        if parent_id is not None:
            parent = by_id.get(parent_id)
            if parent is None:
                raise WebExportError(f"Curve {branch['id']} has missing parent {parent_id}")
            progress = attachment_progress(parent["points"], branch["points"][0])
            branch["attachmentProgress"] = round(progress, 6)
            if parent["level"] == 0 and parent["traversals"]:
                arrival_times = [
                    event["startTime"]
                    + event["duration"]
                    * (progress if event["direction"] == "forward" else 1.0 - progress)
                    for event in parent["traversals"]
                ]
                required_birth = min(arrival_times) + 0.04 * branch["level"]
            else:
                required_birth = (
                    parent["birthTime"]
                    + parent["duration"] * progress
                    + 0.04 * branch["level"]
                )
        else:
            node_time = node_birth.get(str(branch["sourceNode"]), 0.0)
            if not math.isfinite(node_time):
                node_time = 0.0
            required_birth = max(1.2, node_time + 0.16)
        branch["birthTime"] = round(
            max(branch["_sourceBirth"] - main_offset, required_birth),
            4,
        )

    visit_values = [float(item.get("visit_count", 0.0)) for item in source_nodes]
    dwell_values = [float(item.get("average_dwell", 0.0)) for item in source_nodes]
    deep_values = [float(item.get("deep_visit_count", 0.0)) for item in source_nodes]

    def normalized(value: float, values: Sequence[float]) -> float:
        low = min(values, default=0.0)
        high = max(values, default=0.0)
        if high - low <= 1e-9:
            return 0.5
        return clamp((value - low) / (high - low), 0.0, 1.0)

    nodes: list[dict[str, Any]] = []
    for item in source_nodes:
        screen_point = require_list(item.get("screen_point"), f"node {item.get('id')}")
        node_id = str(item["id"])
        birth_time = node_birth[node_id]
        if not math.isfinite(birth_time):
            birth_time = 0.0
        organ = ORGAN_SPECS.get(node_id)
        if organ is None:
            raise WebExportError(f"No browser organ image is configured for {node_id}")
        visit_count = float(item.get("visit_count", 0.0))
        average_dwell = float(item.get("average_dwell", 0.0))
        deep_visit_count = float(item.get("deep_visit_count", 0.0))
        data_density = (
            0.2 * normalized(visit_count, visit_values)
            + 0.6 * normalized(average_dwell, dwell_values)
            + 0.2 * normalized(deep_visit_count, deep_values)
        )
        organ_data = dict(organ)
        # A non-zero base keeps every anatomical image legible, while the
        # dissertation's 20/60/20 engagement weighting controls extra growth.
        organ_data["vesselDensity"] = round(0.76 + 0.42 * data_density, 4)
        organ_data["vesselDepth"] = 3 if deep_visit_count < max(deep_values) else 4

        nodes.append({
            "id": node_id,
            "x": round(float(screen_point[0]), 3),
            "y": round(float(screen_point[1]), 3),
            "radius": round(float(item.get("marker_radius_pixels", 5.0)), 3),
            "brightness": round(float(item.get("brightness", 1.0)), 6),
            "birthTime": round(birth_time, 4),
            "connectedMainBranchIds": sorted(set(node_connections[node_id])),
            "imageVisibleFrom": 0.0,
            "visitCount": round(visit_count, 3),
            "averageDwell": round(average_dwell, 3),
            "deepVisitCount": round(deep_visit_count, 3),
            "organ": organ_data,
        })

    growth_end = max(
        branch["birthTime"] + branch["duration"] for branch in branches
    )
    growth_end = max(
        growth_end,
        max(
            (
                event["startTime"] + event["duration"]
                for branch in mains
                for event in branch["traversals"]
            ),
            default=0.0,
        ),
    )
    for branch in branches:
        branch.pop("_sourceBirth", None)
    branches.sort(key=lambda item: (item["level"], item["birthTime"], item["id"]))
    return nodes, branches, round(growth_end, 4)


def build_web_payload(source: dict[str, Any]) -> dict[str, Any]:
    graph = require_mapping(source["graph"], "graph")
    source_nodes = require_list(graph["nodes"], "graph.nodes")
    branches = simplify_branches(source)
    populate_traversal_events(source, branches)
    nodes, branches, growth_end = schedule_animation(branches, source_nodes)
    source_metadata = source.get("source", {})
    row_counts = (
        source_metadata.get("row_counts", {})
        if isinstance(source_metadata, dict)
        else {}
    )
    visitor_count = max(
        (int(float(node.get("visit_count", 0))) for node in source_nodes),
        default=0,
    )
    return {
        "format": "GrowthNetwork Web Canvas",
        "formatVersion": "1.2",
        "applicationVersion": source.get("application_version"),
        "source": "growth_network_curves.json",
        "canvas": {
            "width": int(source["canvas"]["width"]),
            "height": int(source["canvas"]["height"]),
        },
        "summary": {
            "visitorCount": visitor_count,
            "visitorEvents": int(row_counts.get("visitor_events", 0)),
            "mainRoutes": sum(1 for branch in branches if branch["level"] == 0),
            "branchCount": len(branches),
        },
        "style": {
            "background": "#fbfaf7",
            "mainStroke": "#e92b1f",
            "branchStroke": "#c51d16",
            "nodeStroke": "#f23829",
            "organMainStroke": "#2157a6",
            "organBranchStroke": "#4f79c7",
            "labelStroke": "#111111",
        },
        "timeline": {
            "growthDuration": growth_end,
            "unit": "seconds",
            "deterministic": True,
        },
        "nodes": nodes,
        "branches": branches,
    }


def main() -> int:
    try:
        payload = build_web_payload(load_source())
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        for path in (EXPORT_PATH, WEB_DATA_PATH):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded, encoding="utf-8", newline="\n")
    except (OSError, KeyError, TypeError, ValueError, WebExportError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        "Web export: "
        f"{len(payload['nodes'])} nodes, {len(payload['branches'])} branches, "
        f"{payload['timeline']['growthDuration']:.2f}s"
    )
    print(f"Canonical JSON: {EXPORT_PATH}")
    print(f"Browser JSON:   {WEB_DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
