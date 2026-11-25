"""Payload validation for platform configs, per category (and per key for PAYROLL_STATUTORY / FOLDER_TEMPLATES).

Shapes follow what ``app.seeds.config_rows()`` produces (the seeds must validate — see tests). Models allow extra
keys (forward compatible, the admin web keeps unknown keys on round-trips) but type-check the known ones.
Money/rates are decimal *strings* (never floats). Categories without a model accept any JSON object.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic.functional_validators import AfterValidator

from app.core.errors import ValidationFailedError
from app.core.money import DECIMAL_PATTERN
from app.core.permissions import validate_permission_map

Dec = Annotated[str, Field(pattern=DECIMAL_PATTERN, strict=True)]
OptDec = Dec | None


class _Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------- tax
class _Cess(_Loose):
    modes: list[str]


class _HsnDigits(_Loose):
    upto_5cr: int = Field(ge=0, le=8)
    above_5cr: int = Field(ge=0, le=8)


class _Rcm(_Loose):
    service: str
    rate: Dec


class GstSlabs(_Loose):
    rates: list[Dec] = Field(min_length=1)
    cess: _Cess
    eway_bill_threshold: Dec
    einvoice_aato_threshold: Dec
    b2cl_threshold: Dec
    hsn_digits: _HsnDigits
    rcm_common: list[_Rcm] = []


class _TdsSection(_Loose):
    kind: Literal["TDS", "TCS"]
    section: str = Field(min_length=1)
    nature: str
    threshold_single: OptDec = None
    threshold_annual: OptDec = None
    rate_individual: Dec
    rate_company: Dec
    rate_no_pan: Dec


class TdsSections(_Loose):
    due_day_of_next_month: int = Field(ge=1, le=31)
    march_due_date: str
    sections: list[_TdsSection] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> TdsSections:
        keys = [(s.kind, s.section) for s in self.sections]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate TDS/TCS section")
        return self


# ---------------------------------------------------------------- payroll statutory
class Epf(_Loose):
    wage_ceiling: Dec
    employee_rate: Dec
    employer_eps_rate: Dec
    employer_eps_cap: Dec
    employer_epf_rate: Dec
    edli_rate: Dec
    edli_cap: Dec
    admin_charges_rate: Dec
    admin_charges_min: Dec
    wage_components: list[str] = Field(min_length=1)
    mandatory_employee_count: int = Field(ge=0)


class Esic(_Loose):
    gross_ceiling: Dec
    gross_ceiling_disabled: OptDec = None
    employee_rate: Dec
    employer_rate: Dec
    employee_rounding: str


class _PtSlab(_Loose):
    min: Dec
    max: OptDec = None
    amount: Dec


class _PtState(_Loose):
    name: str
    frequency: str
    slabs: list[_PtSlab] = Field(min_length=1)
    deduction_months: list[Annotated[int, Field(ge=1, le=12)]] | None = None


class PtSlabs(_Loose):
    states: dict[Annotated[str, Field(pattern=r"^\d{2}$")], _PtState]


class _ItSlab(_Loose):
    from_: Dec = Field(alias="from")
    to: OptDec = None
    rate: Dec


class _Regime(_Loose):
    standard_deduction: Dec
    slabs: list[_ItSlab] = Field(min_length=1)
    rebate_87a: dict[str, Any] = {}
    surcharge: list[dict[str, Any]] = []


class IncomeTax(_Loose):
    fy: str | None = None
    cess_rate: Dec
    regimes: dict[Literal["NEW", "OLD"], _Regime]

    @model_validator(mode="after")
    def _both(self) -> IncomeTax:
        if "NEW" not in self.regimes:
            raise ValueError("regimes.NEW is required")
        return self


# ---------------------------------------------------------------- templates & roles
def _perm_map(v: dict[str, str]) -> dict[str, str]:
    return validate_permission_map(v)


class DefaultRole(_Loose):
    role_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    role_name: str = Field(min_length=1)
    is_external_collaborator: bool = False
    permissions: Annotated[dict[str, str], AfterValidator(_perm_map)]


class _Node(_Loose):
    id: str = Field(min_length=1)
    shape: Literal["OVAL", "RECTANGLE", "DIAMOND", "PARALLEL", "TERMINATOR"]
    label: str = ""


class _Edge(_Loose):
    source: str
    target: str


class _Graph(_Loose):
    nodes: list[_Node] = Field(min_length=1)
    edges: list[_Edge] = []

    @model_validator(mode="after")
    def _refs(self) -> _Graph:
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate node id")
        missing = [e for e in self.edges if e.source not in ids or e.target not in ids]
        if missing:
            raise ValueError("edge references an unknown node")
        return self


class IsoWorkflowTemplate(_Loose):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    iso_clause_ref: str | None = None
    graph_definition: _Graph


class _Block(_Loose):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    data: dict[str, Any] = {}


class DocReportTemplate(_Loose):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    blocks: list[_Block]


class _Folder(_Loose):
    name: str = Field(min_length=1, max_length=200)
    system_kind: str = Field(min_length=1)


class MonthlyFolders(_Loose):
    subfolders: list[_Folder]

    @model_validator(mode="after")
    def _system(self) -> MonthlyFolders:
        kinds = {f.system_kind for f in self.subfolders}
        if not {"BILLS", "OPERATIONS", "PAYROLL"} <= kinds:
            raise ValueError("subfolders must include the BILLS, OPERATIONS and PAYROLL system folders")
        return self


class MasterLibrary(_Folder):
    children: list[_Folder] = []


# (category, key) wins over (category, "*")
_MODELS: dict[tuple[str, str], type[BaseModel]] = {
    ("GST_SLABS", "*"): GstSlabs,
    ("TDS_SECTIONS", "*"): TdsSections,
    ("PAYROLL_STATUTORY", "EPF"): Epf,
    ("PAYROLL_STATUTORY", "ESIC"): Esic,
    ("PAYROLL_STATUTORY", "PT_SLABS"): PtSlabs,
    ("PAYROLL_STATUTORY", "INCOME_TAX"): IncomeTax,
    ("DEFAULT_ROLES", "*"): DefaultRole,
    ("ISO_WORKFLOW_TEMPLATES", "*"): IsoWorkflowTemplate,
    ("DOC_REPORT_TEMPLATES", "*"): DocReportTemplate,
    ("FOLDER_TEMPLATES", "MONTHLY"): MonthlyFolders,
    ("FOLDER_TEMPLATES", "MASTER_LIBRARY"): MasterLibrary,
}
# Also accept the payroll parts as stand-alone categories (brief/W4 naming), same models.
for _part in ("EPF", "ESIC", "PT_SLABS", "INCOME_TAX"):
    _MODELS[(_part, "*")] = _MODELS[("PAYROLL_STATUTORY", _part)]


def model_for(category: str, key: str) -> type[BaseModel] | None:
    return _MODELS.get((category, key)) or _MODELS.get((category, "*"))


def validate_payload(category: str, key: str, payload: Any) -> dict[str, Any]:
    """Raise VALIDATION_ERROR (400) with pydantic details when the payload does not fit its category."""
    if not isinstance(payload, dict):
        raise ValidationFailedError("payload must be a JSON object")
    model = model_for(category, key)
    if model is None:
        return payload
    try:
        model.model_validate(payload)
    except ValidationError as exc:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors(include_url=False)]
        raise ValidationFailedError(f"Invalid {category} payload: {errors[0]['msg']}", {"errors": errors[:20]}) from exc
    except ValueError as exc:  # pragma: no cover - permission map errors surface as ValidationError
        raise ValidationFailedError(str(exc)) from exc
    if category in ("ISO_WORKFLOW_TEMPLATES", "DOC_REPORT_TEMPLATES") and payload.get("key") != key:
        raise ValidationFailedError("payload.key must equal config_key")
    if category == "DEFAULT_ROLES" and payload.get("role_code") != key:
        raise ValidationFailedError("payload.role_code must equal config_key")
    return payload


PUSHABLE = frozenset({"ISO_WORKFLOW_TEMPLATES", "DOC_REPORT_TEMPLATES", "FOLDER_TEMPLATES", "DEFAULT_ROLES"})
