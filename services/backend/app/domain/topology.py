from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import TopologyEdge, TopologyPole, TransformerInfo


@dataclass
class PoleNode:
    pole_id: str
    dt_id: str
    feeder_id: str
    parent_id: str | None
    latitude: float
    longitude: float
    pincode: str | None
    edge_source: str
    edge_confidence: float
    children: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DistributionTree:
    dt_id: str
    feeder_id: str
    dt_latitude: float
    dt_longitude: float
    roots: tuple[str, ...]
    poles: dict[str, PoleNode]


def build_distribution_trees(
    transformers: list[TransformerInfo],
    poles: list[TopologyPole],
    edges: list[TopologyEdge],
) -> dict[str, DistributionTree]:
    edges_by_child: dict[str, TopologyEdge] = {edge.child_pole_id: edge for edge in edges}

    trees: dict[str, DistributionTree] = {}
    for transformer in transformers:
        dt_poles = [pole for pole in poles if pole.dt_id == transformer.dt_id]
        nodes: dict[str, PoleNode] = {}
        for pole in dt_poles:
            edge = edges_by_child.get(pole.pole_id)
            nodes[pole.pole_id] = PoleNode(
                pole_id=pole.pole_id,
                dt_id=pole.dt_id,
                feeder_id=pole.feeder_id,
                parent_id=edge.parent_pole_id if edge else None,
                latitude=pole.latitude,
                longitude=pole.longitude,
                pincode=pole.pincode,
                edge_source=edge.source if edge else "known",
                edge_confidence=edge.confidence if edge else 1.0,
            )

        for node in nodes.values():
            if node.parent_id and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node.pole_id)

        roots = tuple(node.pole_id for node in nodes.values() if node.parent_id is None)
        trees[transformer.dt_id] = DistributionTree(
            dt_id=transformer.dt_id,
            feeder_id=transformer.feeder_id,
            dt_latitude=transformer.latitude,
            dt_longitude=transformer.longitude,
            roots=roots,
            poles=nodes,
        )

    return trees
