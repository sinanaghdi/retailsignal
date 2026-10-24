import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "powerbi" / "RetailSignalProject"
MODEL = PROJECT / "RetailSignal.SemanticModel"
REPORT = PROJECT / "RetailSignal.Report"


def _unquote_tmdl_name(value: str) -> str:
    value = value.strip()
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def _model_objects() -> dict[str, dict[str, set[str]]]:
    objects: dict[str, dict[str, set[str]]] = {}
    for path in (MODEL / "definition" / "tables").glob("*.tmdl"):
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^table (.+)$", text, flags=re.MULTILINE)
        assert match, f"No top-level table declaration in {path}"
        table = _unquote_tmdl_name(match.group(1))
        columns = {
            _unquote_tmdl_name(name)
            for name in re.findall(r"^\tcolumn (.+)$", text, flags=re.MULTILINE)
        }
        measures = set(re.findall(r"^\tmeasure '(.+?)' =", text, flags=re.MULTILINE))
        objects[table] = {"columns": columns, "measures": measures}
    return objects


def _field_refs(value):
    if isinstance(value, dict):
        for field_type in ("Column", "Measure"):
            if field_type in value and isinstance(value[field_type], dict):
                field = value[field_type]
                source = field.get("Expression", {}).get("SourceRef", {})
                entity, prop = source.get("Entity"), field.get("Property")
                if entity and prop:
                    yield field_type, entity, prop
        for child in value.values():
            yield from _field_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _field_refs(child)


def test_pbip_and_report_json_files_are_valid_json():
    required = [
        PROJECT / "RetailSignal.pbip",
        MODEL / "definition.pbism",
        REPORT / "definition.pbir",
        REPORT / "definition" / "report.json",
        REPORT / "definition" / "version.json",
        REPORT / "definition" / "pages" / "pages.json",
    ]
    for file in required:
        assert file.is_file(), f"Missing PBIP source file: {file}"
    for file in PROJECT.rglob("*"):
        if file.is_file() and file.suffix in {".json", ".pbip", ".pbir", ".pbism"}:
            json.loads(file.read_text(encoding="utf-8"))


def test_pbip_report_pages_exist_and_page_order_is_consistent():
    page_index = json.loads((REPORT / "definition/pages/pages.json").read_text(encoding="utf-8"))
    assert len(page_index["pageOrder"]) == 5
    assert page_index["activePageName"] in page_index["pageOrder"]
    actual_ids = set()
    for page_file in (REPORT / "definition/pages").glob("*.Page/page.json"):
        page = json.loads(page_file.read_text(encoding="utf-8"))
        actual_ids.add(page["name"])
        assert page["width"] == 1280
        assert page["height"] == 720
    assert actual_ids == set(page_index["pageOrder"])


def test_visual_fields_reference_declared_model_columns_or_measures():
    model = _model_objects()
    visual_files = list((REPORT / "definition/pages").glob("*.Page/visuals/*.Visual/visual.json"))
    assert len(visual_files) >= 20
    for visual_file in visual_files:
        visual = json.loads(visual_file.read_text(encoding="utf-8"))
        for field_type, entity, prop in _field_refs(visual.get("visual", {}).get("query", {})):
            assert entity in model, f"{visual_file}: unknown model table {entity}"
            object_key = "measures" if field_type == "Measure" else "columns"
            assert prop in model[entity][object_key], (
                f"{visual_file}: {entity}.{prop} is not declared as a {object_key[:-1]}"
            )


def test_relationships_reference_existing_model_columns():
    model = _model_objects()
    relationships = (MODEL / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    for entity, col in re.findall(r"^\t(?:fromColumn|toColumn): ([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)$", relationships, re.MULTILINE):
        assert entity in model, f"Unknown relationship table {entity}"
        assert col in model[entity]["columns"], f"Unknown relationship column {entity}.{col}"


def test_report_references_the_local_semantic_model_folder():
    report_definition = json.loads((REPORT / "definition.pbir").read_text(encoding="utf-8"))
    relative = report_definition["datasetReference"]["byPath"]["path"]
    assert (REPORT / relative).resolve() == MODEL.resolve()
    pbip = json.loads((PROJECT / "RetailSignal.pbip").read_text(encoding="utf-8"))
    report_path = pbip["artifacts"][0]["report"]["path"]
    assert (PROJECT / report_path).is_dir()
