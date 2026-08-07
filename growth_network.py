#!/usr/bin/env python3
"""GrowthNetwork: a visitor-generated museum capillary visualisation.

The program validates six linked CSV datasets and constructs a directed
NetworkX analysis graph. Movements between the same artwork pair reinforce one
organic centreline, while dwell and visit metrics generate local recursive
capillary trees. pygame renders the result as a glowing, evolving projection
and the final curves are exported to JSON for Blender.

The implementation deliberately keeps the complete application in one source
file.  Its classes separate data ingestion, graph construction, generative
geometry, rendering, and export so that each dissertation method can be
described, tested, and modified independently.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


APP_NAME = "GrowthNetwork"
APP_VERSION = "2.3.4"
DEEP_VISIT_THRESHOLD_SECONDS = 30.0
Vec2 = tuple[float, float]

# Kept in the exported schema for backward compatibility. All exhibits share
# one scalar because hue is deliberately fixed to the installation's restrained
# capillary-red palette; data remains encoded through width, luminance, density,
# and branching complexity.
MONOCHROME_COLOUR_BIAS = 0.5


class DataValidationError(Exception):
    """Raised after collecting all actionable CSV validation errors."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = list(issues)
        message = "Dataset validation failed:\n  - " + "\n  - ".join(self.issues)
        super().__init__(message)


class DependencyError(RuntimeError):
    """Raised when a required runtime package is unavailable."""


@dataclass(frozen=True, slots=True)
class ArtworkRecord:
    artwork_id: int
    name: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class NodeRecord:
    node_id: str
    x: float
    y: float
    visit_count: int
    average_dwell: float
    deep_visit_count: int


@dataclass(frozen=True, slots=True)
class EdgeRecord:
    source: str
    target: str
    weight: float
    average_dwell: float
    deep_visit_count: int


@dataclass(frozen=True, slots=True)
class VisitorRecord:
    visitor_id: str
    artwork_id: str
    order: int
    dwell_time: float


@dataclass(frozen=True, slots=True)
class RelationshipRecord:
    source: str
    target: str
    count: int
    average_dwell: float
    thickness: float
    density: float


@dataclass(frozen=True, slots=True)
class NetworkRecord:
    source: str
    target: str
    count: int
    average_dwell: float
    thickness: float
    density: float
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(slots=True)
class DatasetBundle:
    """Validated, typed representation of all six input datasets."""

    data_dir: Path
    artworks: list[ArtworkRecord]
    nodes: list[NodeRecord]
    edges: list[EdgeRecord]
    visitors: list[VisitorRecord]
    relationships: list[RelationshipRecord]
    network: list[NetworkRecord]

    def summary(self) -> dict[str, int]:
        return {
            "artworks": len(self.artworks),
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "visitor_events": len(self.visitors),
            "relationships": len(self.relationships),
            "network_segments": len(self.network),
        }


class DatasetLoader:
    """Load the CSV files and validate both schemas and relationships.

    Validation is intentionally strict.  Generative mappings are sensitive to
    accidental negative counts, duplicate edges, non-finite numbers, and
    broken identifiers; silently accepting any of those would make the visual
    output difficult to defend methodologically.
    """

    FILE_SCHEMAS: dict[str, tuple[str, ...]] = {
        "artwork.csv": ("ID", "Name", "X", "Y"),
        "nodes.csv": ("ID", "X", "Y", "VisitCount", "AverageDwell", "DeepVisitCount"),
        "edges.csv": ("Source", "Target", "Weight", "AverageDwell", "DeepVisitCount"),
        "visitor.csv": ("VisitorID", "ArtworkID", "Order", "DwellTime"),
        "relationship.csv": ("Source", "Target", "Count", "AvgDwell", "Thickness", "Density"),
        "network.csv": (
            "Source", "Target", "Count", "AvgDwell", "Thickness", "Density",
            "X1", "Y1", "X2", "Y2",
        ),
    }

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir.expanduser().resolve()
        self.issues: list[str] = []

    def load(self) -> DatasetBundle:
        raw = {
            filename: self._read_csv(filename, columns)
            for filename, columns in self.FILE_SCHEMAS.items()
        }

        artworks = self._parse_artworks(raw["artwork.csv"])
        nodes = self._parse_nodes(raw["nodes.csv"])
        edges = self._parse_edges(raw["edges.csv"])
        visitors = self._parse_visitors(raw["visitor.csv"])
        relationships = self._parse_relationships(raw["relationship.csv"])
        network = self._parse_network(raw["network.csv"])

        self._validate_links(artworks, nodes, edges, visitors, relationships, network)
        if self.issues:
            raise DataValidationError(self.issues)

        return DatasetBundle(
            data_dir=self.data_dir,
            artworks=artworks,
            nodes=nodes,
            edges=edges,
            visitors=visitors,
            relationships=relationships,
            network=network,
        )

    def _read_csv(self, filename: str, required: Sequence[str]) -> list[tuple[int, dict[str, str]]]:
        path = self.data_dir / filename
        if not path.is_file():
            self.issues.append(f"{filename}: file not found at {path}")
            return []

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                headers = reader.fieldnames or []
                if len(headers) != len(set(headers)):
                    self.issues.append(f"{filename}: duplicate column names are not allowed")
                missing = [column for column in required if column not in headers]
                if missing:
                    self.issues.append(f"{filename}: missing required columns {missing}")
                    return []

                rows: list[tuple[int, dict[str, str]]] = []
                for line_number, row in enumerate(reader, start=2):
                    if None in row:
                        self.issues.append(f"{filename}:{line_number}: too many comma-separated values")
                        continue
                    clean = {key: (value or "").strip() for key, value in row.items()}
                    if not any(clean.values()):
                        continue
                    rows.append((line_number, clean))
        except (OSError, UnicodeError, csv.Error) as exc:
            self.issues.append(f"{filename}: could not be read: {exc}")
            return []

        if not rows:
            self.issues.append(f"{filename}: contains no data rows")
        return rows

    def _text(self, value: str, field_name: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError(f"{field_name} must not be empty")
        return text

    def _integer(self, value: str, field_name: str, minimum: int = 0) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an integer, got {value!r}") from exc
        if number < minimum:
            raise ValueError(f"{field_name} must be >= {minimum}, got {number}")
        return number

    def _number(self, value: str, field_name: str, minimum: float | None = None) -> float:
        try:
            number = float(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be numeric, got {value!r}") from exc
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite")
        if minimum is not None and number < minimum:
            raise ValueError(f"{field_name} must be >= {minimum}, got {number}")
        return number

    def _parse(self, filename: str, rows: list[tuple[int, dict[str, str]]], factory: Any) -> list[Any]:
        records: list[Any] = []
        for line_number, row in rows:
            try:
                records.append(factory(row))
            except (KeyError, ValueError) as exc:
                self.issues.append(f"{filename}:{line_number}: {exc}")
        return records

    def _parse_artworks(self, rows: list[tuple[int, dict[str, str]]]) -> list[ArtworkRecord]:
        return self._parse(
            "artwork.csv", rows,
            lambda row: ArtworkRecord(
                self._integer(row["ID"], "ID", 1),
                self._text(row["Name"], "Name"),
                self._number(row["X"], "X"),
                self._number(row["Y"], "Y"),
            ),
        )

    def _parse_nodes(self, rows: list[tuple[int, dict[str, str]]]) -> list[NodeRecord]:
        return self._parse(
            "nodes.csv", rows,
            lambda row: NodeRecord(
                self._text(row["ID"], "ID"),
                self._number(row["X"], "X"),
                self._number(row["Y"], "Y"),
                self._integer(row["VisitCount"], "VisitCount"),
                self._number(row["AverageDwell"], "AverageDwell", 0.0),
                self._integer(row["DeepVisitCount"], "DeepVisitCount"),
            ),
        )

    def _parse_edges(self, rows: list[tuple[int, dict[str, str]]]) -> list[EdgeRecord]:
        return self._parse(
            "edges.csv", rows,
            lambda row: EdgeRecord(
                self._text(row["Source"], "Source"),
                self._text(row["Target"], "Target"),
                self._number(row["Weight"], "Weight", 0.0),
                self._number(row["AverageDwell"], "AverageDwell", 0.0),
                self._integer(row["DeepVisitCount"], "DeepVisitCount"),
            ),
        )

    def _parse_visitors(self, rows: list[tuple[int, dict[str, str]]]) -> list[VisitorRecord]:
        return self._parse(
            "visitor.csv", rows,
            lambda row: VisitorRecord(
                self._text(row["VisitorID"], "VisitorID"),
                self._text(row["ArtworkID"], "ArtworkID"),
                self._integer(row["Order"], "Order", 1),
                self._number(row["DwellTime"], "DwellTime", 0.0),
            ),
        )

    def _parse_relationships(
        self, rows: list[tuple[int, dict[str, str]]]
    ) -> list[RelationshipRecord]:
        return self._parse(
            "relationship.csv", rows,
            lambda row: RelationshipRecord(
                self._text(row["Source"], "Source"),
                self._text(row["Target"], "Target"),
                self._integer(row["Count"], "Count"),
                self._number(row["AvgDwell"], "AvgDwell", 0.0),
                self._number(row["Thickness"], "Thickness", 0.0),
                self._number(row["Density"], "Density", 0.0),
            ),
        )

    def _parse_network(self, rows: list[tuple[int, dict[str, str]]]) -> list[NetworkRecord]:
        return self._parse(
            "network.csv", rows,
            lambda row: NetworkRecord(
                self._text(row["Source"], "Source"),
                self._text(row["Target"], "Target"),
                self._integer(row["Count"], "Count"),
                self._number(row["AvgDwell"], "AvgDwell", 0.0),
                self._number(row["Thickness"], "Thickness", 0.0),
                self._number(row["Density"], "Density", 0.0),
                self._number(row["X1"], "X1"),
                self._number(row["Y1"], "Y1"),
                self._number(row["X2"], "X2"),
                self._number(row["Y2"], "Y2"),
            ),
        )

    def _duplicates(self, values: Iterable[Any]) -> list[Any]:
        counts = Counter(values)
        return sorted(value for value, count in counts.items() if count > 1)

    def _validate_links(
        self,
        artworks: list[ArtworkRecord],
        nodes: list[NodeRecord],
        edges: list[EdgeRecord],
        visitors: list[VisitorRecord],
        relationships: list[RelationshipRecord],
        network: list[NetworkRecord],
    ) -> None:
        duplicate_art_ids = self._duplicates(a.artwork_id for a in artworks)
        duplicate_art_names = self._duplicates(a.name for a in artworks)
        duplicate_nodes = self._duplicates(n.node_id for n in nodes)
        duplicate_edges = self._duplicates((e.source, e.target) for e in edges)
        duplicate_relationships = self._duplicates((r.source, r.target) for r in relationships)
        duplicate_network = self._duplicates((n.source, n.target) for n in network)
        for label, duplicates in (
            ("artwork.csv ID", duplicate_art_ids),
            ("artwork.csv Name", duplicate_art_names),
            ("nodes.csv ID", duplicate_nodes),
            ("edges.csv Source/Target", duplicate_edges),
            ("relationship.csv Source/Target", duplicate_relationships),
            ("network.csv Source/Target", duplicate_network),
        ):
            if duplicates:
                self.issues.append(f"{label}: duplicate keys {duplicates}")

        artwork_by_name = {record.name: record for record in artworks}
        node_ids = {record.node_id for record in nodes}
        edge_keys = {(record.source, record.target) for record in edges}

        missing_artworks = sorted(node_ids - set(artwork_by_name))
        orphan_artworks = sorted(set(artwork_by_name) - node_ids)
        if missing_artworks:
            self.issues.append(f"artwork.csv: missing rows for node names {missing_artworks}")
        if orphan_artworks:
            self.issues.append(f"artwork.csv: artwork names have no matching node {orphan_artworks}")

        for edge in edges:
            for role, identifier in (("Source", edge.source), ("Target", edge.target)):
                if identifier not in node_ids:
                    self.issues.append(f"edges.csv: {role} {identifier!r} does not exist in nodes.csv")
            if edge.source == edge.target:
                self.issues.append(f"edges.csv: self-loop {edge.source!r} -> {edge.target!r} is unsupported")

        event_keys = [(event.visitor_id, event.order) for event in visitors]
        duplicate_events = self._duplicates(event_keys)
        if duplicate_events:
            self.issues.append(f"visitor.csv: duplicate VisitorID/Order keys {duplicate_events}")

        events_by_visitor: dict[str, list[VisitorRecord]] = defaultdict(list)
        for event in visitors:
            events_by_visitor[event.visitor_id].append(event)
            if event.artwork_id not in node_ids:
                self.issues.append(
                    f"visitor.csv: ArtworkID {event.artwork_id!r} does not exist in nodes.csv"
                )
        for visitor_id, events in events_by_visitor.items():
            orders = sorted(event.order for event in events)
            expected = list(range(1, len(orders) + 1))
            if orders != expected:
                self.issues.append(
                    f"visitor.csv: visitor {visitor_id!r} orders must be contiguous from 1; got {orders}"
                )
            for first, second in zip(sorted(events, key=lambda event: event.order),
                                     sorted(events, key=lambda event: event.order)[1:]):
                transition = (first.artwork_id, second.artwork_id)
                reverse_transition = (second.artwork_id, first.artwork_id)
                if transition not in edge_keys and reverse_transition not in edge_keys:
                    self.issues.append(
                        f"visitor.csv: corridor {transition[0]!r} -- {transition[1]!r} "
                        "does not exist in either direction in edges.csv"
                    )

        self._validate_visitor_aggregates(
            nodes, edges, relationships, network, events_by_visitor
        )

        for label, records in (("relationship.csv", relationships), ("network.csv", network)):
            for record in records:
                key = (record.source, record.target)
                if key not in edge_keys:
                    self.issues.append(
                        f"{label}: edge {record.source!r} -> {record.target!r} "
                        "does not exist in edges.csv"
                    )

        # network.csv uses the artwork-layout coordinates.  Checking those
        # coordinates catches reversed or incorrectly joined segments without
        # forcing artwork.csv and nodes.csv to share the same layout system.
        tolerance = 1e-6
        for segment in network:
            source = artwork_by_name.get(segment.source)
            target = artwork_by_name.get(segment.target)
            if source and (abs(segment.x1 - source.x) > tolerance or abs(segment.y1 - source.y) > tolerance):
                self.issues.append(
                    f"network.csv: ({segment.x1}, {segment.y1}) does not match "
                    f"artwork.csv coordinates for {segment.source!r}"
                )
            if target and (abs(segment.x2 - target.x) > tolerance or abs(segment.y2 - target.y) > tolerance):
                self.issues.append(
                    f"network.csv: ({segment.x2}, {segment.y2}) does not match "
                    f"artwork.csv coordinates for {segment.target!r}"
                )

    def _validate_visitor_aggregates(
        self,
        nodes: list[NodeRecord],
        edges: list[EdgeRecord],
        relationships: list[RelationshipRecord],
        network: list[NetworkRecord],
        events_by_visitor: dict[str, list[VisitorRecord]],
    ) -> None:
        """Reconcile every summary table against visitor-level evidence.

        DeepVisitCount uses the documented threshold of 30 seconds.  Numeric
        tolerances allow the CSV summaries to be rounded to two or three decimal
        places without hiding meaningful inconsistencies.
        """

        all_events = [event for events in events_by_visitor.values() for event in events]
        if not all_events:
            return

        events_by_artwork: dict[str, list[VisitorRecord]] = defaultdict(list)
        for event in all_events:
            events_by_artwork[event.artwork_id].append(event)

        for node in nodes:
            events = events_by_artwork.get(node.node_id, [])
            if not events:
                continue
            expected_count = len(events)
            expected_average = sum(event.dwell_time for event in events) / expected_count
            expected_deep = sum(
                event.dwell_time >= DEEP_VISIT_THRESHOLD_SECONDS for event in events
            )
            if node.visit_count != expected_count:
                self.issues.append(
                    f"nodes.csv: {node.node_id!r} VisitCount={node.visit_count}, "
                    f"but visitor.csv contains {expected_count} visits"
                )
            if not math.isclose(node.average_dwell, expected_average, abs_tol=0.011):
                self.issues.append(
                    f"nodes.csv: {node.node_id!r} AverageDwell={node.average_dwell}, "
                    f"expected {expected_average:.2f} from visitor.csv"
                )
            if node.deep_visit_count != expected_deep:
                self.issues.append(
                    f"nodes.csv: {node.node_id!r} DeepVisitCount={node.deep_visit_count}, "
                    f"expected {expected_deep} visits >= {DEEP_VISIT_THRESHOLD_SECONDS:g}s"
                )

        transition_groups: dict[tuple[str, str], list[tuple[VisitorRecord, VisitorRecord]]] = (
            defaultdict(list)
        )
        for events in events_by_visitor.values():
            ordered = sorted(events, key=lambda event: event.order)
            for current, following in zip(ordered, ordered[1:]):
                transition_groups[(current.artwork_id, following.artwork_id)].append(
                    (current, following)
                )

        edge_map = {(row.source, row.target): row for row in edges}
        relationship_map = {(row.source, row.target): row for row in relationships}
        network_map = {(row.source, row.target): row for row in network}
        observed_keys = set(transition_groups)
        for label, summary_map in (
            ("edges.csv", edge_map),
            ("relationship.csv", relationship_map),
            ("network.csv", network_map),
        ):
            missing = sorted(observed_keys - set(summary_map))
            if missing:
                self.issues.append(f"{label}: missing observed visitor transitions {missing}")

        if not transition_groups:
            return
        maximum_count = max(len(rows) for rows in transition_groups.values())
        for key, rows in transition_groups.items():
            expected_count = len(rows)
            expected_target_dwell = sum(second.dwell_time for _, second in rows) / expected_count
            expected_segment_dwell = sum(
                (first.dwell_time + second.dwell_time) / 2.0 for first, second in rows
            ) / expected_count
            expected_deep = sum(
                second.dwell_time >= DEEP_VISIT_THRESHOLD_SECONDS for _, second in rows
            )
            expected_thickness = expected_segment_dwell / 50.0
            expected_density = expected_count / maximum_count

            edge = edge_map.get(key)
            if edge:
                if not math.isclose(edge.weight, expected_count, abs_tol=1e-9):
                    self.issues.append(
                        f"edges.csv: {key} Weight={edge.weight}, expected {expected_count}"
                    )
                if not math.isclose(edge.average_dwell, expected_target_dwell, abs_tol=0.011):
                    self.issues.append(
                        f"edges.csv: {key} AverageDwell={edge.average_dwell}, "
                        f"expected {expected_target_dwell:.2f} target dwell"
                    )
                if edge.deep_visit_count != expected_deep:
                    self.issues.append(
                        f"edges.csv: {key} DeepVisitCount={edge.deep_visit_count}, "
                        f"expected {expected_deep}"
                    )

            for label, summary in (
                ("relationship.csv", relationship_map.get(key)),
                ("network.csv", network_map.get(key)),
            ):
                if summary is None:
                    continue
                if summary.count != expected_count:
                    self.issues.append(
                        f"{label}: {key} Count={summary.count}, expected {expected_count}"
                    )
                if not math.isclose(summary.average_dwell, expected_segment_dwell, abs_tol=0.011):
                    self.issues.append(
                        f"{label}: {key} AvgDwell={summary.average_dwell}, "
                        f"expected {expected_segment_dwell:.2f}"
                    )
                if not math.isclose(summary.thickness, expected_thickness, abs_tol=0.0011):
                    self.issues.append(
                        f"{label}: {key} Thickness={summary.thickness}, "
                        f"expected {expected_thickness:.3f}"
                    )
                if not math.isclose(summary.density, expected_density, abs_tol=0.0011):
                    self.issues.append(
                        f"{label}: {key} Density={summary.density}, "
                        f"expected {expected_density:.3f}"
                    )


class FlowGraphBuilder:
    """Construct and enrich the directed graph used by the generator."""

    def build(self, data: DatasetBundle) -> Any:
        try:
            import networkx as nx
        except ImportError as exc:
            raise DependencyError(
                "NetworkX is required. Install dependencies with: "
                "python -m pip install -r requirements.txt"
            ) from exc

        graph = nx.DiGraph(name=APP_NAME)
        for node in data.nodes:
            graph.add_node(
                node.node_id,
                x=node.x,
                y=node.y,
                visit_count=node.visit_count,
                average_dwell=node.average_dwell,
                deep_visit_count=node.deep_visit_count,
            )

        relationship_map = {(row.source, row.target): row for row in data.relationships}
        network_map = {(row.source, row.target): row for row in data.network}
        for edge in data.edges:
            relationship = relationship_map.get((edge.source, edge.target))
            network = network_map.get((edge.source, edge.target))
            graph.add_edge(
                edge.source,
                edge.target,
                weight=edge.weight,
                average_dwell=edge.average_dwell,
                deep_visit_count=edge.deep_visit_count,
                relationship_count=relationship.count if relationship else 0,
                relationship_thickness=relationship.thickness if relationship else 0.0,
                relationship_density=relationship.density if relationship else 0.0,
                network_count=network.count if network else 0,
                network_average_dwell=network.average_dwell if network else None,
            )

        events_by_visitor: dict[str, list[VisitorRecord]] = defaultdict(list)
        for event in data.visitors:
            events_by_visitor[event.visitor_id].append(event)

        transition_count: Counter[tuple[str, str]] = Counter()
        transition_dwell: dict[tuple[str, str], list[float]] = defaultdict(list)
        entry_count: Counter[str] = Counter()
        visitor_paths: dict[str, list[str]] = {}
        visitor_routes: list[dict[str, Any]] = []
        for visitor_id, events in events_by_visitor.items():
            ordered = sorted(events, key=lambda event: event.order)
            visitor_paths[visitor_id] = [event.artwork_id for event in ordered]
            visitor_routes.append({
                "visitor_id": visitor_id,
                "events": [
                    {
                        "artwork_id": event.artwork_id,
                        "order": event.order,
                        "dwell_time": event.dwell_time,
                    }
                    for event in ordered
                ],
            })
            if ordered:
                entry_count[ordered[0].artwork_id] += 1
            for current, following in zip(ordered, ordered[1:]):
                key = (current.artwork_id, following.artwork_id)
                transition_count[key] += 1
                transition_dwell[key].append(following.dwell_time)

        for source, target, attributes in graph.edges(data=True):
            key = (source, target)
            observed = transition_count[key]
            values = transition_dwell.get(key, [])
            attributes["observed_transition_count"] = observed
            attributes["visitor_average_target_dwell"] = (
                sum(values) / len(values) if values else None
            )
            attributes["observed_corridor_count"] = (
                transition_count[(source, target)] + transition_count[(target, source)]
            )

        # Direction is retained in the analytical DiGraph and ordered visitor
        # routes. The visual layer uses undirected corridors so return journeys
        # reinforce one centreline instead of duplicating the geometry.
        flow_edges = sorted(transition_count)
        graph.graph["visitor_flow_edges"] = flow_edges
        graph.graph["visitor_corridors"] = sorted({tuple(sorted(edge)) for edge in flow_edges})
        graph.graph["entry_count"] = dict(entry_count)
        graph.graph["visitor_paths"] = visitor_paths
        graph.graph["visitor_routes"] = sorted(
            visitor_routes,
            key=lambda route: (
                not str(route["visitor_id"]).isdigit(),
                int(route["visitor_id"])
                if str(route["visitor_id"]).isdigit()
                else str(route["visitor_id"]),
            ),
        )
        graph.graph["dataset_summary"] = data.summary()
        return graph


@dataclass(slots=True)
class GrowthConfig:
    width: int = 1280
    height: int = 720
    margin: int = 90
    fps: int = 30
    seed: int = 42
    noise_frequency: float = 2.2
    attraction_strength: float = 0.56
    curvature_strength: float = 0.11
    capillary_density: float = 1.00
    trail_decay_seconds: float = 24.0
    memory_floor: float = 0.24
    trace_stage_delay: float = 2.2
    dendrite_density: float = 1.55
    dendrite_length_scale: float = 0.90
    dendrite_refresh_fps: float = 6.0
    local_density_cell_size: float = 44.0
    local_density_strength: float = 0.85
    visitor_seconds_per_animation_second: float = 18.0
    main_route_duration_scale: float = 3.0
    artery_min_thickness: float = 3.0
    artery_max_thickness: float = 12.5
    min_node_radius: float = 4.5
    max_node_radius: float = 8.5
    pixels_per_blender_unit: float = 50.0

    def validate(self) -> None:
        issues: list[str] = []
        if self.width < 320 or self.height < 240:
            issues.append("canvas must be at least 320 x 240")
        if self.margin < 0 or self.margin * 2 >= min(self.width, self.height):
            issues.append("margin must fit inside the canvas")
        if self.fps < 1:
            issues.append("fps must be at least 1")
        if self.min_node_radius <= 0 or self.max_node_radius < self.min_node_radius:
            issues.append("node radius bounds are invalid")
        if self.visitor_seconds_per_animation_second <= 0:
            issues.append("visitor time scale must be positive")
        if self.main_route_duration_scale <= 0:
            issues.append("main route duration scale must be positive")
        if not 0.0 <= self.attraction_strength <= 1.0:
            issues.append("attraction strength must be between 0 and 1")
        if not 0.01 <= self.curvature_strength <= 0.5:
            issues.append("curvature strength must be between 0.01 and 0.5")
        if not 0.5 <= self.capillary_density <= 2.0:
            issues.append("capillary density must be between 0.5 and 2.0")
        if self.trail_decay_seconds <= 0:
            issues.append("trail decay must be positive")
        if not 0.0 <= self.memory_floor <= 1.0:
            issues.append("memory floor must be between 0 and 1")
        if self.trace_stage_delay < 0:
            issues.append("trace stage delay cannot be negative")
        if not 0.25 <= self.dendrite_density <= 2.0:
            issues.append("dendrite density must be between 0.25 and 2.0")
        if not 0.4 <= self.dendrite_length_scale <= 1.8:
            issues.append("dendrite length scale must be between 0.4 and 1.8")
        if self.dendrite_refresh_fps <= 0:
            issues.append("dendrite refresh rate must be positive")
        if self.local_density_cell_size <= 0:
            issues.append("local density cell size must be positive")
        if not 0.0 <= self.local_density_strength <= 2.0:
            issues.append("local density strength must be between 0 and 2")
        if (
            self.artery_min_thickness <= 0
            or self.artery_max_thickness <= self.artery_min_thickness
        ):
            issues.append("artery thickness bounds are invalid")
        if self.pixels_per_blender_unit <= 0:
            issues.append("pixels per Blender unit must be positive")
        if issues:
            raise ValueError("Configuration error: " + "; ".join(issues))


class PerlinNoise2D:
    """Seeded implementation of Ken Perlin's improved gradient noise.

    Keeping the noise implementation local avoids platform-specific compiled
    packages and makes the curvature method exactly reproducible from the JSON
    seed, an important property for dissertation evaluation.
    """

    def __init__(self, seed: int) -> None:
        permutation = list(range(256))
        random.Random(seed).shuffle(permutation)
        self.permutation = permutation * 2

    @staticmethod
    def _fade(value: float) -> float:
        return value * value * value * (value * (value * 6.0 - 15.0) + 10.0)

    @staticmethod
    def _lerp(left: float, right: float, amount: float) -> float:
        return left + amount * (right - left)

    @staticmethod
    def _gradient(code: int, x: float, y: float) -> float:
        vectors = ((1.0, 1.0), (-1.0, 1.0), (1.0, -1.0), (-1.0, -1.0),
                   (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0))
        gx, gy = vectors[code & 7]
        return gx * x + gy * y

    def sample(self, x: float, y: float) -> float:
        x_cell = math.floor(x) & 255
        y_cell = math.floor(y) & 255
        x_fraction = x - math.floor(x)
        y_fraction = y - math.floor(y)
        u = self._fade(x_fraction)
        v = self._fade(y_fraction)
        p = self.permutation

        aa = p[p[x_cell] + y_cell]
        ab = p[p[x_cell] + y_cell + 1]
        ba = p[p[x_cell + 1] + y_cell]
        bb = p[p[x_cell + 1] + y_cell + 1]

        lower = self._lerp(
            self._gradient(aa, x_fraction, y_fraction),
            self._gradient(ba, x_fraction - 1.0, y_fraction),
            u,
        )
        upper = self._lerp(
            self._gradient(ab, x_fraction, y_fraction - 1.0),
            self._gradient(bb, x_fraction - 1.0, y_fraction - 1.0),
            u,
        )
        return self._lerp(lower, upper, v)


def add(a: Vec2, b: Vec2) -> Vec2:
    return a[0] + b[0], a[1] + b[1]


def subtract(a: Vec2, b: Vec2) -> Vec2:
    return a[0] - b[0], a[1] - b[1]


def multiply(vector: Vec2, scalar: float) -> Vec2:
    return vector[0] * scalar, vector[1] * scalar


def length(vector: Vec2) -> float:
    return math.hypot(vector[0], vector[1])


def unit(vector: Vec2) -> Vec2:
    magnitude = length(vector)
    return (1.0, 0.0) if magnitude <= 1e-12 else (vector[0] / magnitude, vector[1] / magnitude)


def interpolate(a: Vec2, b: Vec2, amount: float) -> Vec2:
    return a[0] + (b[0] - a[0]) * amount, a[1] + (b[1] - a[1]) * amount


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalise(value: float, low: float, high: float) -> float:
    return 0.5 if math.isclose(low, high) else clamp((value - low) / (high - low), 0.0, 1.0)


def artery_width_profile(fraction: float) -> float:
    """Return a smooth vessel profile: full at nodes and lean at mid-span."""

    t = clamp(fraction, 0.0, 1.0)
    edge_distance = abs(2.0 * t - 1.0)
    smooth_edge = edge_distance * edge_distance * (3.0 - 2.0 * edge_distance)
    # 1.02 at the source, 0.68 at the centre, and 1.05 at the target.
    return 0.68 + smooth_edge * (0.34 + 0.03 * t)


def recursive_branch_depth(deep_visit_normalised: float) -> int:
    """Map DeepVisitCount to a visible tertiary hierarchy and selective depth."""

    deep = clamp(deep_visit_normalised, 0.0, 1.0)
    # Three levels ensure that secondary vessels develop fine terminal children.
    # Deeply engaged exhibits gain a fourth and, selectively, fifth generation.
    return 3 + int(deep >= 0.24) + int(deep >= 0.78)


@dataclass(slots=True)
class CanvasTransform:
    source_min_x: float
    source_min_y: float
    scale: float
    offset_x: float
    offset_y: float

    @classmethod
    def from_graph(cls, graph: Any, config: GrowthConfig) -> "CanvasTransform":
        xs = [float(attributes["x"]) for _, attributes in graph.nodes(data=True)]
        ys = [float(attributes["y"]) for _, attributes in graph.nodes(data=True)]
        if not xs or not ys:
            raise ValueError("The graph has no positioned nodes")
        source_width = max(max(xs) - min(xs), 1.0)
        source_height = max(max(ys) - min(ys), 1.0)
        available_width = config.width - config.margin * 2
        available_height = config.height - config.margin * 2
        scale = min(available_width / source_width, available_height / source_height)
        rendered_width = source_width * scale
        rendered_height = source_height * scale
        return cls(
            source_min_x=min(xs),
            source_min_y=min(ys),
            scale=scale,
            offset_x=(config.width - rendered_width) / 2.0,
            offset_y=(config.height - rendered_height) / 2.0,
        )

    def apply(self, point: Vec2) -> Vec2:
        return (
            self.offset_x + (point[0] - self.source_min_x) * self.scale,
            self.offset_y + (point[1] - self.source_min_y) * self.scale,
        )


@dataclass(slots=True)
class GrowthCurve:
    curve_id: str
    branch_type: str
    order: int
    parent_id: str | None
    source: str
    target: str | None
    visitor_ids: tuple[str, ...]
    visitor_count: int
    traversal_count: int
    forward_traversal_count: int
    reverse_traversal_count: int
    individual_dwell_times: tuple[float, ...]
    screen_points: list[Vec2]
    thickness: float
    start_time_seconds: float
    growth_duration_seconds: float
    lifetime_seconds: float
    average_dwell: float
    visit_count: float
    deep_visit_count: float
    activation_visitor_count: int = 1
    brightness: float = 1.0
    glow_radius: float = 4.0
    reinforcement_times: tuple[float, ...] = ()
    # Each artery keeps the exact visitor start, duration, and direction that
    # reinforced it. Browser renderers can therefore grow the same centreline
    # from either endpoint without creating parallel duplicate routes.
    traversal_events: tuple[tuple[float, float, str, str, str], ...] = ()
    junction_fractions: tuple[float, ...] = ()
    memory_floor: float = 1.0
    source_colour_bias: float = 0.5
    target_colour_bias: float = 0.5

    @property
    def finish_time(self) -> float:
        return self.start_time_seconds + self.lifetime_seconds

    @property
    def arc_length_pixels(self) -> float:
        return sum(length(subtract(b, a)) for a, b in zip(self.screen_points, self.screen_points[1:]))


@dataclass(frozen=True, slots=True)
class NodeMarker:
    """A small biological glow point anchored to an artwork node."""

    node_id: str
    screen_point: Vec2
    radius_pixels: float
    visit_count: int
    average_dwell: float
    brightness: float
    colour_bias: float


class VascularGrowthGenerator:
    """Accumulate visitor movements into a reproducible capillary hierarchy.

    Mapping used by the model:

    * all traffic in either direction forms one arterial centreline per corridor;
    * transition count controls that vessel's width and luminance;
    * AverageDwell controls local root and bifurcation probability;
    * VisitCount caps the number of roots around each exhibition node;
    * DeepVisitCount controls recursive depth, lifetime, and branch reach;
    * low-frequency Perlin noise adds gentle, turn-limited organic curvature.
    """

    def __init__(self, graph: Any, config: GrowthConfig) -> None:
        self.graph = graph
        self.config = config
        self.noise = PerlinNoise2D(config.seed)
        self.transform = CanvasTransform.from_graph(graph, config)
        self.curves: list[GrowthCurve] = []
        self._curve_counter = 0
        self._branch_density: Counter[tuple[int, int]] = Counter()

        node_visits = [float(data["visit_count"]) for _, data in graph.nodes(data=True)]
        node_dwells = [float(data["average_dwell"]) for _, data in graph.nodes(data=True)]
        edge_dwells = [float(data["average_dwell"]) for _, _, data in graph.edges(data=True)]
        individual_dwells = [
            (float(first["dwell_time"]) + float(second["dwell_time"])) / 2.0
            for route in graph.graph.get("visitor_routes", [])
            for first, second in zip(route["events"], route["events"][1:])
        ]
        self.visit_bounds = (min(node_visits), max(node_visits))
        self.node_dwell_bounds = (min(node_dwells), max(node_dwells))
        dwell_values = individual_dwells or edge_dwells
        self.dwell_bounds = (min(dwell_values), max(dwell_values))
        node_deep = [float(data["deep_visit_count"]) for _, data in graph.nodes(data=True)]
        self.node_deep_bounds = (min(node_deep), max(node_deep))

        self.node_colour_bias = {
            node_id: MONOCHROME_COLOUR_BIAS for node_id in graph.nodes
        }
        visitor_routes = graph.graph.get("visitor_routes", [])
        self.visitor_rank = {
            str(route["visitor_id"]): route_index + 1
            for route_index, route in enumerate(visitor_routes)
        }
        self.total_visitors = max(1, len(visitor_routes))
        self.node_visitor_ids: dict[str, set[str]] = defaultdict(set)
        self.node_dwell_values: dict[str, list[float]] = defaultdict(list)
        for route in graph.graph.get("visitor_routes", []):
            visitor_id = str(route["visitor_id"])
            for event in route["events"]:
                node_id = str(event["artwork_id"])
                self.node_visitor_ids[node_id].add(visitor_id)
                self.node_dwell_values[node_id].append(float(event["dwell_time"]))

    def generate(self) -> list[GrowthCurve]:
        self.curves.clear()
        self._curve_counter = 0
        self._branch_density.clear()
        self._generate_capillary_network()
        # Exactly one spatial vessel is generated for each bidirectional artwork
        # corridor. Traffic strengthens that centreline; it never creates full-
        # edge parallel copies. The directed graph remains available for analysis.
        network_curves = list(self.curves)
        # Dendrites render behind the route hierarchy but are generated after it
        # so their parent identifiers and temporal staging can reference the
        # completed data-driven network.
        node_dendrites = self._generate_node_dendrites()
        route_dendrites = self._generate_route_dendrites(network_curves)
        self.curves = node_dendrites + route_dendrites + network_curves
        return self.curves

    def _generate_capillary_network(self) -> None:
        """Generate one smooth collective centreline per observed corridor.

        The directed visitor records remain the evidence carried by each vessel,
        but repeated movements reinforce width and brightness instead of creating
        parallel source-to-target geometry. Low-frequency Perlin drift supplies
        one broad bend; smoothing and a curvature bound preserve continuity and
        exact arrival at both fixed artwork anchors.
        """

        records = self._timed_visitor_segments()
        if not records:
            raise RuntimeError("No visitor transitions are available for capillary growth")

        by_corridor: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            by_corridor[record["corridor"]].append(record)

        # Prefer the reconciled directed graph Count/Weight and retain the
        # observed-record count as a safe lower bound. Both directions contribute
        # to one undirected visual corridor, while direction remains in metadata.
        corridor_transition_counts: dict[tuple[str, str], int] = {}
        for corridor, corridor_records in by_corridor.items():
            graph_count = 0.0
            for source, target in (corridor, tuple(reversed(corridor))):
                if not self.graph.has_edge(source, target):
                    continue
                attributes = self.graph[source][target]
                graph_count += float(
                    attributes.get(
                        "observed_transition_count",
                        attributes.get("weight", 0.0),
                    )
                )
            corridor_transition_counts[corridor] = max(
                len(corridor_records),
                round(graph_count),
            )
        traffic_values = list(corridor_transition_counts.values())
        traffic_bounds = (float(min(traffic_values)), float(max(traffic_values)))
        ordered_corridors = sorted(
            by_corridor,
            key=lambda corridor: (-corridor_transition_counts[corridor], corridor),
        )
        artery_start_by_corridor = {
            corridor: 0.28 + rank * 0.20
            for rank, corridor in enumerate(ordered_corridors)
        }
        corridor_lengths = {
            corridor: length(subtract(
                self._node_point(corridor[1]),
                self._node_point(corridor[0]),
            ))
            for corridor in ordered_corridors
        }
        longest_corridor = max(corridor_lengths.values())
        node_points = [self._node_point(node_id) for node_id in self.graph.nodes]
        composition_centre = (
            sum(point[0] for point in node_points) / len(node_points),
            sum(point[1] for point in node_points) / len(node_points),
        )

        for corridor in ordered_corridors:
            corridor_records = by_corridor[corridor]
            start = self._node_point(corridor[0])
            end = self._node_point(corridor[1])
            distance = length(subtract(end, start))
            traffic_n = normalise(
                float(corridor_transition_counts[corridor]), *traffic_bounds
            )

            point_count = max(33, math.ceil(max(32.0, distance / 6.0)) + 1)
            corridor_phase = self._stable_corridor_phase(corridor)
            # Attraction stays deliberately modest: every vessel reaches the
            # target, while the organic field has room to create one calm bend.
            # Popular routes are only slightly calmer, never multiplied.
            guide_amplitude = distance * (
                0.15 + self.config.curvature_strength * 0.72 - 0.035 * traffic_n
            )
            # Pull only the longest outer-spanning connection toward the inner
            # composition. This opens the overall silhouette without changing
            # any graph relationship or forcing the route into a straight line.
            outer_span = normalise(
                distance,
                longest_corridor * 0.82,
                longest_corridor,
            )
            guide_amplitude *= 1.0 - 0.46 * outer_span
            centreline = self._smooth_path(
                self._curved_connection(
                    start,
                    end,
                    point_count,
                    guide_amplitude,
                    corridor_phase,
                ),
                (),
                passes=6,
            )
            if outer_span > 0.0:
                centreline = self._smooth_path(
                    [
                        interpolate(
                            point,
                            interpolate(start, end, index / (len(centreline) - 1)),
                            outer_span
                            * 0.30
                            * math.sin(math.pi * index / (len(centreline) - 1)) ** 1.4,
                        )
                        for index, point in enumerate(centreline)
                    ],
                    (),
                    passes=4,
                )
            # Medium-long perimeter edges are softly biased toward the internal
            # field. Their paths therefore weave through the composition instead
            # of joining into a closed fish/leaf-like upper and lower outline.
            span_ratio = distance / longest_corridor
            if 0.58 <= span_ratio <= 0.76:
                direction = unit(subtract(end, start))
                perpendicular = (-direction[1], direction[0])
                baseline_middle = interpolate(start, end, 0.5)
                inward_offset = (
                    subtract(composition_centre, baseline_middle)[0] * perpendicular[0]
                    + subtract(composition_centre, baseline_middle)[1] * perpendicular[1]
                )
                centreline = self._smooth_path(
                    [
                        add(
                            point,
                            multiply(
                                perpendicular,
                                inward_offset
                                * 0.86
                                * math.sin(math.pi * index / (len(centreline) - 1)) ** 1.3,
                            ),
                        )
                        for index, point in enumerate(centreline)
                    ],
                    (),
                    passes=4,
                )
            centreline = self._smooth_path(centreline, (), passes=7)
            dwell_values = tuple(record["dwell"] for record in corridor_records)
            average_dwell = sum(dwell_values) / len(dwell_values)
            starts = tuple(sorted(record["start_time"] for record in corridor_records))
            end_time = max(
                record["start_time"] + record["duration"] for record in corridor_records
            )
            visitor_ids = tuple(sorted(
                {record["visitor_id"] for record in corridor_records},
                key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
            ))
            forward_count = sum(record["source"] == corridor[0] for record in corridor_records)
            traffic_n = normalise(
                float(corridor_transition_counts[corridor]), *traffic_bounds
            )
            artery_duration = max(
                4.0,
                average_dwell / 12.0 * self.config.main_route_duration_scale,
            )
            artery_start = artery_start_by_corridor[corridor]
            self.curves.append(GrowthCurve(
                curve_id=self._new_id("artery"),
                branch_type="artery",
                order=0,
                parent_id=None,
                source=corridor[0],
                target=corridor[1],
                visitor_ids=visitor_ids,
                visitor_count=len(visitor_ids),
                traversal_count=corridor_transition_counts[corridor],
                forward_traversal_count=forward_count,
                reverse_traversal_count=len(corridor_records) - forward_count,
                individual_dwell_times=dwell_values,
                screen_points=centreline,
                thickness=(
                    self.config.artery_min_thickness
                    + (self.config.artery_max_thickness - self.config.artery_min_thickness)
                    * traffic_n ** 1.70
                ),
                start_time_seconds=artery_start,
                growth_duration_seconds=artery_duration,
                lifetime_seconds=max(artery_duration, end_time - artery_start),
                average_dwell=average_dwell,
                visit_count=float(len(visitor_ids)),
                deep_visit_count=float(sum(record["deep"] for record in corridor_records)),
                activation_visitor_count=min(
                    record["route_index"] + 1 for record in corridor_records
                ),
                brightness=0.68 + 0.32 * traffic_n,
                glow_radius=3.5 + 3.5 * traffic_n,
                reinforcement_times=starts,
                traversal_events=tuple(
                    (
                        float(record["start_time"]),
                        float(record["duration"]),
                        str(record["source"]),
                        str(record["target"]),
                        str(record["visitor_id"]),
                    )
                    for record in sorted(
                        corridor_records,
                        key=lambda value: (
                            value["start_time"],
                            value["route_index"],
                            value["segment_index"],
                        ),
                    )
                ),
                junction_fractions=(),
                memory_floor=1.0,
                source_colour_bias=self.node_colour_bias[corridor[0]],
                target_colour_bias=self.node_colour_bias[corridor[1]],
            ))

    def _generate_node_dendrites(self) -> list[GrowthCurve]:
        """Generate data-weighted neural trees rooted at exhibition nodes.

        These are not independent decorative strokes. Every tree is attached to
        one real artwork node, carries that node's visitor evidence, and has an
        explicit parent chain. VisitCount controls the maximum number of primary
        roots, AverageDwell controls root and bifurcation probability, and
        DeepVisitCount controls recursive depth, reach, and developmental life.
        """

        dendrites: list[GrowthCurve] = []
        for node_index, (node_id, attributes) in enumerate(
            sorted(self.graph.nodes(data=True))
        ):
            visit_count = float(attributes["visit_count"])
            average_dwell = float(attributes["average_dwell"])
            deep_visit_count = float(attributes["deep_visit_count"])
            visit_n = normalise(visit_count, *self.visit_bounds)
            dwell_n = normalise(average_dwell, *self.node_dwell_bounds)
            deep_n = normalise(deep_visit_count, *self.node_deep_bounds)
            maximum_roots = max(
                5,
                round((6.0 + visit_n * 9.0) * self.config.dendrite_density),
            )
            maximum_depth = recursive_branch_depth(deep_n)
            root_length = (
                15.0 + deep_n * 27.0
            ) * self.config.dendrite_length_scale
            split_probability = clamp(
                0.34 + dwell_n * 0.52 + deep_n * 0.08,
                0.32,
                0.96,
            )
            root_probability = clamp(0.62 + dwell_n * 0.34, 0.58, 0.98)
            root_width = 1.08 + visit_n * 0.38 + deep_n * 0.16
            token = f"{node_id}|{self.config.seed}|dendrite"
            stable_seed = sum(
                (index + 1) * ord(character)
                for index, character in enumerate(token)
            )
            rng = random.Random(stable_seed)
            visitor_ids = tuple(sorted(
                self.node_visitor_ids.get(node_id, set()),
                key=lambda value: (
                    not value.isdigit(),
                    int(value) if value.isdigit() else value,
                ),
            ))
            dwell_values = tuple(
                self.node_dwell_values.get(node_id, [average_dwell])
            )

            for root_index in range(maximum_roots):
                root_segment_length = root_length * rng.uniform(0.78, 1.12)
                angle = self._exploratory_angle(
                    rng,
                    self._node_point(node_id),
                    None,
                    math.pi,
                    root_segment_length,
                )
                probe = add(
                    self._node_point(node_id),
                    (
                        math.cos(angle) * root_segment_length,
                        math.sin(angle) * root_segment_length,
                    ),
                )
                effective_root_probability = root_probability * self._density_exploration_factor(
                    probe,
                    dwell_n,
                )
                if rng.random() > effective_root_probability:
                    continue
                start_time = 3.0 + node_index * 0.28 + root_index * 0.035
                self._grow_dendrite_tree(
                    output=dendrites,
                    rng=rng,
                    node_id=node_id,
                    visitor_ids=visitor_ids,
                    dwell_values=dwell_values,
                    visit_count=visit_count,
                    average_dwell=average_dwell,
                    deep_visit_count=deep_visit_count,
                    visit_n=visit_n,
                    dwell_n=dwell_n,
                    deep_n=deep_n,
                    start=self._node_point(node_id),
                    angle=angle,
                    segment_length=root_segment_length,
                    branch_width=root_width * rng.uniform(0.92, 1.08),
                    depth=0,
                    maximum_depth=maximum_depth,
                    split_probability=split_probability,
                    parent_id=None,
                    start_time=start_time,
                    activation_visitor_count=self._activation_rank_for_fraction(
                        visitor_ids,
                        (root_index + 0.5) / maximum_roots,
                    ),
                )
        return dendrites

    def _generate_route_dendrites(
        self,
        network_curves: Sequence[GrowthCurve],
    ) -> list[GrowthCurve]:
        """Grow local parent-child trees from points on each arterial centreline."""

        dendrites: list[GrowthCurve] = []
        arteries = [
            curve for curve in network_curves if curve.branch_type == "artery"
        ]
        traffic_values = [float(curve.traversal_count) for curve in arteries]
        traffic_bounds = (
            (min(traffic_values), max(traffic_values))
            if traffic_values
            else (0.0, 1.0)
        )
        route_dwell_values = [curve.average_dwell for curve in arteries]
        route_dwell_bounds = (
            (min(route_dwell_values), max(route_dwell_values))
            if route_dwell_values
            else (0.0, 1.0)
        )
        deep_rates = [
            curve.deep_visit_count / max(1.0, float(curve.traversal_count))
            for curve in arteries
        ]
        deep_bounds = (
            (min(deep_rates), max(deep_rates))
            if deep_rates
            else (0.0, 1.0)
        )
        for artery in arteries:
            dwell_n = normalise(artery.average_dwell, *route_dwell_bounds)
            traffic_n = normalise(float(artery.traversal_count), *traffic_bounds)
            density_values = [
                float(self.graph[source][target].get("relationship_density", 0.0))
                for source, target in (
                    (artery.source, artery.target),
                    (artery.target, artery.source),
                )
                if self.graph.has_edge(source, target)
            ]
            density_n = clamp(max(density_values, default=traffic_n), 0.0, 1.0)
            deep_rate = clamp(
                artery.deep_visit_count / max(1.0, float(artery.traversal_count)),
                0.0,
                1.0,
            )
            deep_n = normalise(deep_rate, *deep_bounds)
            maximum_depth = recursive_branch_depth(deep_n)
            maximum_root_length = (
                22.0 + deep_n * 40.0
            ) * self.config.dendrite_length_scale
            split_probability = clamp(
                0.32
                + dwell_n * 0.43
                + density_n * 0.17
                + deep_n * 0.05,
                0.30,
                0.97,
            )
            root_probability = clamp(
                0.56 + dwell_n * 0.25 + density_n * 0.13 + traffic_n * 0.04,
                0.54,
                0.98,
            )
            candidate_count = max(
                6,
                round(
                    (
                        7.0
                        + dwell_n * 14.0
                        + density_n * 8.0
                        + traffic_n * 2.0
                    )
                    * self.config.capillary_density
                ),
            )
            token = f"{artery.curve_id}|{self.config.seed}|local-tree"
            stable_seed = sum(
                (index + 1) * ord(character)
                for index, character in enumerate(token)
            )
            rng = random.Random(stable_seed)
            span = 0.78 / candidate_count
            branch_origins = sorted(
                0.11 + candidate_index * span + rng.uniform(0.18, 0.82) * span
                for candidate_index in range(candidate_count)
            )
            accepted_origins: list[float] = []
            for branch_index, fraction in enumerate(branch_origins):
                point_index = round(fraction * (len(artery.screen_points) - 1))
                previous = artery.screen_points[max(0, point_index - 1)]
                following = artery.screen_points[
                    min(len(artery.screen_points) - 1, point_index + 1)
                ]
                tangent = unit(subtract(following, previous))
                tangent_angle = math.atan2(tangent[1], tangent[0])
                start = artery.screen_points[point_index]
                side = -1.0 if rng.random() < 0.5 else 1.0
                branch_angle = math.radians(rng.uniform(25.0, 65.0))
                base_angle = tangent_angle + side * branch_angle
                root_segment_length = maximum_root_length * rng.uniform(0.72, 1.0)
                angle = self._exploratory_angle(
                    rng,
                    start,
                    base_angle,
                    0.06,
                    root_segment_length,
                )
                probe = add(
                    start,
                    (
                        math.cos(angle) * root_segment_length,
                        math.sin(angle) * root_segment_length,
                    ),
                )
                effective_probability = root_probability * self._density_exploration_factor(
                    probe,
                    dwell_n,
                )
                # Every observed corridor receives at least one local root; the
                # normalized dwell probability controls all additional density.
                force_last_root = (
                    branch_index == candidate_count - 1 and not accepted_origins
                )
                if rng.random() > effective_probability and not force_last_root:
                    continue
                accepted_origins.append(fraction)
                start_time = (
                    artery.start_time_seconds
                    + artery.growth_duration_seconds * fraction
                    + 0.65
                )
                colour_bias = artery.source_colour_bias
                self._grow_dendrite_tree(
                    output=dendrites,
                    rng=rng,
                    node_id=artery.source,
                    visitor_ids=artery.visitor_ids,
                    dwell_values=artery.individual_dwell_times,
                    visit_count=artery.visit_count,
                    average_dwell=artery.average_dwell,
                    deep_visit_count=artery.deep_visit_count,
                    visit_n=traffic_n,
                    dwell_n=dwell_n,
                    deep_n=deep_n,
                    start=start,
                    angle=angle,
                    segment_length=root_segment_length,
                    branch_width=max(
                        1.20,
                        min(
                            2.20,
                            artery.thickness
                            * artery_width_profile(fraction)
                            * rng.uniform(0.25, 0.35),
                        ),
                    ),
                    depth=0,
                    maximum_depth=maximum_depth,
                    split_probability=split_probability,
                    parent_id=artery.curve_id,
                    start_time=start_time,
                    branch_type="route_dendrite",
                    target_id=artery.target,
                    colour_bias_override=colour_bias,
                    activation_visitor_count=self._activation_rank_for_fraction(
                        artery.visitor_ids,
                        (branch_index + 0.5) / candidate_count,
                    ),
                )
            artery.junction_fractions = tuple(accepted_origins)
        return dendrites

    def _grow_dendrite_tree(
        self,
        *,
        output: list[GrowthCurve],
        rng: random.Random,
        node_id: str,
        visitor_ids: tuple[str, ...],
        dwell_values: tuple[float, ...],
        visit_count: float,
        average_dwell: float,
        deep_visit_count: float,
        visit_n: float,
        dwell_n: float,
        deep_n: float,
        start: Vec2,
        angle: float,
        segment_length: float,
        branch_width: float,
        depth: int,
        maximum_depth: int,
        split_probability: float,
        parent_id: str | None,
        start_time: float,
        activation_visitor_count: int,
        branch_type: str = "dwell_dendrite",
        target_id: str | None = None,
        colour_bias_override: float | None = None,
    ) -> None:
        """Recursively add one smooth, tapered dendrite and its children."""

        if depth >= maximum_depth or segment_length < 5.5:
            return
        phase = rng.uniform(0.0, 10_000.0)
        points = self._dendrite_bezier_segment(
            start,
            angle,
            segment_length,
            phase,
            rng,
        )
        curve_id = self._new_id("dendrite")
        duration = max(
            0.34,
            segment_length / 65.0 * (0.82 + 0.38 * deep_n),
        )
        colour_bias = (
            self.node_colour_bias[node_id]
            if colour_bias_override is None
            else colour_bias_override
        )
        curve = GrowthCurve(
            curve_id=curve_id,
            branch_type=branch_type,
            order=3 + depth,
            parent_id=parent_id,
            source=node_id,
            target=target_id,
            visitor_ids=visitor_ids,
            visitor_count=len(visitor_ids),
            traversal_count=len(dwell_values),
            forward_traversal_count=0,
            reverse_traversal_count=0,
            individual_dwell_times=dwell_values,
            screen_points=points,
            thickness=max(0.14, branch_width),
            start_time_seconds=start_time,
            growth_duration_seconds=duration,
            lifetime_seconds=duration * (1.0 + 0.34 * deep_n),
            average_dwell=average_dwell,
            visit_count=visit_count,
            deep_visit_count=deep_visit_count,
            activation_visitor_count=activation_visitor_count,
            brightness=(0.34 + dwell_n * 0.38 + deep_n * 0.10) * (0.90 ** depth),
            glow_radius=max(0.38, 1.55 * (0.68 ** depth)),
            reinforcement_times=(start_time,),
            memory_floor=max(0.55, self.config.memory_floor),
            source_colour_bias=colour_bias,
            target_colour_bias=colour_bias,
        )
        output.append(curve)
        self._record_branch_density(points)

        if depth + 1 >= maximum_depth:
            return
        # Fifth-generation survival remains data-selective, while all trees are
        # allowed to form a complete secondary/tertiary hierarchy first.
        if (
            maximum_depth >= 5
            and depth == 3
            and rng.random() > 0.48 + 0.34 * deep_n + 0.10 * dwell_n
        ):
            return
        end = points[-1]
        tangent = unit(subtract(points[-1], points[-2]))
        tangent_angle = math.atan2(tangent[1], tangent[0])
        child_start = start_time + duration * 0.58

        # One continuation preserves the primary tree direction. Its angle is
        # softly biased into less occupied tissue without disrupting tangent
        # continuity at the parent junction.
        continuation_length = segment_length * rng.uniform(0.66, 0.82)
        continuation_width = branch_width * rng.uniform(0.58, 0.72)
        continuation_angle = self._exploratory_angle(
            rng,
            end,
            tangent_angle,
            0.16,
            continuation_length,
        )
        self._grow_dendrite_tree(
            output=output,
            rng=rng,
            node_id=node_id,
            visitor_ids=visitor_ids,
            dwell_values=dwell_values,
            visit_count=visit_count,
            average_dwell=average_dwell,
            deep_visit_count=deep_visit_count,
            visit_n=visit_n,
            dwell_n=dwell_n,
            deep_n=deep_n,
            start=end,
            angle=continuation_angle,
            segment_length=continuation_length,
            branch_width=continuation_width,
            depth=depth + 1,
            maximum_depth=maximum_depth,
            split_probability=split_probability * 0.98,
            parent_id=curve_id,
            start_time=child_start,
            activation_visitor_count=activation_visitor_count,
            branch_type=branch_type,
            target_id=target_id,
            colour_bias_override=colour_bias,
        )

        # A second child is deterministic for the seed but its probability is
        # driven by the node's dwell and deep-visit engagement.
        density_factor = self._density_exploration_factor(end, dwell_n)
        effective_split_probability = clamp(
            split_probability * density_factor,
            0.08,
            0.97,
        )
        if rng.random() <= effective_split_probability:
            child_length = segment_length * rng.uniform(0.58, 0.76)
            child_width = branch_width * rng.uniform(0.55, 0.70)
            branch_angle = math.radians(rng.uniform(25.0, 65.0))
            left_angle = tangent_angle - branch_angle
            right_angle = tangent_angle + branch_angle
            left_probe = add(
                end,
                (math.cos(left_angle) * child_length, math.sin(left_angle) * child_length),
            )
            right_probe = add(
                end,
                (math.cos(right_angle) * child_length, math.sin(right_angle) * child_length),
            )
            left_density = self._local_branch_density(left_probe)
            right_density = self._local_branch_density(right_probe)
            if math.isclose(left_density, right_density, abs_tol=0.25):
                side_angle = left_angle if rng.random() < 0.5 else right_angle
            else:
                side_angle = left_angle if left_density < right_density else right_angle
            self._grow_dendrite_tree(
                output=output,
                rng=rng,
                node_id=node_id,
                visitor_ids=visitor_ids,
                dwell_values=dwell_values,
                visit_count=visit_count,
                average_dwell=average_dwell,
                deep_visit_count=deep_visit_count,
                visit_n=visit_n,
                dwell_n=dwell_n,
                deep_n=deep_n,
                start=end,
                angle=side_angle,
                segment_length=child_length,
                branch_width=child_width,
                depth=depth + 1,
                maximum_depth=maximum_depth,
                split_probability=split_probability * 0.93,
                parent_id=curve_id,
                start_time=child_start + duration * 0.10,
                activation_visitor_count=activation_visitor_count,
                branch_type=branch_type,
                target_id=target_id,
                colour_bias_override=colour_bias,
            )

    def _dendrite_bezier_segment(
        self,
        start: Vec2,
        angle: float,
        segment_length: float,
        phase: float,
        rng: random.Random,
    ) -> list[Vec2]:
        """Create one smooth cubic-Bezier neural segment with micro-curvature."""

        turn = rng.uniform(-0.20, 0.20)
        end_angle = angle + turn
        travel_angle = angle + turn * 0.46
        end = add(
            start,
            (
                math.cos(travel_angle) * segment_length,
                math.sin(travel_angle) * segment_length,
            ),
        )
        start_direction = (math.cos(angle), math.sin(angle))
        end_direction = (math.cos(end_angle), math.sin(end_angle))
        normal = (-start_direction[1], start_direction[0])
        bend = rng.uniform(-0.075, 0.075) * segment_length
        control_1 = add(
            add(start, multiply(start_direction, segment_length * 0.36)),
            multiply(normal, bend),
        )
        control_2 = add(
            subtract(end, multiply(end_direction, segment_length * 0.34)),
            multiply(normal, bend * 0.55),
        )
        point_count = max(7, math.ceil(segment_length / 5.5))
        points: list[Vec2] = []
        for index in range(point_count):
            t = index / (point_count - 1)
            inverse = 1.0 - t
            point = (
                inverse ** 3 * start[0]
                + 3.0 * inverse ** 2 * t * control_1[0]
                + 3.0 * inverse * t ** 2 * control_2[0]
                + t ** 3 * end[0],
                inverse ** 3 * start[1]
                + 3.0 * inverse ** 2 * t * control_1[1]
                + 3.0 * inverse * t ** 2 * control_2[1]
                + t ** 3 * end[1],
            )
            micro_noise = self.noise.sample(
                phase + t * self.config.noise_frequency * 2.8,
                phase * 0.013 + 31.7,
            )
            envelope = math.sin(math.pi * t)
            point = add(
                point,
                multiply(normal, segment_length * 0.018 * envelope * micro_noise),
            )
            points.append(point)
        points[0] = start
        return points

    def _timed_visitor_segments(self) -> list[dict[str, Any]]:
        """Attach a calm, continuous animation schedule to visitor movements."""

        route_elapsed: dict[int, float] = defaultdict(float)
        records: list[dict[str, Any]] = []
        for route_index, visitor_id, segment_index, current, following in self._visitor_segments():
            source = str(current["artwork_id"])
            target = str(following["artwork_id"])
            dwell = (
                float(current["dwell_time"]) + float(following["dwell_time"])
            ) / 2.0
            duration = max(
                1.0,
                dwell / self.config.visitor_seconds_per_animation_second
                * self.config.main_route_duration_scale,
            )
            start_time = (
                self.config.trace_stage_delay
                + 0.40
                + route_index * 0.32
                + route_elapsed[route_index]
            )
            route_elapsed[route_index] += duration * 0.64
            corridor = tuple(sorted((source, target)))
            token = (
                f"{visitor_id}|{segment_index}|{source}|{target}|{self.config.seed}"
            )
            phase = (
                sum((index + 1) * ord(character) for index, character in enumerate(token))
                % 100_000
            ) / 97.0
            records.append({
                "route_index": route_index,
                "visitor_id": str(visitor_id) if visitor_id is not None else "graph",
                "segment_index": segment_index,
                "source": source,
                "target": target,
                "corridor": corridor,
                "dwell": dwell,
                "deep": float(following["dwell_time"]) >= DEEP_VISIT_THRESHOLD_SECONDS,
                "duration": duration,
                "start_time": start_time,
                "phase": phase,
            })
        return records

    @staticmethod
    def _smooth_path(
        points: Sequence[Vec2],
        junction_fractions: Sequence[float],
        passes: int,
    ) -> list[Vec2]:
        """Low-pass filter a polyline while preserving topology anchors."""

        result = list(points)
        protected = {0, len(result) - 1}
        protected.update(
            round(fraction * (len(result) - 1))
            for fraction in junction_fractions
        )
        for _ in range(max(0, passes)):
            previous = result
            result = list(previous)
            for index in range(1, len(previous) - 1):
                if index in protected:
                    continue
                result[index] = (
                    previous[index - 1][0] * 0.23
                    + previous[index][0] * 0.54
                    + previous[index + 1][0] * 0.23,
                    previous[index - 1][1] * 0.23
                    + previous[index][1] * 0.54
                    + previous[index + 1][1] * 0.23,
                )
        return result

    def generate_node_markers(self) -> list[NodeMarker]:
        """Create data-scaled soft biological cores for every artwork anchor."""

        markers: list[NodeMarker] = []
        for node_id, attributes in sorted(self.graph.nodes(data=True)):
            visit_count = int(attributes["visit_count"])
            average_dwell = float(attributes["average_dwell"])
            visit_n = normalise(float(visit_count), *self.visit_bounds)
            dwell_n = normalise(average_dwell, *self.node_dwell_bounds)
            radius = self.config.min_node_radius + (
                self.config.max_node_radius - self.config.min_node_radius
            ) * visit_n
            markers.append(
                NodeMarker(
                    node_id=node_id,
                    screen_point=self._node_point(node_id),
                    radius_pixels=radius,
                    visit_count=visit_count,
                    average_dwell=average_dwell,
                    brightness=0.58 + 0.42 * dwell_n,
                    colour_bias=self.node_colour_bias[node_id],
                )
            )
        return markers

    def _new_id(self, prefix: str) -> str:
        self._curve_counter += 1
        return f"{prefix}_{self._curve_counter:04d}"

    def _density_cell(self, point: Vec2) -> tuple[int, int]:
        size = self.config.local_density_cell_size
        return math.floor(point[0] / size), math.floor(point[1] / size)

    def _local_branch_density(self, point: Vec2) -> float:
        """Estimate fine-vessel crowding in a compact spatial neighbourhood."""

        centre_x, centre_y = self._density_cell(point)
        density = 0.0
        for offset_x in (-1, 0, 1):
            for offset_y in (-1, 0, 1):
                distance_weight = 1.0 if offset_x == 0 and offset_y == 0 else 0.46
                density += (
                    self._branch_density[(centre_x + offset_x, centre_y + offset_y)]
                    * distance_weight
                )
        return density

    def _record_branch_density(self, points: Sequence[Vec2]) -> None:
        """Deposit a branch midpoint and tip into the local density field."""

        if len(points) < 2:
            return
        for point in (points[len(points) // 2], points[-1]):
            self._branch_density[self._density_cell(point)] += 1

    def _density_exploration_factor(
        self,
        point: Vec2,
        dwell_n: float = 0.0,
    ) -> float:
        """Prefer empty tissue while allowing more density after long dwell."""

        crowding = self._local_branch_density(point)
        dwell_tolerance = 1.0 - 0.54 * clamp(dwell_n, 0.0, 1.0)
        factor = (1.12 + 0.17 * dwell_n) / (
            1.0
            + crowding
            * 0.038
            * dwell_tolerance
            * self.config.local_density_strength
        )
        return clamp(factor, 0.26, 1.29)

    def _exploratory_angle(
        self,
        rng: random.Random,
        start: Vec2,
        base_angle: float | None,
        spread: float,
        probe_length: float,
    ) -> float:
        """Select a softly random heading biased toward locally empty space."""

        candidates: list[float] = []
        for _ in range(5):
            if base_angle is None:
                candidates.append(rng.uniform(0.0, math.tau))
            else:
                candidates.append(base_angle + rng.uniform(-spread, spread))
        return min(
            candidates,
            key=lambda angle: self._local_branch_density(
                add(
                    start,
                    (
                        math.cos(angle) * probe_length,
                        math.sin(angle) * probe_length,
                    ),
                )
            )
            + rng.random() * 0.18,
        )

    def _activation_rank_for_fraction(
        self,
        visitor_ids: Sequence[str],
        fraction: float,
    ) -> int:
        """Map a generated detail to the cumulative visitor cohort that reveals it."""

        ranks = sorted(
            self.visitor_rank[visitor_id]
            for visitor_id in visitor_ids
            if visitor_id in self.visitor_rank
        )
        if not ranks:
            return 1
        index = min(len(ranks) - 1, math.floor(clamp(fraction, 0.0, 0.999999) * len(ranks)))
        return ranks[index]

    def _node_point(self, node_id: str) -> Vec2:
        attributes = self.graph.nodes[node_id]
        return self.transform.apply((float(attributes["x"]), float(attributes["y"])))

    def _corridor_attributes(self, source: str, target: str) -> Any:
        """Return edge metrics without imposing a direction on the corridor."""

        if self.graph.has_edge(source, target):
            return self.graph.edges[source, target]
        if self.graph.has_edge(target, source):
            return self.graph.edges[target, source]
        raise RuntimeError(f"No graph corridor exists between {source!r} and {target!r}")

    def _stable_corridor_phase(self, corridor: tuple[str, str]) -> float:
        """Create a process-independent Perlin phase for a node pair."""

        token = f"{corridor[0]}|{corridor[1]}|{self.config.seed}"
        return (sum((index + 1) * ord(character) for index, character in enumerate(token)) % 100_000) / 100.0

    def _visitor_segments(
        self,
    ) -> list[tuple[int, str | None, int, dict[str, Any], dict[str, Any]]]:
        """Return every individual visitor choice in route and sequence order."""

        segments: list[tuple[int, str | None, int, dict[str, Any], dict[str, Any]]] = []
        for route_index, route in enumerate(self.graph.graph.get("visitor_routes", [])):
            events = route["events"]
            for segment_index, (current, following) in enumerate(zip(events, events[1:]), start=1):
                segments.append(
                    (route_index, str(route["visitor_id"]), segment_index, current, following)
                )

        if segments:
            return segments

        # A dataset containing only single-artwork visits has no transitions.
        # In that exceptional case, show every undirected graph corridor once.
        seen: set[tuple[str, str]] = set()
        for segment_index, (source, target) in enumerate(self.graph.edges(), start=1):
            corridor = tuple(sorted((source, target)))
            if corridor in seen:
                continue
            seen.add(corridor)
            dwell = float(self._corridor_attributes(source, target)["average_dwell"])
            segments.append((
                0,
                None,
                segment_index,
                {"artwork_id": source, "order": segment_index, "dwell_time": dwell},
                {"artwork_id": target, "order": segment_index + 1, "dwell_time": dwell},
            ))
        return segments

    def _curved_connection(
        self, start: Vec2, end: Vec2, point_count: int, amplitude: float, phase: float
    ) -> list[Vec2]:
        """Create a smooth, turn-limited centreline that still reaches its node.

        Perlin noise first defines a slowly moving organic attractor around the
        direct connection. Repeated interpolation smooths the implied tangent
        angles and an explicit second-difference limit bounds local curvature.
        The normal-offset envelope is zero at both ends, guaranteeing exact
        arrival without a late kink.
        """

        displacement = subtract(end, start)
        direction = unit(displacement)
        perpendicular = (-direction[1], direction[0])
        raw_offsets: list[float] = []
        sampled_drift = self.noise.sample(phase * 0.19, phase * 0.041 + 13.7)
        drift_sign = -1.0 if math.sin(phase * 0.071 + 0.9) < 0.0 else 1.0
        # A minimum low-frequency bias prevents an unlucky near-zero Perlin
        # sample from collapsing a corridor back into a straight road.
        corridor_drift = drift_sign * (0.56 + abs(sampled_drift) * 0.30)
        for index in range(point_count):
            t = index / (point_count - 1)
            envelope = math.sin(math.pi * t) ** 0.82
            primary_noise = self.noise.sample(
                phase * 0.23 + t * self.config.noise_frequency * 0.72,
                phase * 0.017 + t * 0.37,
            )
            secondary_noise = self.noise.sample(
                phase * 0.11 + t * self.config.noise_frequency * 1.55,
                phase * 0.029 + t * 0.81 + 27.4,
            )
            organic_offset = clamp(
                corridor_drift * 0.58 + primary_noise * 0.92 + secondary_noise * 0.24,
                -1.15,
                1.15,
            )
            raw_offsets.append(amplitude * envelope * organic_offset)
        raw_offsets[0] = 0.0
        raw_offsets[-1] = 0.0

        # Repeated low-pass interpolation removes angular discontinuities while
        # retaining the low-frequency Perlin bend. Endpoints remain locked.
        offsets = raw_offsets
        smoothing_passes = max(
            5,
            round(11.0 - self.config.attraction_strength * 4.0),
        )
        for _ in range(smoothing_passes):
            previous = offsets
            offsets = list(previous)
            for index in range(1, point_count - 1):
                offsets[index] = (
                    previous[index - 1] * 0.24
                    + previous[index] * 0.52
                    + previous[index + 1] * 0.24
                )
            offsets[0] = 0.0
            offsets[-1] = 0.0

        # The second difference of the normal offset approximates turning
        # curvature. Clamp it over several passes to prevent sharp changes in
        # heading, then reconstruct the centreline against the exact baseline.
        maximum_second_difference = max(0.18, amplitude / point_count * 0.095)
        for _ in range(4):
            limited = list(offsets)
            for index in range(1, point_count - 1):
                second_difference = (
                    offsets[index - 1] - 2.0 * offsets[index] + offsets[index + 1]
                )
                bounded = clamp(
                    second_difference,
                    -maximum_second_difference,
                    maximum_second_difference,
                )
                limited[index] += (second_difference - bounded) * 0.5
            limited[0] = 0.0
            limited[-1] = 0.0
            offsets = limited

        result = [
            add(
                interpolate(start, end, index / (point_count - 1)),
                multiply(perpendicular, offsets[index]),
            )
            for index in range(point_count)
        ]
        result[0] = start
        result[-1] = end
        return result

class BlenderJsonExporter:
    """Export curves in a stable JSON structure convenient for Blender Python."""

    def __init__(self, config: GrowthConfig) -> None:
        self.config = config

    def _blender_point(self, point: Vec2) -> list[float]:
        # Centre the pygame canvas on the Blender origin.  Screen Y points down,
        # so it is inverted to Blender Y; curves lie on Z=0 and can be extruded
        # with bevel_depth or projected onto another surface by an import script.
        scale = self.config.pixels_per_blender_unit
        return [
            round((point[0] - self.config.width / 2.0) / scale, 6),
            round((self.config.height / 2.0 - point[1]) / scale, 6),
            0.0,
        ]

    def build_payload(
        self,
        graph: Any,
        curves: Sequence[GrowthCurve],
        node_markers: Sequence[NodeMarker],
        data: DatasetBundle,
    ) -> dict[str, Any]:
        curve_items: list[dict[str, Any]] = []
        for curve in curves:
            point_total = max(1, len(curve.screen_points) - 1)
            radii: list[float] = []
            for index in range(len(curve.screen_points)):
                t = index / point_total
                if curve.branch_type == "artery":
                    radius = 0.72 + 0.28 * math.sin(math.pi * t)
                elif curve.branch_type == "repeated_path":
                    radius = 0.58 + 0.42 * math.sin(math.pi * t)
                elif curve.branch_type in {"dwell_dendrite", "route_dendrite"}:
                    radius = 1.0 - 0.86 * t
                else:
                    radius = 0.42 + 0.58 * math.sin(math.pi * t)
                radii.append(round(radius, 6))
            curve_items.append({
                "id": curve.curve_id,
                "type": curve.branch_type,
                "order": curve.order,
                "parent_id": curve.parent_id,
                "source": curve.source,
                "target": curve.target,
                "visitor_route": {
                    "aggregated": curve.branch_type != "visitor_trace",
                    "directed": curve.branch_type in {"visitor_trace", "repeated_path"},
                    "corridor": (
                        [curve.source, curve.target]
                        if curve.target is not None
                        else None
                    ),
                    "origin_node": (
                        curve.source if curve.branch_type == "dwell_dendrite" else None
                    ),
                    "visitor_ids": list(curve.visitor_ids),
                    "visitor_count": curve.visitor_count,
                    "activation_visitor_count": curve.activation_visitor_count,
                    "traversal_count": curve.traversal_count,
                    "forward_traversal_count": curve.forward_traversal_count,
                    "reverse_traversal_count": curve.reverse_traversal_count,
                    "individual_segment_dwell_times": list(curve.individual_dwell_times),
                },
                "points": [self._blender_point(point) for point in curve.screen_points],
                "screen_points": [[round(x, 3), round(y, 3)] for x, y in curve.screen_points],
                "radii": radii,
                "thickness_pixels": round(curve.thickness, 3),
                "bevel_depth": round(max(0.01, curve.thickness / self.config.pixels_per_blender_unit), 6),
                "arc_length_pixels": round(curve.arc_length_pixels, 3),
                "junction_fractions": [
                    round(value, 6) for value in curve.junction_fractions
                ],
                "visual_tone": {
                    "artery": "bright_monochrome_main_vessel",
                    "repeated_path": "medium_monochrome_vessel",
                    "visitor_trace": "faint_monochrome_trace",
                    "dwell_dendrite": "fine_monochrome_node_capillary",
                    "route_dendrite": "fine_monochrome_route_capillary",
                }[curve.branch_type],
                "colour_bias": {
                    "source": round(curve.source_colour_bias, 6),
                    "target": round(curve.target_colour_bias, 6),
                },
                "timing": {
                    "activation_visitor_count": curve.activation_visitor_count,
                    "start_seconds": round(curve.start_time_seconds, 4),
                    "baseline_growth_duration_seconds": round(curve.growth_duration_seconds, 4),
                    "developmental_lifetime_seconds": round(curve.lifetime_seconds, 4),
                    "reinforcement_times_seconds": [
                        round(value, 4) for value in curve.reinforcement_times
                    ],
                    "traversal_events": [
                        {
                            "start_seconds": round(start, 4),
                            "duration_seconds": round(duration, 4),
                            "source": source,
                            "target": target,
                            "visitor_id": visitor_id,
                            "direction": (
                                "forward"
                                if source == curve.source and target == curve.target
                                else "reverse"
                            ),
                        }
                        for start, duration, source, target, visitor_id
                        in curve.traversal_events
                    ],
                },
                "metrics": {
                    "average_dwell": curve.average_dwell,
                    "visit_count": curve.visit_count,
                    "deep_visit_count": curve.deep_visit_count,
                    "brightness": round(curve.brightness, 6),
                    "glow_radius_pixels": round(curve.glow_radius, 3),
                    "memory_retention_floor": round(curve.memory_floor, 6),
                },
            })

        marker_by_node = {marker.node_id: marker for marker in node_markers}
        nodes = []
        for node_id, attributes in sorted(graph.nodes(data=True)):
            marker = marker_by_node[node_id]
            screen = marker.screen_point
            nodes.append({
                "id": node_id,
                "point": self._blender_point(screen),
                "screen_point": [round(screen[0], 3), round(screen[1], 3)],
                "marker_radius_pixels": round(marker.radius_pixels, 3),
                "marker_radius_blender_units": round(
                    marker.radius_pixels / self.config.pixels_per_blender_unit, 6
                ),
                "brightness": round(marker.brightness, 6),
                "colour_bias": round(marker.colour_bias, 6),
                "visit_count": attributes["visit_count"],
                "average_dwell": attributes["average_dwell"],
                "deep_visit_count": attributes["deep_visit_count"],
            })

        edges = []
        for source, target, attributes in sorted(graph.edges(data=True)):
            edges.append({
                "source": source,
                "target": target,
                "weight": attributes["weight"],
                "average_dwell": attributes["average_dwell"],
                "deep_visit_count": attributes["deep_visit_count"],
                "observed_transition_count": attributes["observed_transition_count"],
                "observed_corridor_count": attributes["observed_corridor_count"],
            })

        return {
            "format": "GrowthNetwork Blender Curves",
            "format_version": "2.3",
            "application_version": APP_VERSION,
            "coordinate_system": {
                "axes": "Blender right-handed XY plane, Z=0",
                "origin": "centre of the pygame canvas",
                "pixels_per_blender_unit": self.config.pixels_per_blender_unit,
            },
            "canvas": {"width": self.config.width, "height": self.config.height},
            "generation": {
                "seed": self.config.seed,
                "system": "visitor-generated hierarchical capillary network",
                "artery_basis": "one bidirectional centreline per artwork corridor",
                "artery_thickness_metric": "summed directed edge Count/Weight",
                "repeated_path_basis": "analytical reinforcement only; no duplicate geometry",
                "individual_trace_basis": "directed evidence retained in artery metadata",
                "brightness_and_glow_metric": "edge Count/Weight for arteries; AverageDwell for branches",
                "node_glow_metric": "node AverageDwell",
                "growth_method": "one turn-limited Perlin centreline plus local recursive growth",
                "branching_method": (
                    "parent-child trees taper and shorten by generation, normally ending freely"
                ),
                "curvature_method": (
                    "multi-frequency seeded Perlin attractors, smooth heading interpolation, "
                    "and bounded angular change"
                ),
                "animation_order": (
                    "arteries initiate first; cumulative visitors reveal persistent local trees"
                ),
                "spatial_memory": "completed vessels remain visible as cumulative spatial memory",
                "dendrite_basis": (
                    "AverageDwell controls density; VisitCount controls node roots; "
                    "DeepVisitCount controls depth, length, and lifetime"
                ),
                "dendrite_geometry": "seeded cubic Bezier branches with explicit parent-child topology",
                "local_density_control": (
                    "nearby fine-vessel occupancy suppresses splitting; empty cells encourage exploration"
                ),
                "colour_method": (
                    "monochrome white-grey; data is encoded by width, luminance, density, "
                    "and complexity"
                ),
                "visitor_stages": "each curve records the cumulative visitor count that activates it",
                "config": asdict(self.config),
            },
            "source": {
                "data_directory": str(data.data_dir),
                "files": list(DatasetLoader.FILE_SCHEMAS),
                "row_counts": data.summary(),
            },
            "graph": {
                "directed": True,
                "analysis_graph_directed": True,
                "rendered_main_routes_directed": False,
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "visitor_flow_edges": [list(edge) for edge in graph.graph["visitor_flow_edges"]],
                "visitor_corridors": [list(edge) for edge in graph.graph["visitor_corridors"]],
                "visitor_paths": graph.graph["visitor_paths"],
                "visitor_routes": graph.graph["visitor_routes"],
                "nodes": nodes,
                "edges": edges,
            },
            "curve_count": len(curve_items),
            "curves": curve_items,
        }

    def export(
        self,
        output_path: Path,
        graph: Any,
        curves: Sequence[GrowthCurve],
        node_markers: Sequence[NodeMarker],
        data: DatasetBundle,
    ) -> None:
        output_path = output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.build_payload(graph, curves, node_markers, data)
        temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            temporary_path.replace(output_path)
        except OSError:
            temporary_path.unlink(missing_ok=True)
            raise


class PygameGrowthRenderer:
    """Animate a flat capillary-red line field on black projection space."""

    BACKGROUND = (0, 0, 0)
    MUTED = (162, 32, 24)

    def __init__(
        self,
        config: GrowthConfig,
        curves: Sequence[GrowthCurve],
        node_markers: Sequence[NodeMarker],
    ) -> None:
        self.config = config
        self.curves = list(curves)
        self.node_markers = list(node_markers)
        visitor_ids = {
            visitor_id
            for curve in self.curves
            for visitor_id in curve.visitor_ids
        }
        self.visitor_order = sorted(
            visitor_ids,
            key=lambda value: (
                not value.isdigit(),
                int(value) if value.isdigit() else value,
            ),
        )
        if not self.visitor_order:
            self.visitor_order = ["graph"]
        self.visitor_rank = {
            visitor_id: index + 1
            for index, visitor_id in enumerate(self.visitor_order)
        }

    def _curve_stage_fraction(self, curve: GrowthCurve, visitor_limit: int) -> float:
        """Return the share of a curve's evidence present in this visitor stage."""

        if curve.activation_visitor_count > visitor_limit:
            return 0.0
        unique_visitors = set(curve.visitor_ids)
        if not unique_visitors:
            return 1.0
        active = sum(
            self.visitor_rank.get(visitor_id, 1) <= visitor_limit
            for visitor_id in unique_visitors
        )
        return active / len(unique_visitors)

    def _stage_final_time(self, visitor_limit: int) -> float:
        """Find the completion time of the selected cumulative visitor cohort."""

        active_curves = [
            curve
            for curve in self.curves
            if self._curve_stage_fraction(curve, visitor_limit) > 0.0
        ]
        return max(
            (
                curve.start_time_seconds
                + (
                    curve.lifetime_seconds
                    if curve.branch_type in {"visitor_trace", "dwell_dendrite", "route_dendrite"}
                    else curve.growth_duration_seconds
                )
                for curve in active_curves
            ),
            default=0.0,
        )

    def run(
        self,
        hold_seconds: float,
        loop: bool = False,
        visitor_limit: int | None = None,
    ) -> None:
        try:
            import pygame
        except ImportError as exc:
            raise DependencyError(
                "pygame is required for real-time rendering. Install dependencies with: "
                "python -m pip install -r requirements.txt (or run with --no-render)."
            ) from exc

        pygame.init()
        try:
            screen = pygame.display.set_mode((self.config.width, self.config.height))
            glow_surface = pygame.Surface(
                (self.config.width, self.config.height), pygame.SRCALPHA
            )
            dendrite_glow_surface = pygame.Surface(
                (self.config.width, self.config.height), pygame.SRCALPHA
            )
            dendrite_core_surface = pygame.Surface(
                (self.config.width, self.config.height), pygame.SRCALPHA
            )
            pygame.display.set_caption(f"{APP_NAME} {APP_VERSION}")
            clock = pygame.time.Clock()
            font = pygame.font.Font(None, 22)
            node_font = pygame.font.Font(None, 20)
            dendrite_types = {"dwell_dendrite", "route_dendrite"}
            dendrite_curves = [
                curve for curve in self.curves if curve.branch_type in dendrite_types
            ]
            primary_curves = [
                curve for curve in self.curves if curve.branch_type not in dendrite_types
            ]
            dendrite_update_interval = 1.0 / self.config.dendrite_refresh_fps
            last_dendrite_update = -math.inf
            cached_dendrite_visible = 0
            total_visitors = len(self.visitor_order)
            early_visitors = max(1, math.ceil(total_visitors * 0.25))
            middle_visitors = max(
                early_visitors,
                math.ceil(total_visitors * 0.60),
            )
            stage_limits = (early_visitors, middle_visitors, total_visitors)
            active_visitor_limit = (
                total_visitors
                if visitor_limit is None
                else max(1, min(total_visitors, visitor_limit))
            )
            start_ticks = pygame.time.get_ticks()
            paused_at: int | None = None
            paused_total = 0
            # A clean field is the museum-projection default. The operator can
            # reveal diagnostics with H without placing UI text in the artwork.
            show_overlay = False
            final_time = self._stage_final_time(active_visitor_limit)
            running = True

            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_ESCAPE, pygame.K_q):
                            running = False
                        elif event.key == pygame.K_SPACE:
                            if paused_at is None:
                                paused_at = pygame.time.get_ticks()
                            else:
                                paused_total += pygame.time.get_ticks() - paused_at
                                paused_at = None
                        elif event.key == pygame.K_r:
                            start_ticks = pygame.time.get_ticks()
                            paused_total = 0
                            paused_at = None
                            last_dendrite_update = -math.inf
                        elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                            stage_index = {
                                pygame.K_1: 0,
                                pygame.K_2: 1,
                                pygame.K_3: 2,
                            }[event.key]
                            active_visitor_limit = stage_limits[stage_index]
                            final_time = self._stage_final_time(active_visitor_limit)
                            # Selecting a cohort restarts its progressive growth,
                            # making the three accumulation stages directly
                            # comparable instead of instantly swapping snapshots.
                            start_ticks = pygame.time.get_ticks()
                            paused_total = 0
                            paused_at = None
                            last_dendrite_update = -math.inf
                        elif event.key == pygame.K_h:
                            show_overlay = not show_overlay
                        elif event.key == pygame.K_s:
                            pygame.image.save(screen, "growth_network_screenshot.png")

                now = paused_at if paused_at is not None else pygame.time.get_ticks()
                elapsed = max(0.0, (now - start_ticks - paused_total) / 1000.0)
                screen.fill(self.BACKGROUND)
                glow_surface.fill((0, 0, 0, 0))
                visible_curves: list[tuple[GrowthCurve, float, float]] = []
                for curve in primary_curves:
                    stage_fraction = self._curve_stage_fraction(
                        curve, active_visitor_limit
                    )
                    if stage_fraction <= 0.0:
                        continue
                    if elapsed < curve.start_time_seconds:
                        continue
                    progress = clamp(
                        (elapsed - curve.start_time_seconds)
                        / curve.growth_duration_seconds,
                        0.0,
                        1.0,
                    )
                    visible_curves.append((curve, progress, stage_fraction))

                # Hundreds of recursively generated dendrite segments change
                # much more slowly than the bright arterial growth tips. Cache
                # them on two transparent layers and refresh at a calm 6 Hz;
                # the main vessels and controls still render at the target FPS.
                if (
                    elapsed < last_dendrite_update
                    or elapsed - last_dendrite_update >= dendrite_update_interval
                ):
                    dendrite_glow_surface.fill((0, 0, 0, 0))
                    dendrite_core_surface.fill((0, 0, 0, 0))
                    cached_dendrite_visible = 0
                    for curve in dendrite_curves:
                        stage_fraction = self._curve_stage_fraction(
                            curve, active_visitor_limit
                        )
                        if stage_fraction <= 0.0:
                            continue
                        if elapsed < curve.start_time_seconds:
                            continue
                        cached_dendrite_visible += 1
                        progress = clamp(
                            (elapsed - curve.start_time_seconds)
                            / curve.growth_duration_seconds,
                            0.0,
                            1.0,
                        )
                        self._draw_curve(
                            pygame,
                            dendrite_glow_surface,
                            curve,
                            progress,
                            elapsed,
                            glow_only=True,
                            cohort_fraction=stage_fraction,
                        )
                        self._draw_curve(
                            pygame,
                            dendrite_core_surface,
                            curve,
                            progress,
                            elapsed,
                            glow_only=False,
                            cohort_fraction=stage_fraction,
                        )
                    last_dendrite_update = elapsed
                visible_count = len(visible_curves) + cached_dendrite_visible

                # A restrained additive red halo is drawn first, followed by
                # crisp flat strokes. No shaded body or inner tube is composited.
                screen.blit(
                    dendrite_glow_surface,
                    (0, 0),
                    special_flags=pygame.BLEND_RGBA_ADD,
                )
                for curve, progress, stage_fraction in visible_curves:
                    self._draw_curve(
                        pygame,
                        glow_surface,
                        curve,
                        progress,
                        elapsed,
                        glow_only=True,
                        cohort_fraction=stage_fraction,
                    )
                for marker in self.node_markers:
                    self._draw_node_marker(
                        pygame, glow_surface, marker, glow_only=True
                    )
                screen.blit(glow_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                screen.blit(dendrite_core_surface, (0, 0))
                for curve, progress, stage_fraction in visible_curves:
                    self._draw_curve(
                        pygame,
                        screen,
                        curve,
                        progress,
                        elapsed,
                        glow_only=False,
                        cohort_fraction=stage_fraction,
                    )

                for marker in self.node_markers:
                    self._draw_node_marker(pygame, screen, marker, glow_only=False)
                    self._draw_node_label(pygame, screen, marker, node_font)

                if show_overlay:
                    status = "PAUSED" if paused_at is not None else "GROWING"
                    if elapsed >= final_time:
                        status = "COMPLETE"
                    text = font.render(
                        f"{APP_NAME}  |  {status}  |  {visible_count}/{len(self.curves)} curves  "
                        f"|  visitors {active_visitor_limit}/{total_visitors}  "
                        "|  1 early  2 middle  3 final  SPACE pause  R restart  ESC quit",
                        True,
                        self.MUTED,
                    )
                    screen.blit(text, (18, self.config.height - 30))

                pygame.display.flip()
                clock.tick(self.config.fps)

                if elapsed >= final_time:
                    if loop:
                        start_ticks = pygame.time.get_ticks()
                        paused_total = 0
                        last_dendrite_update = -math.inf
                    elif hold_seconds >= 0.0 and elapsed >= final_time + hold_seconds:
                        running = False
        finally:
            pygame.quit()

    def _draw_curve(
        self,
        pygame: Any,
        surface: Any,
        curve: GrowthCurve,
        progress: float,
        elapsed: float,
        glow_only: bool,
        cohort_fraction: float = 1.0,
    ) -> None:
        if len(curve.screen_points) < 2 or progress <= 0.0:
            return
        exact_index = progress * (len(curve.screen_points) - 1)
        completed = min(int(exact_index), len(curve.screen_points) - 1)
        points = curve.screen_points[: completed + 1]
        if completed < len(curve.screen_points) - 1:
            partial = exact_index - completed
            points.append(interpolate(
                curve.screen_points[completed],
                curve.screen_points[completed + 1],
                partial,
            ))

        if curve.reinforcement_times:
            accumulated = sum(time <= elapsed for time in curve.reinforcement_times)
            reinforcement = accumulated / len(curve.reinforcement_times)
        else:
            reinforcement = 1.0
        if curve.branch_type == "artery":
            cohort_scale = 0.28 + 0.72 * math.sqrt(cohort_fraction)
        elif curve.branch_type == "repeated_path":
            cohort_scale = 0.42 + 0.58 * math.sqrt(cohort_fraction)
        elif curve.branch_type in {"dwell_dendrite", "route_dendrite"}:
            cohort_scale = 0.74 + 0.26 * cohort_fraction
        else:
            cohort_scale = 1.0
        live_thickness = (
            curve.thickness
            * (0.24 + 0.76 * reinforcement)
            * cohort_scale
        )
        age_after_growth = max(
            0.0,
            elapsed - curve.start_time_seconds - curve.growth_duration_seconds,
        )
        if curve.branch_type == "artery":
            retention = 1.0
        else:
            retention = curve.memory_floor + (1.0 - curve.memory_floor) * math.exp(
                -age_after_growth / self.config.trail_decay_seconds
            )
        brightness = clamp(
            curve.brightness
            * retention
            * (0.72 + 0.28 * cohort_fraction),
            0.0,
            1.0,
        )

        if curve.branch_type in {"dwell_dendrite", "route_dendrite"}:
            self._draw_dendrite_curve(
                pygame,
                surface,
                curve,
                points,
                progress,
                live_thickness,
                brightness,
                glow_only,
            )
            return

        # Batch each long centreline into a small number of tapered polylines,
        # leaving enough frame budget for the recursive capillary field.
        self._draw_primary_curve_batches(
            pygame,
            surface,
            curve,
            points,
            live_thickness,
            brightness,
            glow_only,
        )

        # The leading growth tip is slightly brighter, making the attraction-
        # guided extension legible during slow floor-projection animation.
        if progress < 0.999 and points:
            tip = (round(points[-1][0]), round(points[-1][1]))
            tip_thickness = live_thickness * (
                artery_width_profile(progress)
                if curve.branch_type == "artery"
                else 1.0
            )
            if glow_only:
                level = round(18 + 22 * brightness)
                pygame.draw.circle(
                    surface,
                    self._curve_glow_colour(curve, level, progress),
                    tip,
                    max(3, round(tip_thickness * 0.45) + 3),
                )
            else:
                intensity = round(185 + 70 * brightness)
                pygame.draw.circle(
                    surface,
                    self._curve_core_colour(curve, intensity, progress),
                    tip,
                    max(1, round(tip_thickness * 0.34)),
                )

    @staticmethod
    def _draw_rounded_polyline(
        pygame: Any,
        surface: Any,
        colour: tuple[int, ...],
        points: Sequence[tuple[int, int]],
        width: int,
        *,
        round_start: bool = True,
        round_end: bool = True,
    ) -> None:
        """Draw a joined antialiased stroke with optional circular end caps."""

        if len(points) < 2:
            return
        width = max(1, width)
        if width == 1:
            pygame.draw.aalines(surface, colour, False, points)
            return
        pygame.draw.lines(surface, colour, False, points, width)
        edge_distance = max(0.5, width * 0.5 - 0.35)
        for side in (-1.0, 1.0):
            edge_points: list[tuple[float, float]] = []
            for index, point in enumerate(points):
                previous = points[max(0, index - 1)]
                following = points[min(len(points) - 1, index + 1)]
                tangent_x = following[0] - previous[0]
                tangent_y = following[1] - previous[1]
                magnitude = max(1e-9, math.hypot(tangent_x, tangent_y))
                normal_x = -tangent_y / magnitude
                normal_y = tangent_x / magnitude
                edge_points.append((
                    point[0] + normal_x * edge_distance * side,
                    point[1] + normal_y * edge_distance * side,
                ))
            pygame.draw.aalines(surface, colour, False, edge_points)
        radius = max(1, width // 2)
        if round_start:
            pygame.draw.circle(surface, colour, points[0], radius)
        if round_end:
            pygame.draw.circle(surface, colour, points[-1], radius)

    def _draw_primary_curve_batches(
        self,
        pygame: Any,
        surface: Any,
        curve: GrowthCurve,
        points: Sequence[Vec2],
        live_thickness: float,
        brightness: float,
        glow_only: bool,
    ) -> None:
        """Draw one artery as a single flat red stroke with a restrained halo."""

        total_segments = len(points) - 1
        if total_segments < 1:
            return
        # More samples make the node-to-centre width profile visually continuous
        # while remaining inexpensive because only six arteries are rendered.
        batch_count = min(24, total_segments)
        full_denominator = max(1, len(curve.screen_points) - 1)
        batches: list[tuple[list[tuple[int, int]], int, float]] = []
        for batch_index in range(batch_count):
            start_index = round(batch_index * total_segments / batch_count)
            end_index = round((batch_index + 1) * total_segments / batch_count)
            end_index = max(start_index + 1, min(total_segments, end_index))
            t = (start_index + end_index) * 0.5 / full_denominator
            if curve.branch_type == "artery":
                taper = artery_width_profile(t)
            elif curve.branch_type == "repeated_path":
                taper = 0.58 + 0.42 * math.sin(math.pi * t)
            else:
                taper = 0.42 + 0.58 * math.sin(math.pi * t)
            core_width = max(1, round(live_thickness * taper))
            pixel_points = [
                (round(point[0]), round(point[1]))
                for point in points[start_index : end_index + 1]
            ]
            batches.append((pixel_points, core_width, t))

        if glow_only:
            for batch_index, (pixel_points, core_width, t) in enumerate(batches):
                # One low-energy support stroke keeps the result flat and avoids
                # the concentric layered appearance of a rendered pipe.
                halo_width = max(core_width + 2, round(core_width * 1.58))
                level = round(4 + 5 * brightness)
                self._draw_rounded_polyline(
                    pygame,
                    surface,
                    self._curve_glow_colour(curve, level, t),
                    pixel_points,
                    halo_width,
                    round_start=batch_index == 0,
                    round_end=batch_index == len(batches) - 1,
                )
            return

        if curve.branch_type == "artery":
            intensity = round(150 + 84 * brightness)
            for batch_index, (pixel_points, core_width, t) in enumerate(batches):
                self._draw_rounded_polyline(
                    pygame,
                    surface,
                    self._curve_core_colour(curve, intensity, t),
                    pixel_points,
                    core_width,
                    round_start=batch_index == 0,
                    round_end=batch_index == len(batches) - 1,
                )
            return

        intensity = round(82 + 165 * brightness)
        for batch_index, (pixel_points, core_width, t) in enumerate(batches):
            self._draw_rounded_polyline(
                pygame,
                surface,
                self._curve_core_colour(curve, intensity, t),
                pixel_points,
                core_width,
                round_start=batch_index == 0,
                round_end=batch_index == len(batches) - 1,
            )

    def _draw_dendrite_curve(
        self,
        pygame: Any,
        surface: Any,
        curve: GrowthCurve,
        points: Sequence[Vec2],
        progress: float,
        live_thickness: float,
        brightness: float,
        glow_only: bool,
    ) -> None:
        """Render one branch with continuous root-to-tip taper and fading."""

        pixel_points = [(round(point[0]), round(point[1])) for point in points]
        if len(pixel_points) < 2:
            return
        full_segment_count = max(1, len(curve.screen_points) - 1)
        last_colour: tuple[int, ...] = (0, 0, 0, 0) if glow_only else (0, 0, 0)
        last_width = 1
        for index, (first, second) in enumerate(zip(pixel_points, pixel_points[1:])):
            t = clamp((index + 0.5) / full_segment_count, 0.0, 1.0)
            width_factor = max(0.10, (1.0 - t) ** 0.68)
            if t <= 0.70:
                alpha_factor = 1.0
            else:
                alpha_factor = max(0.14, ((1.0 - t) / 0.30) ** 0.48)
            branch_width = max(
                1,
                math.ceil(live_thickness * width_factor - 0.25),
            )
            if glow_only:
                level = round((7 + 12 * brightness) * alpha_factor)
                last_width = max(
                    branch_width + 1,
                    round(branch_width + curve.glow_radius * (0.90 - 0.42 * t)),
                )
                last_colour = self._curve_glow_colour(curve, level, t)
            else:
                intensity = round((58 + 164 * brightness) * alpha_factor)
                last_width = branch_width
                last_colour = self._curve_core_colour(curve, intensity, t)
            self._draw_rounded_polyline(
                pygame,
                surface,
                last_colour,
                (first, second),
                last_width,
            )

        if progress < 0.999:
            tip = pixel_points[-1]
            pygame.draw.circle(
                surface,
                last_colour,
                tip,
                max(1, last_width // 2),
            )

    @staticmethod
    def _neural_palette(colour_bias: float) -> tuple[float, float, float]:
        """Return the fixed capillary-red basis retained by the legacy colour API."""

        _ = colour_bias
        return 255.0, 38.0, 25.0

    @staticmethod
    def _curve_colour_bias(curve: GrowthCurve, t: float) -> float:
        return (
            curve.source_colour_bias
            + (curve.target_colour_bias - curve.source_colour_bias) * clamp(t, 0.0, 1.0)
        )

    @classmethod
    def _curve_core_colour(
        cls,
        curve: GrowthCurve,
        intensity: int,
        t: float,
    ) -> tuple[int, int, int]:
        """Map luminance to restrained blood-red while keeping hue constant."""

        _ = (curve, t)
        strength = clamp(float(intensity) / 255.0, 0.0, 1.0)
        red = round(255.0 * (strength ** 0.88))
        return red, round(red * 0.15), round(red * 0.10)

    @classmethod
    def _curve_glow_colour(
        cls,
        curve: GrowthCurve,
        level: int,
        t: float,
    ) -> tuple[int, int, int, int]:
        """Create a subtle additive red halo with branch-specific strength."""

        _ = t
        gain = {
            "artery": 1.85,
            "repeated_path": 1.22,
            "visitor_trace": 0.76,
            "dwell_dendrite": 0.92,
            "route_dendrite": 0.92,
        }[curve.branch_type]
        value = min(255, round(max(0.0, level) * gain))
        return value, round(value * 0.08), round(value * 0.05), 255

    def _draw_node_marker(
        self, pygame: Any, surface: Any, marker: NodeMarker, glow_only: bool
    ) -> None:
        centre = (round(marker.screen_point[0]), round(marker.screen_point[1]))
        radius = max(3, round(marker.radius_pixels))
        if glow_only:
            strength = clamp(marker.brightness, 0.0, 1.0)
            # Nested low-energy discs accumulate into a soft radial bloom on
            # the additive layer. This approximates a luminous neural soma
            # without requiring an expensive per-frame blur operation.
            glow_steps = (
                (round(9 + 5 * strength), round(2 + 2 * strength)),
                (round(6 + 3 * strength), round(5 + 3 * strength)),
                (round(3 + 2 * strength), round(9 + 4 * strength)),
                (round(1 + strength), round(14 + 6 * strength)),
            )
            for level, extra_radius in reversed(glow_steps):
                value = min(255, round(level * 1.45))
                pygame.draw.circle(
                    surface,
                    (value, round(value * 0.08), round(value * 0.05), 255),
                    centre,
                    radius + extra_radius,
                )
            return

        # No outline or hollow ring: the node is a compact, filled origin from
        # which vessels appear to emerge.
        core_radius = radius
        shoulder = round(132 + 55 * marker.brightness)
        pygame.draw.circle(
            surface,
            (shoulder, round(shoulder * 0.14), round(shoulder * 0.09)),
            centre,
            core_radius + 1,
        )
        core = round(207 + 38 * marker.brightness)
        pygame.draw.circle(
            surface,
            (core, round(core * 0.16), round(core * 0.10)),
            centre,
            core_radius,
        )
        pygame.draw.circle(surface, (255, 52, 34), centre, 1)

    def _draw_node_label(
        self,
        pygame: Any,
        surface: Any,
        marker: NodeMarker,
        font: Any,
    ) -> None:
        """Label each glowing soma without adding a projection UI panel."""

        value = round(145 + 35 * marker.brightness)
        colour = (value, round(value * 0.17), round(value * 0.11))
        label = font.render(marker.node_id, True, colour)
        shadow = font.render(marker.node_id, True, (0, 0, 0))
        x = round(marker.screen_point[0] - label.get_width() / 2)
        y = round(marker.screen_point[1] + marker.radius_pixels + 8)
        surface.blit(shadow, (x + 1, y + 1))
        surface.blit(label, (x, y))


def build_argument_parser(script_dir: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="growth_network.py",
        description=(
            "Generate a visitor-attracted capillary network from museum-flow CSV files, "
            "render it with pygame, and export Blender-ready JSON."
        ),
    )
    parser.add_argument("--data-dir", type=Path, default=script_dir / "data",
                        help="Directory containing the six CSV files (default: ./data)")
    parser.add_argument("--output", type=Path, default=script_dir / "growth_network_curves.json",
                        help="Blender JSON output path")
    parser.add_argument("--width", type=int, default=1280, help="render width in pixels")
    parser.add_argument("--height", type=int, default=720, help="render height in pixels")
    parser.add_argument("--fps", type=int, default=30, help="render frame rate")
    parser.add_argument("--seed", type=int, default=42, help="reproducible Perlin-noise seed")
    parser.add_argument("--main-duration-scale", type=float, default=3.0,
                        help="main-vessel duration multiplier; larger values animate more slowly")
    parser.add_argument("--attraction-strength", type=float, default=0.56,
                        help="target-attraction and centreline smoothing, from 0 to 1")
    parser.add_argument("--curvature-strength", type=float, default=0.11,
                        help="organic lateral curvature, from 0.01 to 0.5")
    parser.add_argument("--capillary-density", type=float, default=0.85,
                        help="artery-rooted local branch density, from 0.5 to 2.0")
    parser.add_argument("--trail-decay", type=float, default=24.0,
                        help="seconds for older fine branches to settle into spatial memory")
    parser.add_argument("--memory-floor", type=float, default=0.24,
                        help="minimum retained luminance of old branches, from 0 to 1")
    parser.add_argument("--dendrite-density", type=float, default=1.35,
                        help="node-rooted neural branch density, from 0.25 to 2.0")
    parser.add_argument("--dendrite-length", type=float, default=0.90,
                        help="node-rooted neural branch length scale, from 0.4 to 1.8")
    parser.add_argument("--visitor-limit", type=int, default=None,
                        help="initial cumulative visitor cohort shown by pygame")
    parser.add_argument("--no-render", action="store_true",
                        help="validate, generate, and export without opening pygame")
    parser.add_argument("--validate-only", action="store_true",
                        help="validate the CSV datasets and exit")
    parser.add_argument("--hold", type=float, default=-1.0,
                        help="seconds to hold after completion; negative waits until quit")
    parser.add_argument("--loop", action="store_true", help="loop the growth animation")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    script_dir = Path(__file__).resolve().parent
    parser = build_argument_parser(script_dir)
    arguments = parser.parse_args(argv)
    try:
        if arguments.visitor_limit is not None and arguments.visitor_limit < 1:
            raise ValueError("--visitor-limit must be at least 1")
        data = DatasetLoader(arguments.data_dir).load()
        print("Validated datasets: " + ", ".join(
            f"{name}={count}" for name, count in data.summary().items()
        ))
        if arguments.validate_only:
            return 0

        config = GrowthConfig(
            width=arguments.width,
            height=arguments.height,
            fps=arguments.fps,
            seed=arguments.seed,
            main_route_duration_scale=arguments.main_duration_scale,
            attraction_strength=arguments.attraction_strength,
            curvature_strength=arguments.curvature_strength,
            capillary_density=arguments.capillary_density,
            trail_decay_seconds=arguments.trail_decay,
            memory_floor=arguments.memory_floor,
            dendrite_density=arguments.dendrite_density,
            dendrite_length_scale=arguments.dendrite_length,
        )
        config.validate()
        graph = FlowGraphBuilder().build(data)
        generator = VascularGrowthGenerator(graph, config)
        curves = generator.generate()
        node_markers = generator.generate_node_markers()
        if not curves:
            raise RuntimeError("No curves were generated from the validated graph")

        exporter = BlenderJsonExporter(config)
        exporter.export(arguments.output, graph, curves, node_markers, data)
        artery_count = sum(curve.branch_type == "artery" for curve in curves)
        dendrite_count = sum(
            curve.branch_type in {"dwell_dendrite", "route_dendrite"}
            for curve in curves
        )
        visitor_count = len(graph.graph.get("visitor_routes", []))
        print(
            f"Built directed analysis graph ({graph.number_of_nodes()} nodes, "
            f"{graph.number_of_edges()} edges); rendered {artery_count} single "
            f"centreline vessels with {dendrite_count} hierarchical capillary "
            f"segments for "
            f"{visitor_count} visitors."
        )
        print(f"Blender JSON: {arguments.output.expanduser().resolve()}")

        if not arguments.no_render:
            PygameGrowthRenderer(config, curves, node_markers).run(
                arguments.hold,
                arguments.loop,
                visitor_limit=arguments.visitor_limit,
            )
        return 0
    except (DataValidationError, DependencyError, ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
