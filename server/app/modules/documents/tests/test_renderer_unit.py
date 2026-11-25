"""Pure unit tests for the template token renderer and folder-name rules."""

from __future__ import annotations

from app.modules.documents import renderer
from app.modules.documents.folders_rules import validate_folder_name, would_create_cycle
from app.seeds.doc_templates import DOC_REPORT_TEMPLATES


def _content(*texts: str) -> dict:
    return {"blocks": [{"id": f"b{i}", "type": "paragraph", "data": {"text": t}} for i, t in enumerate(texts)]}


def test_substitutes_known_tokens():
    out, warnings = renderer.render_content(_content("Item {{item.name}} on {{ today }}"),
                                            {"item.name": "Shaft", "today": "2026-09-01"})  # fmt: skip
    assert out["blocks"][0]["data"]["text"] == "Item Shaft on 2026-09-01"
    assert warnings == []


def test_unknown_token_renders_empty_with_warning():
    out, warnings = renderer.render_content(_content("A{{bogus.token}}B"), {})
    assert out["blocks"][0]["data"]["text"] == "AB"
    assert warnings == ["Unknown token {{bogus.token}}"]


def test_known_token_without_value_warns():
    out, warnings = renderer.render_content(_content("{{run.title}}", "{{run.title}}"), {})
    assert out["blocks"][1]["data"]["text"] == ""
    assert warnings == ["No value for {{run.title}} in this context"]


def test_dynamic_tokens_and_nested_data():
    content = {
        "blocks": [
            {
                "id": "k",
                "type": "kv",
                "data": {
                    "rows": [
                        {"label": "Rev", "value": "{{item.custom.drawing_rev}}"},
                        {"label": "Heat", "value": "{{step.qc.heat_no}}"},
                    ]
                },
            }
        ]
    }
    out, warnings = renderer.render_content(content, {"item.custom.drawing_rev": "C", "step.qc.heat_no": "H1"})
    rows = out["blocks"][0]["data"]["rows"]
    assert [r["value"] for r in rows] == ["C", "H1"] and warnings == []
    assert content["blocks"][0]["data"]["rows"][0]["value"] == "{{item.custom.drawing_rev}}"  # not mutated


def test_qc_table_expansion_and_text_summary():
    rows = [["OD", "25.00", "-0.02/+0.02", "25.01", "OK"]]
    content = {"blocks": [{"id": "q", "type": "qc_table", "data": {"source": "step", "text": "{{step.qc_readings}}"}}]}
    out, warnings = renderer.render_content(content, {}, qc_rows=rows)
    data = out["blocks"][0]["data"]
    assert data["columns"] == renderer.QC_COLUMNS and data["rows"] == rows
    assert data["text"] == "OD: 25.01 (OK)" and warnings == []
    _, warnings = renderer.render_content(content, {})
    assert "QC table needs a run step in the context" in warnings


def test_no_code_execution_in_tokens():
    out, warnings = renderer.render_content(_content("{{__class__.__mro__}} {{ 7*7 }}"), {})
    assert out["blocks"][0]["data"]["text"] == " {{ 7*7 }}"
    assert warnings == ["Unknown token {{__class__.__mro__}}"]


def test_every_system_template_token_is_known():
    for tpl in DOC_REPORT_TEMPLATES:
        unknown = [t for t in renderer.tokens_in({"blocks": tpl["blocks"]}) if not renderer.is_known_token(t)]
        assert not unknown, (tpl["key"], unknown)


def test_folder_name_rules():
    assert validate_folder_name("  QC Logs ") == "QC Logs"
    for bad in ("", "   ", "a/b", "..", "x" * 201, "a\\b"):
        assert validate_folder_name(bad) is None


def test_cycle_detection():
    parents = {"a": None, "b": "a", "c": "b"}
    assert would_create_cycle("a", "c", parents.get) is True  # move a under its grandchild
    assert would_create_cycle("c", "a", parents.get) is False
    assert would_create_cycle("b", "b", parents.get) is True
