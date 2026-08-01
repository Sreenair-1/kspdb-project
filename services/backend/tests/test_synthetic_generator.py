from collections import Counter, defaultdict

from app.synthetic.generator import SyntheticNetworkGenerator


def test_generator_creates_assignment_shaped_network() -> None:
    network = SyntheticNetworkGenerator().generate()

    assert len(network.feeders) == 31
    assert len(network.transformers) == 72
    assert len(network.poles) == 5_000
    assert len(network.topology_edges) == len(network.poles)

    instrumented_ratio = len(network.device_states) / len(network.poles)
    assert 0.89 <= instrumented_ratio <= 0.93

    missing_pincode_ratio = len([pole for pole in network.poles if pole.pincode is None]) / len(
        network.poles
    )
    assert 0.02 <= missing_pincode_ratio <= 0.04

    old_firmware_ratio = len(
        [device for device in network.device_states if device.firmware.startswith("1.2.")]
    ) / len(network.device_states)
    assert 0.06 <= old_firmware_ratio <= 0.10


def test_missing_topology_dts_have_null_registry_order_but_inferred_edges() -> None:
    network = SyntheticNetworkGenerator().generate()
    poles_by_dt = defaultdict(list)
    edges_by_dt = defaultdict(list)
    for pole in network.poles:
        poles_by_dt[pole.dt_id].append(pole)
    for edge in network.topology_edges:
        edges_by_dt[edge.dt_id].append(edge)

    inferred_dt_ids = {
        dt_id
        for dt_id, edges in edges_by_dt.items()
        if all(edge.source == "inferred" for edge in edges)
    }
    known_dt_ids = set(poles_by_dt) - inferred_dt_ids

    missing_topology_ratio = len(inferred_dt_ids) / len(poles_by_dt)
    assert 0.58 <= missing_topology_ratio <= 0.62

    for dt_id in inferred_dt_ids:
        assert all(pole.seq_on_line is None for pole in poles_by_dt[dt_id])
        assert all(pole.parent_pole_id is None for pole in poles_by_dt[dt_id])
        assert all(edge.confidence < 0.75 for edge in edges_by_dt[dt_id])

    for dt_id in known_dt_ids:
        assert all(pole.seq_on_line is not None for pole in poles_by_dt[dt_id])
        assert all(edge.confidence > 0.95 for edge in edges_by_dt[dt_id])


def test_each_transformer_has_radial_edge_shape() -> None:
    network = SyntheticNetworkGenerator().generate()
    child_counts = Counter(edge.child_pole_id for edge in network.topology_edges)
    roots_by_dt = Counter(
        edge.dt_id for edge in network.topology_edges if edge.parent_pole_id is None
    )
    pole_counts_by_dt = Counter(pole.dt_id for pole in network.poles)

    assert all(count == 1 for count in child_counts.values())
    assert all(count == 1 for count in roots_by_dt.values())
    assert all(9 <= count <= 240 for count in pole_counts_by_dt.values())
