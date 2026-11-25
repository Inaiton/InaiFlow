"""Library ISO 9001 workflow templates (ISO_WORKFLOW_TEMPLATES). Graph format = contract ``WorkflowGraph``.

Each graph uses all five ISO flowchart shapes. Diamond gates evaluate ``qc_fields`` (nominal/tolerances as
decimal strings) with ``pass_criteria.mode = ALL_IN_TOLERANCE``; rejected units go to Scrap + NCR
(``reject_action = SCRAP_NCR``); REWORK edges loop back.
"""

from __future__ import annotations


def _node(nid: str, shape: str, label: str, x: int, y: int, **config: object) -> dict:
    return {"id": nid, "shape": shape, "label": label, "position": {"x": str(x), "y": str(y)}, "config": config}


def _edge(src: str, dst: str, branch: str = "PASS", label: str | None = None) -> dict:
    return {"id": f"e-{src}-{dst}-{branch.lower()}", "source": src, "target": dst, "branch": branch, "label": label}


def _qc(key: str, label: str, nominal: str, minus: str, plus: str, unit: str = "mm") -> dict:
    return {"key": key, "label": label, "type": "NUMBER", "unit": unit, "nominal": nominal,
            "tol_minus": minus, "tol_plus": plus, "required": True}  # fmt: skip


INCOMING_MATERIAL_INSPECTION = {
    "key": "incoming-material-inspection",
    "name": "Incoming Material Inspection",
    "description": "Goods receipt, identification, parallel lab & dimensional checks and accept/reject gate.",
    "iso_clause_ref": "8.4",
    "graph_definition": {
        "nodes": [
            _node("start", "OVAL", "Goods Receipt (GRN)", 0, 0, trigger="ON_GRN"),
            _node("receive", "RECTANGLE", "Receive & Identify Material", 0, 120,
                  assigned_role_code="OPERATOR", std_cycle_time_mins="15",
                  qc_fields=[{"key": "heat_no", "label": "Heat / Batch No.", "type": "TEXT", "required": True}]),
            _node("checks", "PARALLEL", "Lab Test + Dimensional Check", 0, 240,
                  assigned_role_code="QA_LEAD", instrument_required=True,
                  notes="Material test certificate verification runs alongside dimensional checks."),
            _node("gate", "DIAMOND", "Accept / Reject", 0, 360,
                  assigned_role_code="QA_LEAD", instrument_required=True,
                  qc_fields=[_qc("thickness", "Sheet thickness", "2.00", "0.05", "0.05"),
                             _qc("hardness", "Hardness", "45", "3", "3", unit="HRC"),
                             {"key": "visual_ok", "label": "Visual inspection OK", "type": "BOOL", "required": True}],
                  pass_criteria={"mode": "ALL_IN_TOLERANCE", "expression": None},
                  reject_action="SCRAP_NCR"),
            _node("release", "TERMINATOR", "Release to Raw Material Store", 0, 480, commit_godown_id=None),
        ],
        "edges": [_edge("start", "receive"), _edge("receive", "checks"), _edge("checks", "gate"),
                  _edge("gate", "release", "PASS", "Accepted")],
    },
}  # fmt: skip

CNC_MACHINING_FINAL_INSPECTION = {
    "key": "cnc-machining-final-inspection",
    "name": "CNC Machining with Final Inspection",
    "description": "Material issue, CNC turning with in-process QC, deburr & coating, final inspection.",
    "iso_clause_ref": "8.5.1",
    "graph_definition": {
        "nodes": [
            _node("start", "OVAL", "Start Period Run", 0, 0, trigger="SCHEDULED_PERIOD_START"),
            _node("issue", "RECTANGLE", "Material Issue to Shop Floor", 0, 120,
                  assigned_role_code="OPERATOR", std_cycle_time_mins="10"),
            _node("cnc", "RECTANGLE", "CNC Turning", 0, 240,
                  assigned_role_code="OPERATOR", machine="CNC-01", std_cycle_time_mins="6",
                  instrument_required=True),
            _node("ipqc", "DIAMOND", "In-process QC", 0, 360,
                  assigned_role_code="QA_LEAD", instrument_required=True,
                  qc_fields=[_qc("od", "Outer diameter", "25.00", "0.02", "0.02"),
                             _qc("length", "Overall length", "120.0", "0.1", "0.1"),
                             _qc("ra", "Surface roughness Ra", "1.2", "1.2", "0.4", unit="µm")],
                  pass_criteria={"mode": "ALL_IN_TOLERANCE", "expression": None},
                  reject_action="SCRAP_NCR"),
            _node("finish", "PARALLEL", "Deburr + Coating", 0, 480,
                  assigned_role_code="OPERATOR", std_cycle_time_mins="4"),
            _node("final", "DIAMOND", "Final Inspection", 0, 600,
                  assigned_role_code="QA_LEAD", instrument_required=True,
                  qc_fields=[_qc("od_final", "Outer diameter (final)", "25.00", "0.02", "0.02"),
                             _qc("coating", "Coating thickness", "12", "2", "3", unit="µm")],
                  pass_criteria={"mode": "ALL_IN_TOLERANCE", "expression": None},
                  reject_action="SCRAP_NCR"),
            _node("commit", "TERMINATOR", "Commit Finished Goods", 0, 720),
        ],
        "edges": [_edge("start", "issue"), _edge("issue", "cnc"), _edge("cnc", "ipqc"),
                  _edge("ipqc", "finish", "PASS", "Within tolerance"),
                  _edge("ipqc", "cnc", "REWORK", "Re-machine"),
                  _edge("finish", "final"),
                  _edge("final", "commit", "PASS", "Accepted"),
                  _edge("final", "finish", "REWORK", "Re-coat")],
    },
}  # fmt: skip

ASSEMBLY_AND_TEST = {
    "key": "assembly-and-test",
    "name": "Assembly & Test",
    "description": "Kitting, sub-assembly, parallel leak & electrical tests, functional gate and packing.",
    "iso_clause_ref": "8.6",
    "graph_definition": {
        "nodes": [
            _node("start", "OVAL", "Start Assembly Batch", 0, 0, trigger="MANUAL"),
            _node("kit", "RECTANGLE", "Kit Components (BOM)", 0, 120, assigned_role_code="OPERATOR",
                  std_cycle_time_mins="5"),
            _node("subassy", "RECTANGLE", "Sub-assembly", 0, 240, assigned_role_code="OPERATOR",
                  std_cycle_time_mins="12"),
            _node("tests", "PARALLEL", "Leak Test + Electrical Test", 0, 360, assigned_role_code="QA_LEAD",
                  instrument_required=True,
                  qc_fields=[_qc("leak_rate", "Leak rate", "0.5", "0.5", "0.5", unit="ml/min"),
                             _qc("insulation", "Insulation resistance", "100", "0", "900", unit="MΩ")]),
            _node("functional", "DIAMOND", "Functional Test", 0, 480, assigned_role_code="QA_LEAD",
                  qc_fields=[_qc("torque", "Output torque", "4.5", "0.3", "0.3", unit="Nm"),
                             {"key": "noise_ok", "label": "Noise within limit", "type": "BOOL", "required": True}],
                  pass_criteria={"mode": "ALL_IN_TOLERANCE", "expression": None},
                  reject_action="SCRAP_NCR"),
            _node("pack", "RECTANGLE", "Packing & Labelling", 0, 600, assigned_role_code="OPERATOR",
                  skippable=True),
            _node("done", "TERMINATOR", "Commit to Finished Goods", 0, 720),
        ],
        "edges": [_edge("start", "kit"), _edge("kit", "subassy"), _edge("subassy", "tests"),
                  _edge("tests", "functional"),
                  _edge("functional", "pack", "PASS", "Pass"),
                  _edge("functional", "subassy", "REWORK", "Rework"),
                  _edge("pack", "done")],
    },
}  # fmt: skip

ISO_WORKFLOW_TEMPLATES: list[dict] = [
    INCOMING_MATERIAL_INSPECTION,
    CNC_MACHINING_FINAL_INSPECTION,
    ASSEMBLY_AND_TEST,
]
