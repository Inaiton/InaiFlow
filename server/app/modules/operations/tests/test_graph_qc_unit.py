"""Pure unit tests: graph validation, topological order, readings / Quick QC, pass criteria, expressions."""

from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from app.modules.operations import graph as g
from app.modules.operations import qc
from app.seeds.iso_workflows import ISO_WORKFLOW_TEMPLATES


def _n(nid, shape, **config):  # noqa: ANN001,ANN202
    return {"id": nid, "shape": shape, "label": nid.title(), "position": {"x": "0", "y": "0"}, "config": config}


def _e(s, t, branch="PASS"):  # noqa: ANN001,ANN202
    return {"id": f"{s}-{t}-{branch}", "source": s, "target": t, "branch": branch}


FIELD = {"key": "od", "label": "OD", "type": "NUMBER", "nominal": "25.00", "tol_minus": "0.02", "tol_plus": "0.02",
         "required": True}  # fmt: skip


def linear():  # noqa: ANN201
    return {
        "nodes": [_n("start", "OVAL"), _n("cut", "RECTANGLE"),
                  _n("qc", "DIAMOND", qc_fields=[FIELD], pass_criteria={"mode": "ALL_FIELDS_IN_TOLERANCE"}),
                  _n("end", "TERMINATOR")],
        "edges": [_e("start", "cut"), _e("cut", "qc"), _e("qc", "end"), _e("qc", "cut", "REWORK")],
    }  # fmt: skip


def messages(res: g.ValidationResult) -> list[str]:
    return [i.message for i in res.errors]


# ---------------------------------------------------------------- validation
@pytest.mark.parametrize("tpl", ISO_WORKFLOW_TEMPLATES, ids=lambda t: t["key"])
def test_library_templates_are_valid(tpl):  # noqa: ANN001
    res = g.validate_graph(tpl["graph_definition"])
    assert res.valid, messages(res)


def test_valid_linear_graph():
    assert g.validate_graph(linear()).valid


def test_requires_start_and_terminator():
    graph = {"nodes": [_n("a", "RECTANGLE")], "edges": []}
    msgs = messages(g.validate_graph(graph))
    assert any("Start" in m for m in msgs) and any("End" in m for m in msgs)


def test_duplicate_node_ids_and_dangling_edges():
    graph = linear()
    graph["nodes"].append(_n("cut", "RECTANGLE"))
    graph["edges"].append(_e("cut", "ghost"))
    msgs = messages(g.validate_graph(graph))
    assert any("Duplicate node id" in m for m in msgs)
    assert any("does not exist" in m for m in msgs)


def test_unreachable_node():
    graph = linear()
    graph["nodes"].append(_n("orphan", "RECTANGLE"))
    graph["edges"].append(_e("orphan", "end"))
    res = g.validate_graph(graph)
    assert any(i.node_id == "orphan" and "reachable" in i.message for i in res.errors)


def test_diamond_needs_pass_edge():
    graph = linear()
    graph["edges"] = [e for e in graph["edges"] if not (e["source"] == "qc" and e["branch"] == "PASS")]
    graph["edges"].append(_e("qc", "end", "REJECT"))
    assert any("PASS edge" in m for m in messages(g.validate_graph(graph)))


def test_reject_edge_optional():
    assert g.validate_graph(linear()).valid  # no REJECT edge at all


def test_rework_must_target_upstream():
    graph = linear()
    graph["nodes"].insert(3, _n("pack", "RECTANGLE"))
    graph["edges"] = [_e("start", "cut"), _e("cut", "qc"), _e("qc", "pack"), _e("pack", "end"),
                      _e("cut", "pack", "REWORK")]  # fmt: skip
    assert any("upstream" in m for m in messages(g.validate_graph(graph)))


def test_forward_cycle_rejected():
    graph = linear()
    graph["edges"].append(_e("qc", "cut", "PASS"))
    assert any("loop" in m for m in messages(g.validate_graph(graph)))


def test_qc_field_keys_unique_and_tolerances_numeric():
    graph = linear()
    bad = dict(FIELD, tol_plus="abc")
    graph["nodes"][2]["config"]["qc_fields"] = [FIELD, dict(FIELD), dict(bad, key="x")]
    msgs = messages(g.validate_graph(graph))
    assert any("Duplicate QC field key" in m for m in msgs)
    assert any("numeric" in m for m in msgs)


def test_expression_criteria_validated():
    graph = linear()
    graph["nodes"][2]["config"]["pass_criteria"] = {"mode": "EXPRESSION", "expression": "od > 24.9 and zz < 1"}
    assert any("unknown fields" in m for m in messages(g.validate_graph(graph)))
    graph["nodes"][2]["config"]["pass_criteria"] = {"mode": "EXPRESSION", "expression": "od > (24.9"}
    assert any("Invalid expression" in m for m in messages(g.validate_graph(graph)))


def test_dead_end_step():
    graph = linear()
    graph["nodes"].append(_n("side", "RECTANGLE"))
    graph["edges"].append(_e("cut", "side"))
    assert any(i.node_id == "side" and "dead end" in i.message for i in g.validate_graph(graph).errors)


# ---------------------------------------------------------------- topological order
def test_topological_order_ignores_rework_edges():
    assert g.topological_order(linear()) == ["start", "cut", "qc", "end"]


def test_topological_order_parallel_branches_keep_node_order():
    graph = {
        "nodes": [_n("end", "TERMINATOR"), _n("b", "RECTANGLE"), _n("a", "RECTANGLE"), _n("s", "OVAL")],
        "edges": [_e("s", "a"), _e("s", "b"), _e("a", "end"), _e("b", "end")],
    }
    assert g.topological_order(graph) == ["s", "b", "a", "end"]


def test_topological_order_library():
    tpl = copy.deepcopy(ISO_WORKFLOW_TEMPLATES[1]["graph_definition"])
    order = g.topological_order(tpl)
    assert order[0] == "start" and order[-1] == "commit" and order.index("ipqc") < order.index("final")


def test_routing_lookups():
    graph = linear()
    assert g.pass_targets(graph, "qc") == ["end"]
    assert g.rework_target(graph, "qc") == "cut"
    assert g.rework_target(graph, "cut") is None
    assert g.start_nodes(graph) == ["start"]


# ---------------------------------------------------------------- readings & quick QC
def test_quick_qc_autofills_nominal():
    r = qc.build_readings([FIELD], None, quick_qc=True)
    assert r == {"od": {"value": "25.00", "in_tolerance": True, "auto_filled": True}}


def test_omitted_measurement_with_nominal_autofills_without_flag():
    r = qc.build_readings([FIELD, {"key": "len", "type": "NUMBER", "nominal": "120"}], {"len": "120.5"},
                          quick_qc=False)  # fmt: skip
    assert r["od"]["auto_filled"] is True and r["od"]["in_tolerance"] is True
    assert r["len"] == {"value": "120.5", "in_tolerance": False, "auto_filled": False}


def test_measurement_tolerance_bounds():
    assert qc.build_readings([FIELD], {"od": "25.02"}, quick_qc=False)["od"]["in_tolerance"] is True
    assert qc.build_readings([FIELD], {"od": "24.97"}, quick_qc=False)["od"]["in_tolerance"] is False


def test_bool_and_text_fields():
    fields = [{"key": "ok", "type": "BOOL", "required": True}, {"key": "heat", "type": "TEXT", "required": True}]
    quick = qc.build_readings(fields, None, quick_qc=True)
    assert quick["ok"]["value"] == "true" and quick["heat"]["value"] is None
    with pytest.raises(qc.ReadingError):
        qc.build_readings(fields, {"ok": "yes"}, quick_qc=False)  # heat required
    r = qc.build_readings(fields, {"ok": "no", "heat": "H-12"}, quick_qc=False)
    assert r["ok"]["in_tolerance"] is False and r["heat"]["in_tolerance"] is None


def test_bad_number_and_unknown_field():
    with pytest.raises(qc.ReadingError):
        qc.build_readings([FIELD], {"od": "abc"}, quick_qc=False)
    with pytest.raises(qc.ReadingError):
        qc.build_readings([FIELD], {"zz": "1"}, quick_qc=False)


# ---------------------------------------------------------------- pass criteria
def test_all_in_tolerance_modes():
    ok = qc.build_readings([FIELD], {"od": "25.01"}, quick_qc=False)
    bad = qc.build_readings([FIELD], {"od": "25.10"}, quick_qc=False)
    for mode in ("ALL_FIELDS_IN_TOLERANCE", "ALL_IN_TOLERANCE"):
        assert qc.evaluate_pass_criteria({"mode": mode}, ok) is True
        assert qc.evaluate_pass_criteria({"mode": mode}, bad) is False
    assert qc.evaluate_pass_criteria(None, ok) is True


def test_accepted_gt_zero():
    assert qc.evaluate_pass_criteria({"mode": "ACCEPTED_GT_ZERO"}, {}, accepted=Decimal(1)) is True
    assert qc.evaluate_pass_criteria({"mode": "ACCEPTED_GT_ZERO"}, {}, accepted=Decimal(0)) is False


def test_expression_mode():
    fields = [FIELD, {"key": "ok", "type": "BOOL"}]
    readings = qc.build_readings(fields, {"od": "25.01", "ok": "yes"}, quick_qc=False)
    crit = {"mode": "EXPRESSION", "expression": "od >= 24.98 && od <= 25.02 and ok == true and accepted > 0"}
    assert qc.evaluate_pass_criteria(crit, readings, qc_fields=fields, accepted=Decimal(5)) is True
    assert qc.evaluate_pass_criteria(crit, readings, qc_fields=fields, accepted=Decimal(0)) is False
    crit2 = {"mode": "EXPRESSION", "expression": "not (od > 25) or rejected == 0"}
    assert qc.evaluate_pass_criteria(crit2, readings, qc_fields=fields) is True


@pytest.mark.parametrize("src", ["__import__('os')", "od + 1 > 2", "od > ", "1 > 2)", "a.b > 1", "x = 1"])
def test_expression_rejects_code(src):  # noqa: ANN001
    with pytest.raises(qc.ExpressionError):
        qc.evaluate_expression(src, {"od": Decimal(1), "x": Decimal(1)})


def test_expression_missing_values_are_false_and_negative_numbers():
    assert qc.evaluate_expression("missing > 1", {}) is False
    assert qc.evaluate_expression("t > -0.5", {"t": Decimal("-0.1")}) is True


def test_deeply_nested_expression_is_rejected():
    import pytest

    from app.modules.operations.qc import ExpressionError, parse_expression

    with pytest.raises(ExpressionError):
        parse_expression("(" * 400 + "1" + ")" * 400)
