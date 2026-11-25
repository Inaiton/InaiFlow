#!/usr/bin/env python3
"""Generate docs/api/openapi.json (+ contract index) from docs/api/contract.api.

Usage:  python docs/api/gen_openapi.py [--check]
  --check  exit 1 if the generated files differ from what is on disk (CI).
The generated OpenAPI carries `x-auth` and `x-permission` on every operation; the server's
tests/test_contract.py compares those against the live FastAPI app.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "contract.api"
OUT = HERE / "openapi.json"
INDEX = HERE / "contract_index.json"

DECIMAL = {"type": "string", "pattern": r"^-?\d+(\.\d{1,4})?$", "format": "decimal"}
SCALARS = {
    "str": {"type": "string"},
    "int": {"type": "integer"},
    "bool": {"type": "boolean"},
    "uuid": {"type": "string", "format": "uuid"},
    "date": {"type": "string", "format": "date"},
    "datetime": {"type": "string", "format": "date-time"},
    "decimal": DECIMAL,
    "email": {"type": "string", "format": "email"},
    "json": {},
    "any": {},
}


class ContractError(Exception):
    pass


def strip_comment(line: str) -> str:
    # comments start with '#' at line start or after whitespace (never inside our grammar tokens)
    return re.sub(r"(^|\s)#.*$", "", line).rstrip()


def parse(text: str):
    enums: dict[str, list[str]] = {}
    models: dict[str, dict] = {}
    endpoints: list[dict] = []
    tag = "default"
    for raw in text.splitlines():
        if raw.strip().startswith("# ----") and "--" in raw:
            m = re.search(r"-{3,}\s+(.+)$", raw.strip())
            if m:
                tag = m.group(1).split("(")[0].strip()
            continue
        line = strip_comment(raw)
        if not line.strip():
            continue
        s = line.strip()
        if s.startswith("enum "):
            m = re.fullmatch(r"enum\s+(\w+)\s*=\s*(.+)", s)
            if not m:
                raise ContractError(f"bad enum: {s}")
            if m.group(1) in enums:
                raise ContractError(f"duplicate enum {m.group(1)}")
            enums[m.group(1)] = [v.strip() for v in m.group(2).split("|")]
        elif s.startswith("model "):
            m = re.fullmatch(r"model\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{(.*)\}", s)
            if not m:
                raise ContractError(f"bad model: {s}")
            name, base, body = m.groups()
            fields = parse_fields(body, name)
            if name in models or name in enums:
                raise ContractError(f"duplicate model {name}")
            models[name] = {"base": base, "fields": fields}
        elif re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s", s):
            parts = [p.strip() for p in s.split("|")]
            if len(parts) != 5:
                raise ContractError(f"endpoint needs 5 parts: {s}")
            method, path = parts[0].split()
            endpoints.append(
                {
                    "method": method,
                    "path": path,
                    "auth": parts[1],
                    "query": parts[2],
                    "body": parts[3],
                    "resp": parts[4],
                    "tag": tag,
                }
            )
        else:
            raise ContractError(f"unrecognised line: {s}")
    return enums, models, endpoints


FIELD_RE = re.compile(r"(\w+)(\?)?\s*:\s*((?:[\w<>\[\]]+)(?:\s*\|\s*null)?)")


def parse_fields(body: str, model: str) -> list[dict]:
    out = []
    pos = 0
    body = body.strip()
    while pos < len(body):
        m = FIELD_RE.match(body, pos)
        if not m:
            raise ContractError(f"bad field in {model}: …{body[pos:pos+40]}")
        name, opt, typ = m.groups()
        nullable = typ.replace(" ", "").endswith("|null")
        typ = typ.split("|")[0].strip()
        out.append({"name": name, "optional": bool(opt), "nullable": nullable, "type": typ})
        pos = m.end()
        while pos < len(body) and body[pos].isspace():
            pos += 1
    return out


def type_schema(t: str, enums, models) -> dict:
    if t.endswith("[]"):
        return {"type": "array", "items": type_schema(t[:-2], enums, models)}
    m = re.fullmatch(r"map<(.+)>", t)
    if m:
        return {"type": "object", "additionalProperties": type_schema(m.group(1), enums, models)}
    m = re.fullmatch(r"Page<(\w+)>", t)
    if m:
        return {"$ref": f"#/components/schemas/Page_{m.group(1)}"}
    if t in SCALARS:
        return dict(SCALARS[t])
    if t in enums or t in models:
        return {"$ref": f"#/components/schemas/{t}"}
    raise ContractError(f"unknown type: {t}")


def all_fields(name, models):
    mdl = models[name]
    fields = []
    if mdl["base"]:
        if mdl["base"] not in models:
            raise ContractError(f"{name} extends unknown {mdl['base']}")
        fields.extend(all_fields(mdl["base"], models))
    names = {f["name"] for f in mdl["fields"]}
    fields = [f for f in fields if f["name"] not in names] + mdl["fields"]
    return fields


def model_schema(name, enums, models):
    props, required = {}, []
    for f in all_fields(name, models):
        sch = type_schema(f["type"], enums, models)
        if f["nullable"]:
            sch = {"anyOf": [sch, {"type": "null"}]}
        props[f["name"]] = sch
        if not f["optional"]:
            required.append(f["name"])
    out = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        out["required"] = required
    return out


def parse_auth(auth: str) -> dict:
    a = auth.split()
    if a[0] in ("public", "user", "cron"):
        return {"kind": a[0]}
    if a[0] == "org":
        if len(a) != 2:
            raise ContractError(f"bad org auth: {auth}")
        if a[1] == "member":
            return {"kind": "org", "permission": None, "level": None}
        key, level = a[1].split(":")
        if level not in ("NONE", "READ", "WRITE", "FULL"):
            raise ContractError(f"bad level in {auth}")
        return {"kind": "org", "permission": key, "level": level}
    if a[0] == "admin":
        return {"kind": "admin", "roles": a[1].split(",")}
    raise ContractError(f"bad auth: {auth}")


def op_id(method, path):
    segs = [s for s in path.strip("/").split("/") if s]
    clean = []
    for s in segs:
        if s.startswith("{"):
            clean.append("by_" + s.strip("{}").split(":")[0])
        else:
            clean.append(re.sub(r"[^a-zA-Z0-9]", "_", s))
    return method.lower() + "_" + "_".join(clean)


def build(enums, models, endpoints):
    pages = set()
    for ep in endpoints:
        for m in re.finditer(r"Page<(\w+)>", ep["resp"]):
            pages.add(m.group(1))
    for mdl in models.values():
        for f in mdl["fields"]:
            for m in re.finditer(r"Page<(\w+)>", f["type"]):
                pages.add(m.group(1))

    schemas = {}
    for e, vals in enums.items():
        schemas[e] = {"type": "string", "enum": vals}
    for name in models:
        schemas[name] = model_schema(name, enums, models)
    for p in sorted(pages):
        if p not in models:
            raise ContractError(f"Page<{p}> of unknown model")
        schemas[f"Page_{p}"] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["items", "total", "limit", "offset"],
            "properties": {
                "items": {"type": "array", "items": {"$ref": f"#/components/schemas/{p}"}},
                "total": {"type": "integer"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
            },
        }

    paths: dict = {}
    index = []
    seen = set()
    for ep in endpoints:
        method, path = ep["method"], ep["path"]
        key = (method, path)
        if key in seen:
            raise ContractError(f"duplicate endpoint {method} {path}")
        seen.add(key)
        auth = parse_auth(ep["auth"])
        oapi_path = "/api/v1" + re.sub(r"\{(\w+)(?::\w+)?\}", r"{\1}", path)
        params = []
        for pm in re.finditer(r"\{(\w+)(?::(\w+))?\}", path):
            pname, ptype = pm.group(1), pm.group(2) or "uuid"
            params.append({"name": pname, "in": "path", "required": True, "schema": type_schema(ptype, enums, models)})
        if ep["query"] != "-":
            for q in ep["query"].split():
                qm = re.fullmatch(r"(\w+)(\?)?:(\w+)", q)
                if not qm:
                    raise ContractError(f"bad query param {q} in {method} {path}")
                qn, qopt, qt = qm.groups()
                sch = type_schema(qt, enums, models)
                if qn == "limit":
                    sch = {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}
                if qn == "offset":
                    sch = {"type": "integer", "minimum": 0, "default": 0}
                params.append({"name": qn, "in": "query", "required": not qopt, "schema": sch})
        if auth["kind"] == "org":
            params.append(
                {"name": "X-Organization-ID", "in": "header", "required": True, "schema": {"type": "string", "format": "uuid"}}
            )
            if method in ("POST", "PUT"):
                params.append(
                    {"name": "Idempotency-Key", "in": "header", "required": False, "schema": {"type": "string", "maxLength": 100}}
                )
        op = {
            "operationId": op_id(method, path),
            "summary": f"{method} {path}",
            "tags": [ep["tag"]],
            "x-auth": auth["kind"],
            "parameters": params,
            "responses": {},
        }
        if auth["kind"] == "org":
            op["x-permission"] = None if auth["permission"] is None else f"{auth['permission']}:{auth['level']}"
        if auth["kind"] == "admin":
            op["x-admin-roles"] = auth["roles"]
        if auth["kind"] in ("user", "org"):
            op["security"] = [{"userBearer": []}]
        elif auth["kind"] == "admin":
            op["security"] = [{"adminBearer": []}]
        elif auth["kind"] == "cron":
            op["security"] = [{"cronBearer": []}]
        else:
            op["security"] = []
        body = ep["body"]
        if body == "multipart":
            op["requestBody"] = {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {"file": {"type": "string", "format": "binary"}},
                        }
                    }
                },
            }
        elif body != "-":
            if body not in models:
                raise ContractError(f"unknown body model {body} in {method} {path}")
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{body}"}}}}
        resp = ep["resp"]
        rm = re.fullmatch(r"(\d{3})(?:\s+(.+))?", resp)
        if not rm:
            raise ContractError(f"bad response {resp}")
        status, rtype = rm.group(1), rm.group(2)
        if rtype is None:
            op["responses"][status] = {"description": "No content" if status == "204" else "Redirect"}
        else:
            fm = re.fullmatch(r"file\((.+)\)", rtype)
            if fm:
                op["responses"][status] = {
                    "description": "File",
                    "content": {mime.strip(): {"schema": {"type": "string", "format": "binary"}} for mime in fm.group(1).split(",")},
                }
            else:
                op["responses"][status] = {
                    "description": "OK",
                    "content": {"application/json": {"schema": type_schema(rtype, enums, models)}},
                }
        op["responses"]["default"] = {
            "description": "Error",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        }
        paths.setdefault(oapi_path, {})[method.lower()] = op
        index.append(
            {
                "method": method,
                "path": oapi_path,
                "auth": auth["kind"],
                "permission": op.get("x-permission"),
                "admin_roles": op.get("x-admin-roles"),
                "status": int(status),
                "request": None if body in ("-",) else body,
                "response": rtype,
            }
        )

    spec = {
        "openapi": "3.1.0",
        "info": {"title": "InaiFlow API", "version": "1.0.0", "description": "Generated from docs/api/contract.api — do not edit."},
        "servers": [{"url": "/"}],
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "userBearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
                "adminBearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
                "cronBearer": {"type": "http", "scheme": "bearer"},
            },
        },
    }
    return spec, index


def main() -> int:
    enums, models, endpoints = parse(SRC.read_text(encoding="utf-8"))
    spec, index = build(enums, models, endpoints)
    out = json.dumps(spec, indent=2, sort_keys=False) + "\n"
    idx = json.dumps(index, indent=2) + "\n"
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text() == out and INDEX.exists() and INDEX.read_text() == idx
        print("contract up to date" if ok else "contract out of date: run python docs/api/gen_openapi.py")
        return 0 if ok else 1
    OUT.write_text(out)
    INDEX.write_text(idx)
    print(f"{len(endpoints)} operations, {len(models)} models, {len(enums)} enums -> {OUT.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
