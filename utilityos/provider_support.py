"""Developer-shareable counts. No free-form text, labels, coordinates or values."""
from typing import Literal
from pydantic import Field, field_validator
from .extraction_schema import StrictModel, HEADER_FIELDS, SERVICE_FIELDS


class FieldSupport(StrictModel):
    semantic: str
    rule_type: Literal['inline', 'below', 'right', 'region']
    tested: int = Field(ge=0, le=2147483647)
    exact: int = Field(ge=0, le=2147483647)
    missing: int = Field(ge=0, le=2147483647)
    corrected: int = Field(ge=0, le=2147483647)
    unit_conflicts: int = Field(ge=0, le=2147483647)
    manual_entry: int = Field(ge=0, le=2147483647)
    approved_corrections: int = Field(ge=0, le=2147483647)

    @field_validator('semantic')
    @classmethod
    def semantic_name(cls, value):
        if value not in set(HEADER_FIELDS) | {f'services.*.{key}' for key in SERVICE_FIELDS}:
            raise ValueError('SUPPORT_SEMANTIC_INVALID')
        return value


class SupportBundle(StrictModel):
    format: Literal['utilityos-provider-support-v1'] = 'utilityos-provider-support-v1'
    application_version: str = Field(pattern=r'^[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-rc[1-9][0-9]{0,2})?$')
    schema_version: Literal[6] = 6
    anonymous_provider: str = Field(pattern=r'^[0-9a-f]{32}$')
    anonymous_layout: str = Field(pattern=r'^[0-9a-f]{32}$')
    template_version: int = Field(ge=1, le=1000)
    template_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    state: Literal['draft', 'active', 'retired']
    validation_status: Literal['passed_selected_set', 'needs_validation']
    documents_tested: int = Field(ge=0, le=10)
    fields: list[FieldSupport] = Field(max_length=34)
    evidence_states: dict[str, int]
    drift: Literal['none_observed', 'investigate']
    drift_count: int = Field(ge=0, le=2147483647)
    parser_code: Literal['BOUNDED_LITERAL_RULES_REVIEW_REQUIRED'] = 'BOUNDED_LITERAL_RULES_REVIEW_REQUIRED'
    scope: Literal['provider_version_selected_approved_samples'] = 'provider_version_selected_approved_samples'
    synthetic_guidance: Literal['Construct fictional labels and values with the same rule type, ambiguity and missing-field pattern. Never attach private source documents or local definitions.'] = 'Construct fictional labels and values with the same rule type, ambiguity and missing-field pattern. Never attach private source documents or local definitions.'

    @field_validator('evidence_states')
    @classmethod
    def fixed_counts(cls, values):
        if set(values) - {'high_evidence', 'needs_review', 'missing', 'conflict'} or any(type(v) is not int or not 0 <= v <= 2147483647 for v in values.values()):
            raise ValueError('SUPPORT_EVIDENCE_INVALID')
        return values
