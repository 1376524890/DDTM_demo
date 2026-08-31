"""Round 7: cross-mechanism reverse provenance validator."""

from valor.provenance.reverse import ProvenanceNode, ReverseProvenanceValidator


def test_reverse_provenance_reaches_leaves():
    v = ReverseProvenanceValidator()
    nodes = [
        ProvenanceNode("P_star", "h1", "pricing", "clearing", "COMPUTED"),
        ProvenanceNode("p_min", "h2", "pricing", "seller_min", "COMPUTED"),
        ProvenanceNode("audit_pay_s", "h3", "pricing", "audit", "AUDIT"),
        ProvenanceNode("cert", "h4", "certificate", "R_cert", "CERTIFIED"),
        ProvenanceNode("likelihood", "h5", "likelihood", "R_cal", "CALIBRATION"),
    ]
    for n in nodes:
        v.add_node(n)
    v.add_edge("audit_pay_s", "p_min")
    v.add_edge("p_min", "P_star")
    v.add_edge("cert", "p_min")
    v.add_edge("likelihood", "cert")
    r = v.validate()
    assert r.path_results["P_star_to_pricing_leaves"]["passed"] is True


def test_reverse_provenance_flags_missing_leaf():
    v = ReverseProvenanceValidator()
    v.add_node(ProvenanceNode("P_star", "h1", "pricing", "clearing", "COMPUTED"))
    v.add_node(ProvenanceNode("p_min", "h2", "pricing", "seller_min", "COMPUTED"))
    v.add_edge("p_min", "P_star")
    r = v.validate()
    assert r.required_paths_failed > 0
    assert r.unresolved_leaves
