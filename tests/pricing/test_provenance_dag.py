"""Round 6 Phase 16: PricingProvenanceGraph DAG reverse closure."""

from __future__ import annotations

from valor.pricing.provenance import PricingProvenanceGraph, ResolvedParameter


def _graph():
    g = PricingProvenanceGraph()
    g.add_many([
        ResolvedParameter("w_b_rem", 100.0, "CONTRACT_INPUT"),
        ResolvedParameter("v_gross_lower", 50.0, "CALIBRATION"),
        ResolvedParameter("p_max", 90.0, "COMPUTED", formula_id="PMAX"),
        ResolvedParameter("p_min", 10.0, "COMPUTED", formula_id="PMIN"),
        ResolvedParameter("clearing_price", 50.0, "COMPUTED", formula_id="CLEAR_TRADE"),
        ResolvedParameter("P_star", 50.0, "COMPUTED", formula_id="CLEAR_TRADE"),
    ])
    g.root = "P_star"
    g.add_edge("clearing_price", "P_star", "root")
    g.add_edge("p_max", "clearing_price", "upper")
    g.add_edge("p_min", "clearing_price", "lower")
    g.add_edge("w_b_rem", "p_max", "input")
    g.add_edge("v_gross_lower", "p_max", "input")
    return g


def test_reverse_reaches_leaves():
    g = _graph()
    closure = g.reverse("P_star")
    assert "w_b_rem" in closure
    assert "v_gross_lower" in closure
    assert "p_max" in closure
    assert "p_min" in closure
    assert g.to_plain()["reverse_P_star"] == sorted(closure)


def test_unresolved_leaf_marked_incomplete():
    g = _graph()
    g.add(ResolvedParameter("mystery", 1.0, "UNKNOWN", formula_id="X"))
    g.add_edge("mystery", "p_min", "input")
    assert "mystery" in g.unresolved_leaves()


def test_graph_hash_binds_edges():
    g1 = _graph()
    g2 = _graph()
    assert g1.graph_hash() == g2.graph_hash()
    g2.add_edge("w_b_rem", "clearing_price", "extra")
    assert g1.graph_hash() != g2.graph_hash()
