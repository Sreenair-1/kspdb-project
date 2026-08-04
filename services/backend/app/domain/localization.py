from __future__ import annotations

from collections import defaultdict

from app.domain.models import (
    LocalizedFault,
    PoleObservation,
    TopologyEdge,
    TopologyPole,
    TransformerInfo,
)
from app.domain.topology import DistributionTree, build_distribution_trees


class FaultLocalizer:
    """Find live/dark fault boundaries on radial distribution trees."""

    def localize(
        self,
        transformers: list[TransformerInfo],
        poles: list[TopologyPole],
        edges: list[TopologyEdge],
        observations: list[PoleObservation],
    ) -> list[LocalizedFault]:
        trees = build_distribution_trees(transformers, poles, edges)
        state_by_pole = {observation.pole_id: observation for observation in observations}
        faults: list[LocalizedFault] = []
        trees_by_feeder: dict[str, list[DistributionTree]] = defaultdict(list)
        for tree in trees.values():
            trees_by_feeder[tree.feeder_id].append(tree)

        for feeder_id, feeder_trees in trees_by_feeder.items():
            feeder_fault = self._feeder_fault(feeder_id, feeder_trees, state_by_pole)
            if feeder_fault is not None:
                faults.append(feeder_fault)
                continue

            for tree in feeder_trees:
                faults.extend(self._localize_tree(tree, state_by_pole))

        return faults

    def _feeder_fault(
        self,
        feeder_id: str,
        trees: list[DistributionTree],
        state_by_pole: dict[str, PoleObservation],
    ) -> LocalizedFault | None:
        observed_poles: list[tuple[str, str]] = []
        for tree in trees:
            for pole_id in tree.poles:
                observation = state_by_pole.get(pole_id)
                if observation is not None and observation.state != "unknown":
                    observed_poles.append((pole_id, observation.state))

        if len(trees) < 2:
            return None
        if len(observed_poles) < 3:
            return None
        if any(state == "live" for _, state in observed_poles):
            return None
        if not all(state == "dark" for _, state in observed_poles):
            return None

        affected = sum(len(tree.poles) for tree in trees)
        latitude = sum(tree.dt_latitude for tree in trees) / len(trees)
        longitude = sum(tree.dt_longitude for tree in trees) / len(trees)
        return LocalizedFault(
            incident_type="feeder",
            feeder_id=feeder_id,
            dt_id=None,
            upstream_pole_id=None,
            downstream_pole_id=None,
            latitude=round(latitude, 6),
            longitude=round(longitude, 6),
            pincode=self._representative_pincode(trees, state_by_pole),
            affected_poles=affected,
            confidence=0.88,
            confidence_reasons=[
                "All reporting poles across every DT on the feeder are dark.",
                "No live pole remains beneath this feeder.",
            ],
        )

    def _localize_tree(
        self,
        tree: DistributionTree,
        state_by_pole: dict[str, PoleObservation],
    ) -> list[LocalizedFault]:
        sensor_poles = self._sensor_fault_poles(tree, state_by_pole)
        observed_states = {
            pole_id: observation.state
            for pole_id, observation in state_by_pole.items()
            if pole_id in tree.poles and observation.state != "unknown"
        }
        if not observed_states:
            return []

        if all(state == "dark" for state in observed_states.values()):
            return [self._dt_fault(tree, state_by_pole)]

        faults: list[LocalizedFault] = []
        for pole_id, node in tree.poles.items():
            if pole_id in sensor_poles:
                continue
            if not self._is_live(pole_id, state_by_pole):
                continue
            for child_id in node.children:
                if child_id in sensor_poles:
                    continue
                if self._is_dark(child_id, state_by_pole):
                    faults.append(
                        self._span_fault(
                            tree=tree,
                            upstream_pole_id=pole_id,
                            downstream_pole_id=child_id,
                            state_by_pole=state_by_pole,
                        )
                    )
                elif self._is_unknown(child_id, state_by_pole):
                    # Child is uninstrumented — walk through unknowns to find first dark pole.
                    # Report a fuzzy boundary rather than silently dropping the fault.
                    dark_id = self._find_dark_through_unknowns(
                        tree, child_id, state_by_pole, sensor_poles
                    )
                    if dark_id:
                        faults.append(
                            self._unknown_boundary_span(
                                tree=tree,
                                upstream_pole_id=pole_id,
                                downstream_pole_id=dark_id,
                                state_by_pole=state_by_pole,
                            )
                        )
        return faults

    def _is_unknown(self, pole_id: str, state_by_pole: dict[str, PoleObservation]) -> bool:
        obs = state_by_pole.get(pole_id)
        return obs is None or obs.state == "unknown"

    def _find_dark_through_unknowns(
        self,
        tree: DistributionTree,
        pole_id: str,
        state_by_pole: dict[str, PoleObservation],
        sensor_poles: set[str],
    ) -> str | None:
        """BFS through uninstrumented poles to find the nearest dark descendant."""
        queue = [pole_id]
        visited: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in visited or current in sensor_poles:
                continue
            visited.add(current)
            if self._is_dark(current, state_by_pole):
                return current
            if self._is_unknown(current, state_by_pole) and current in tree.poles:
                queue.extend(tree.poles[current].children)
        return None

    def _unknown_boundary_span(
        self,
        tree: DistributionTree,
        upstream_pole_id: str,
        downstream_pole_id: str,
        state_by_pole: dict[str, PoleObservation],
    ) -> LocalizedFault:
        upstream = tree.poles[upstream_pole_id]
        downstream = tree.poles[downstream_pole_id]
        latitude, longitude = self._span_coordinates(upstream, downstream)
        affected = self._count_dark_descendants(tree, downstream_pole_id, state_by_pole)
        confidence = round(
            min(upstream.edge_confidence, downstream.edge_confidence, 0.55), 2
        )
        return LocalizedFault(
            incident_type="span",
            feeder_id=tree.feeder_id,
            dt_id=tree.dt_id,
            upstream_pole_id=upstream_pole_id,
            downstream_pole_id=downstream_pole_id,
            latitude=latitude,
            longitude=longitude,
            pincode=downstream.pincode or upstream.pincode,
            affected_poles=affected,
            confidence=confidence,
            confidence_reasons=[
                f"Live/dark boundary between {upstream_pole_id} and {downstream_pole_id}.",
                f"{affected} downstream poles are dark.",
                "Fault location is approximate: one or more poles between the boundary are uninstrumented.",
            ],
        )

    def _sensor_fault_poles(
        self,
        tree: DistributionTree,
        state_by_pole: dict[str, PoleObservation],
    ) -> set[str]:
        sensor_poles: set[str] = set()
        for pole_id in tree.poles:
            if not self._is_dark(pole_id, state_by_pole):
                continue
            if self._has_live_descendant(tree, pole_id, state_by_pole):
                sensor_poles.add(pole_id)
        return sensor_poles

    def _has_live_descendant(
        self,
        tree: DistributionTree,
        pole_id: str,
        state_by_pole: dict[str, PoleObservation],
    ) -> bool:
        stack = list(tree.poles[pole_id].children)
        while stack:
            current = stack.pop()
            if self._is_live(current, state_by_pole):
                return True
            stack.extend(tree.poles[current].children)
        return False

    def _dt_fault(
        self,
        tree: DistributionTree,
        state_by_pole: dict[str, PoleObservation],
    ) -> LocalizedFault:
        downstream = tree.roots[0] if tree.roots else None
        pincode = tree.poles[downstream].pincode if downstream else None
        return LocalizedFault(
            incident_type="dt",
            feeder_id=tree.feeder_id,
            dt_id=tree.dt_id,
            upstream_pole_id=None,
            downstream_pole_id=downstream,
            latitude=tree.dt_latitude,
            longitude=tree.dt_longitude,
            pincode=pincode,
            affected_poles=len(tree.poles),
            confidence=0.9,
            confidence_reasons=[
                "Every reporting pole under this DT is dark.",
                "No live/dark boundary exists beneath the transformer.",
            ],
        )

    def _span_fault(
        self,
        tree: DistributionTree,
        upstream_pole_id: str,
        downstream_pole_id: str,
        state_by_pole: dict[str, PoleObservation],
    ) -> LocalizedFault:
        upstream = tree.poles[upstream_pole_id]
        downstream = tree.poles[downstream_pole_id]
        latitude, longitude = self._span_coordinates(upstream, downstream)
        affected = self._count_dark_descendants(tree, downstream_pole_id, state_by_pole)
        confidence, reasons = self._span_confidence(upstream, downstream, affected, state_by_pole)
        return LocalizedFault(
            incident_type="span",
            feeder_id=tree.feeder_id,
            dt_id=tree.dt_id,
            upstream_pole_id=upstream_pole_id,
            downstream_pole_id=downstream_pole_id,
            latitude=latitude,
            longitude=longitude,
            pincode=downstream.pincode or upstream.pincode,
            affected_poles=affected,
            confidence=confidence,
            confidence_reasons=reasons,
        )

    def _span_confidence(
        self,
        upstream,
        downstream,
        affected: int,
        state_by_pole: dict[str, PoleObservation],
    ) -> tuple[float, list[str]]:
        confidence = min(upstream.edge_confidence, downstream.edge_confidence)
        reasons: list[str] = [
            f"Live/dark boundary between {upstream.pole_id} and {downstream.pole_id}.",
            f"{affected} downstream poles are dark.",
        ]
        if downstream.edge_source == "inferred" or upstream.edge_source == "inferred":
            confidence = min(confidence, 0.72)
            reasons.append("Topology for this DT was inferred rather than recorded.")
        else:
            confidence = min(confidence, 0.96)
            reasons.append("Boundary uses recorded pole ordering.")

        upstream_obs = state_by_pole.get(upstream.pole_id)
        downstream_obs = state_by_pole.get(downstream.pole_id)
        if upstream_obs and downstream_obs:
            confidence = min(confidence, upstream_obs.confidence, downstream_obs.confidence)
        return round(confidence, 2), reasons

    def _count_dark_descendants(
        self,
        tree: DistributionTree,
        pole_id: str,
        state_by_pole: dict[str, PoleObservation],
    ) -> int:
        count = 1 if self._is_dark(pole_id, state_by_pole) else 0
        for child_id in tree.poles[pole_id].children:
            if self._subtree_is_dark(tree, child_id, state_by_pole):
                count += self._count_tree_poles(tree, child_id)
        return count

    def _subtree_is_dark(
        self,
        tree: DistributionTree,
        pole_id: str,
        state_by_pole: dict[str, PoleObservation],
    ) -> bool:
        if not self._is_dark(pole_id, state_by_pole):
            return False
        return all(
            self._subtree_is_dark(tree, child_id, state_by_pole)
            for child_id in tree.poles[pole_id].children
        )

    def _count_tree_poles(self, tree: DistributionTree, pole_id: str) -> int:
        child_count = sum(
            self._count_tree_poles(tree, child) for child in tree.poles[pole_id].children
        )
        return 1 + child_count

    def _span_coordinates(self, upstream, downstream) -> tuple[float, float]:
        latitude = round((upstream.latitude + downstream.latitude) / 2, 6)
        longitude = round((upstream.longitude + downstream.longitude) / 2, 6)
        return latitude, longitude

    def _representative_pincode(
        self,
        trees: list[DistributionTree],
        state_by_pole: dict[str, PoleObservation],
    ) -> str | None:
        for tree in trees:
            for pole_id in tree.poles:
                pincode = tree.poles[pole_id].pincode
                if pincode is not None:
                    return pincode
        return None

    def _is_live(self, pole_id: str, state_by_pole: dict[str, PoleObservation]) -> bool:
        observation = state_by_pole.get(pole_id)
        return observation is not None and observation.state == "live"

    def _is_dark(self, pole_id: str, state_by_pole: dict[str, PoleObservation]) -> bool:
        observation = state_by_pole.get(pole_id)
        return observation is not None and observation.state == "dark"
