from app.domain.localization import FaultLocalizer
from app.domain.models import PoleObservation, TopologyEdge, TopologyPole, TransformerInfo


def _line_topology() -> tuple[list[TransformerInfo], list[TopologyPole], list[TopologyEdge]]:
    transformer = TransformerInfo(
        dt_id="D-0001",
        feeder_id="F-07-01",
        latitude=12.9716,
        longitude=77.5946,
    )
    poles = [
        TopologyPole("P-000001", "D-0001", "F-07-01", 12.9717, 77.5947, "560078"),
        TopologyPole("P-000002", "D-0001", "F-07-01", 12.9718, 77.5948, "560078"),
        TopologyPole("P-000003", "D-0001", "F-07-01", 12.9719, 77.5949, "560078"),
        TopologyPole("P-000004", "D-0001", "F-07-01", 12.9720, 77.5950, "560078"),
    ]
    edges = [
        TopologyEdge("F-07-01", "D-0001", None, "P-000001", "known", 0.98),
        TopologyEdge("F-07-01", "D-0001", "P-000001", "P-000002", "known", 0.98),
        TopologyEdge("F-07-01", "D-0001", "P-000002", "P-000003", "known", 0.98),
        TopologyEdge("F-07-01", "D-0001", "P-000003", "P-000004", "known", 0.98),
    ]
    return [transformer], poles, edges


def _branch_topology() -> tuple[list[TransformerInfo], list[TopologyPole], list[TopologyEdge]]:
    transformer = TransformerInfo(
        dt_id="D-0002",
        feeder_id="F-07-02",
        latitude=12.9616,
        longitude=77.5846,
    )
    poles = [
        TopologyPole("P-000101", "D-0002", "F-07-02", 12.9617, 77.5847, "560070"),
        TopologyPole("P-000102", "D-0002", "F-07-02", 12.9618, 77.5848, "560070"),
        TopologyPole("P-000103", "D-0002", "F-07-02", 12.9619, 77.5849, "560070"),
        TopologyPole("P-000104", "D-0002", "F-07-02", 12.9620, 77.5850, "560070"),
        TopologyPole("P-000105", "D-0002", "F-07-02", 12.9621, 77.5851, "560070"),
    ]
    edges = [
        TopologyEdge("F-07-02", "D-0002", None, "P-000101", "known", 0.98),
        TopologyEdge("F-07-02", "D-0002", "P-000101", "P-000102", "known", 0.98),
        TopologyEdge("F-07-02", "D-0002", "P-000102", "P-000103", "known", 0.98),
        TopologyEdge("F-07-02", "D-0002", "P-000102", "P-000104", "known", 0.98),
        TopologyEdge("F-07-02", "D-0002", "P-000104", "P-000105", "known", 0.98),
    ]
    return [transformer], poles, edges


def test_span_fault_on_simple_line() -> None:
    transformers, poles, edges = _line_topology()
    observations = [
        PoleObservation("P-000001", "live"),
        PoleObservation("P-000002", "live"),
        PoleObservation("P-000003", "dark"),
        PoleObservation("P-000004", "dark"),
    ]

    faults = FaultLocalizer().localize(transformers, poles, edges, observations)

    assert len(faults) == 1
    fault = faults[0]
    assert fault.incident_type == "span"
    assert fault.upstream_pole_id == "P-000002"
    assert fault.downstream_pole_id == "P-000003"
    assert fault.affected_poles == 2
    assert fault.pincode == "560078"
    assert fault.confidence >= 0.9


def test_dt_fault_when_all_poles_dark() -> None:
    transformers, poles, edges = _line_topology()
    observations = [PoleObservation(pole.pole_id, "dark") for pole in poles]

    faults = FaultLocalizer().localize(transformers, poles, edges, observations)

    assert len(faults) == 1
    fault = faults[0]
    assert fault.incident_type == "dt"
    assert fault.dt_id == "D-0001"
    assert fault.affected_poles == 4


def test_sensor_fault_is_not_reported_as_outage() -> None:
    transformer = TransformerInfo("D-0003", "F-07-03", 12.9516, 77.5746)
    poles = [
        TopologyPole("P-000201", "D-0003", "F-07-03", 12.9517, 77.5747, "560004"),
        TopologyPole("P-000202", "D-0003", "F-07-03", 12.9518, 77.5748, "560004"),
        TopologyPole("P-000203", "D-0003", "F-07-03", 12.9519, 77.5749, "560004"),
        TopologyPole("P-000204", "D-0003", "F-07-03", 12.9520, 77.5750, "560004"),
    ]
    edges = [
        TopologyEdge("F-07-03", "D-0003", None, "P-000201", "known", 0.98),
        TopologyEdge("F-07-03", "D-0003", "P-000201", "P-000202", "known", 0.98),
        TopologyEdge("F-07-03", "D-0003", "P-000202", "P-000203", "known", 0.98),
        TopologyEdge("F-07-03", "D-0003", "P-000203", "P-000204", "known", 0.98),
    ]
    observations = [
        PoleObservation("P-000201", "live"),
        PoleObservation("P-000202", "live"),
        PoleObservation("P-000203", "dark"),
        PoleObservation("P-000204", "live"),
    ]

    faults = FaultLocalizer().localize([transformer], poles, edges, observations)

    assert faults == []


def test_two_simultaneous_span_faults_on_branches() -> None:
    transformers, poles, edges = _branch_topology()
    observations = [
        PoleObservation("P-000101", "live"),
        PoleObservation("P-000102", "live"),
        PoleObservation("P-000103", "dark"),
        PoleObservation("P-000104", "live"),
        PoleObservation("P-000105", "dark"),
    ]

    faults = FaultLocalizer().localize(transformers, poles, edges, observations)

    assert len(faults) == 2
    boundaries = {
        (fault.upstream_pole_id, fault.downstream_pole_id)
        for fault in faults
        if fault.incident_type == "span"
    }
    assert boundaries == {("P-000102", "P-000103"), ("P-000104", "P-000105")}


def test_inferred_topology_lowers_confidence() -> None:
    transformers, poles, edges = _line_topology()
    edges = [
        TopologyEdge("F-07-01", "D-0001", None, "P-000001", "inferred", 0.68),
        TopologyEdge("F-07-01", "D-0001", "P-000001", "P-000002", "inferred", 0.68),
        TopologyEdge("F-07-01", "D-0001", "P-000002", "P-000003", "inferred", 0.68),
        TopologyEdge("F-07-01", "D-0001", "P-000003", "P-000004", "inferred", 0.68),
    ]
    observations = [
        PoleObservation("P-000001", "live"),
        PoleObservation("P-000002", "live"),
        PoleObservation("P-000003", "dark"),
        PoleObservation("P-000004", "dark"),
    ]

    faults = FaultLocalizer().localize(transformers, poles, edges, observations)

    assert len(faults) == 1
    assert faults[0].confidence <= 0.72
    assert any("inferred" in reason.lower() for reason in faults[0].confidence_reasons)


def test_feeder_fault_when_all_dts_are_dark() -> None:
    transformer_a = TransformerInfo("D-0101", "F-07-10", 12.9516, 77.5746)
    transformer_b = TransformerInfo("D-0102", "F-07-10", 12.9526, 77.5756)
    poles = [
        TopologyPole("P-010001", "D-0101", "F-07-10", 12.9517, 77.5747, "560004"),
        TopologyPole("P-010002", "D-0101", "F-07-10", 12.9518, 77.5748, "560004"),
        TopologyPole("P-010101", "D-0102", "F-07-10", 12.9527, 77.5757, "560011"),
        TopologyPole("P-010102", "D-0102", "F-07-10", 12.9528, 77.5758, "560011"),
    ]
    edges = [
        TopologyEdge("F-07-10", "D-0101", None, "P-010001", "known", 0.98),
        TopologyEdge("F-07-10", "D-0101", "P-010001", "P-010002", "known", 0.98),
        TopologyEdge("F-07-10", "D-0102", None, "P-010101", "known", 0.98),
        TopologyEdge("F-07-10", "D-0102", "P-010101", "P-010102", "known", 0.98),
    ]
    observations = [PoleObservation(pole.pole_id, "dark") for pole in poles]

    faults = FaultLocalizer().localize([transformer_a, transformer_b], poles, edges, observations)

    assert len(faults) == 1
    assert faults[0].incident_type == "feeder"
    assert faults[0].feeder_id == "F-07-10"
    assert faults[0].dt_id is None
    assert faults[0].affected_poles == 4


def test_unknown_boundary_reports_fuzzy_span_fault() -> None:
    """Live → uninstrumented → dark: fault must not be silently dropped."""
    transformers, poles, edges = _line_topology()
    # P-000002 has no observation (uninstrumented)
    observations = [
        PoleObservation("P-000001", "live"),
        PoleObservation("P-000003", "dark"),
        PoleObservation("P-000004", "dark"),
    ]

    faults = FaultLocalizer().localize(transformers, poles, edges, observations)

    assert len(faults) == 1
    fault = faults[0]
    assert fault.incident_type == "span"
    assert fault.upstream_pole_id == "P-000001"
    assert fault.downstream_pole_id == "P-000003"
    assert fault.confidence <= 0.55
    assert any("uninstrumented" in r for r in fault.confidence_reasons)


def test_unknown_boundary_through_multiple_unknowns() -> None:
    """Live → unknown → unknown → dark: BFS must cross multiple uninstrumented poles."""
    transformers, poles, edges = _line_topology()
    # P-000002 and P-000003 have no observations
    observations = [
        PoleObservation("P-000001", "live"),
        PoleObservation("P-000004", "dark"),
    ]

    faults = FaultLocalizer().localize(transformers, poles, edges, observations)

    assert len(faults) == 1
    fault = faults[0]
    assert fault.incident_type == "span"
    assert fault.upstream_pole_id == "P-000001"
    assert fault.downstream_pole_id == "P-000004"
    assert fault.confidence <= 0.55


def test_affected_count_includes_unknown_poles_downstream() -> None:
    """dark(P3) → unknown(P4): P4 is downstream of the fault and must be counted."""
    transformer = TransformerInfo("D-0010", "F-07-10", 12.9716, 77.5946)
    poles = [
        TopologyPole("P-010001", "D-0010", "F-07-10", 12.9717, 77.5947, "560078"),
        TopologyPole("P-010002", "D-0010", "F-07-10", 12.9718, 77.5948, "560078"),
        TopologyPole("P-010003", "D-0010", "F-07-10", 12.9719, 77.5949, "560078"),
        TopologyPole("P-010004", "D-0010", "F-07-10", 12.9720, 77.5950, "560078"),
    ]
    edges = [
        TopologyEdge("F-07-10", "D-0010", None, "P-010001", "known", 0.98),
        TopologyEdge("F-07-10", "D-0010", "P-010001", "P-010002", "known", 0.98),
        TopologyEdge("F-07-10", "D-0010", "P-010002", "P-010003", "known", 0.98),
        TopologyEdge("F-07-10", "D-0010", "P-010003", "P-010004", "known", 0.98),
    ]
    # P-010004 has no observation (unknown/uninstrumented) but is downstream of dark P-010003
    observations = [
        PoleObservation("P-010001", "live"),
        PoleObservation("P-010002", "live"),
        PoleObservation("P-010003", "dark"),
    ]

    faults = FaultLocalizer().localize([transformer], poles, edges, observations)

    assert len(faults) == 1
    fault = faults[0]
    assert fault.incident_type == "span"
    assert fault.upstream_pole_id == "P-010002"
    assert fault.downstream_pole_id == "P-010003"
    # P-010003 (dark) + P-010004 (unknown, downstream of fault) = 2 affected
    assert fault.affected_poles == 2


def test_affected_count_includes_dark_beyond_unknown() -> None:
    """dark(P3) → unknown(P4) → dark(P5): all three must be counted as affected."""
    transformer = TransformerInfo("D-0011", "F-07-11", 12.9716, 77.5946)
    poles = [
        TopologyPole("P-011001", "D-0011", "F-07-11", 12.9717, 77.5947, "560078"),
        TopologyPole("P-011002", "D-0011", "F-07-11", 12.9718, 77.5948, "560078"),
        TopologyPole("P-011003", "D-0011", "F-07-11", 12.9719, 77.5949, "560078"),
        TopologyPole("P-011004", "D-0011", "F-07-11", 12.9720, 77.5950, "560078"),
        TopologyPole("P-011005", "D-0011", "F-07-11", 12.9721, 77.5951, "560078"),
    ]
    edges = [
        TopologyEdge("F-07-11", "D-0011", None, "P-011001", "known", 0.98),
        TopologyEdge("F-07-11", "D-0011", "P-011001", "P-011002", "known", 0.98),
        TopologyEdge("F-07-11", "D-0011", "P-011002", "P-011003", "known", 0.98),
        TopologyEdge("F-07-11", "D-0011", "P-011003", "P-011004", "known", 0.98),
        TopologyEdge("F-07-11", "D-0011", "P-011004", "P-011005", "known", 0.98),
    ]
    # P-011004 has no observation; P-011005 is dark — both are downstream of the fault
    observations = [
        PoleObservation("P-011001", "live"),
        PoleObservation("P-011002", "live"),
        PoleObservation("P-011003", "dark"),
        PoleObservation("P-011005", "dark"),
    ]

    faults = FaultLocalizer().localize([transformer], poles, edges, observations)

    assert len(faults) == 1
    fault = faults[0]
    assert fault.upstream_pole_id == "P-011002"
    assert fault.downstream_pole_id == "P-011003"
    # P-011003 (dark) + P-011004 (unknown) + P-011005 (dark) = 3 affected
    assert fault.affected_poles == 3
