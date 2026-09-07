"""Formal candidate schema. Decimal/date values stay strings, never floats.

This schema is private document data, never a diagnostic or an approved bill.
Coordinates are PDF points, top-left origin, after the recorded page rotation.
"""
from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

HEADER_FIELDS = ('provider', 'invoice_number', 'account_identifier', 'service_address',
                 'invoice_date', 'due_date', 'currency', 'invoice_total', 'previous_balance',
                 'amount_due', 'document_kind', 'supplier_only', 'delivery_only')
SERVICE_FIELDS = ('meter_identifier', 'building', 'utility_type', 'period_start', 'period_end',
                  'consumption_quantity', 'consumption_unit', 'demand_quantity', 'demand_unit',
                  'delivery_quantity', 'quantity_treatment', 'reading_type', 'previous_reading',
                  'current_reading', 'current_charge', 'supply_charge', 'delivery_charge',
                  'demand_charge', 'taxes', 'fees', 'credits')
MONEY_FIELDS = {'invoice_total', 'previous_balance', 'amount_due', 'current_charge',
                'supply_charge', 'delivery_charge', 'demand_charge', 'taxes', 'fees', 'credits'}
NUMBER_FIELDS = {'consumption_quantity', 'demand_quantity', 'delivery_quantity',
                 'previous_reading', 'current_reading'}
DATE_FIELDS = {'invoice_date', 'due_date', 'period_start', 'period_end'}
CRITICAL = {'provider', 'invoice_number', 'account_identifier', 'invoice_date', 'invoice_total',
            'meter_identifier', 'period_start', 'period_end', 'consumption_quantity',
            'consumption_unit', 'delivery_quantity', 'demand_quantity', 'demand_unit'}


def allowed_path(path):
    if path in HEADER_FIELDS:
        return True
    match = re.fullmatch(r'services\.(\d{1,2})\.([a-z_]+)', path)
    return bool(match and int(match[1]) < 50 and match[2] in SERVICE_FIELDS)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class EvidenceField(StrictModel):
    value: str | None = Field(default=None, max_length=120)
    raw: str | None = Field(default=None, max_length=500)
    page: int | None = Field(default=None, ge=1, le=20)
    bbox: tuple[float, float, float, float] | None = None
    method: Literal['native_text', 'template', 'ocr', 'unavailable'] = 'unavailable'
    template_version: str | None = Field(default=None, max_length=80)
    parser_version: str = Field(max_length=160)
    state: Literal['high_evidence', 'needs_review', 'missing', 'conflict'] = 'missing'

    @field_validator('bbox')
    @classmethod
    def ordered_box(cls, value):
        if value is not None and not (0 <= value[0] < value[2] <= 4000 and 0 <= value[1] < value[3] <= 4000):
            raise ValueError('EVIDENCE_COORDINATES_INVALID')
        return value


class SourcePage(StrictModel):
    number: int = Field(ge=1, le=20)
    width: float = Field(gt=0, le=4000)
    height: float = Field(gt=0, le=4000)
    rotation: Literal[0, 90, 180, 270] = 0
    method: Literal['native_text', 'ocr', 'unavailable']


class Extraction(StrictModel):
    schema_version: Literal[1] = 1
    file_type: Literal['pdf'] = 'pdf'
    pdf_kind: Literal['digital_text', 'scanned', 'mixed', 'unreadable']
    provider_key: str | None = Field(default=None, max_length=80)
    provider_fingerprint: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    layout_fingerprint: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    layout_state: Literal['known', 'known_provider_unknown_layout', 'unknown_provider', 'unreadable']
    template_version: str | None = Field(default=None, max_length=80)
    document_type: Literal['invoice', 'supporting_document', 'unknown']
    fields: dict[str, EvidenceField] = Field(max_length=1063)
    pages: list[SourcePage] = Field(default_factory=list, max_length=20)
    codes: list[str] = Field(default_factory=list, max_length=30)
    parser_version: str = Field(max_length=160)

    @field_validator('fields')
    @classmethod
    def field_names(cls, fields):
        if any(not allowed_path(path) for path in fields) or not set(HEADER_FIELDS).issubset(fields):
            raise ValueError('EXTRACTION_FIELDS_INVALID')
        return fields

    @field_validator('codes')
    @classmethod
    def fixed_codes(cls, values):
        allowed = {'PDF_UNREADABLE_MANUAL_ENTRY', 'PDF_PAGE_LIMIT', 'PDF_RESOURCE_LIMIT',
                   'EXTRACTION_TIMED_OUT', 'EXTRACTION_BUSY', 'OCR_UNAVAILABLE_MANUAL_ENTRY',
                   'OCR_REVIEW_REQUIRED', 'KNOWN_PROVIDER_UNKNOWN_LAYOUT', 'UNKNOWN_PROVIDER',
                   'SUPPORTING_DOCUMENT_REQUIRES_REVIEW', 'AMBIGUOUS_PROVIDER', 'AMBIGUOUS_LAYOUT',
                   'EXTRACTION_DEPENDENCY_UNAVAILABLE', 'SOURCE_TEXT_LIMIT',
                   'LOCAL_LAYOUT_DRIFT', 'LOCAL_SERVICE_STRUCTURE_CONFLICT', 'LOCAL_UNIT_CONFLICT',
                   'LOCAL_REQUIRED_FIELD_FAILED', 'LOCAL_TEMPLATE_DAMAGED_MANUAL_REVIEW',
                   'LOCAL_LAYOUT_NOT_ACTIVE_REVIEW_REQUIRED'}
        if any(value not in allowed for value in values):
            raise ValueError('EXTRACTION_CODE_INVALID')
        return values
