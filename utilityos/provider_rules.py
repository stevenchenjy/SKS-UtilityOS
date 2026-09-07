"""Bounded private layout vocabulary. No document/template code is executed."""
from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import Literal
from pydantic import Field, field_validator, model_validator
from .extraction_schema import (StrictModel, SourcePage, EvidenceField, Extraction,
                                HEADER_FIELDS, SERVICE_FIELDS, DATE_FIELDS)
from .extraction import normalize, parse_lines, PARSER_VERSION
from .parsers import UNITS, ValidationError

LOCAL_PARSER = 'utilityos-local-rules-1'


class Observation(StrictModel):
    text: str = Field(max_length=3000)
    page: int = Field(ge=1, le=20)
    bbox: tuple[float, float, float, float]
    method: Literal['native_text', 'ocr']
    parser_version: str = Field(default=PARSER_VERSION, max_length=160)
    _box = field_validator('bbox')(EvidenceField.ordered_box.__func__)


class Observations(StrictModel):
    adapter_version: Literal[1] = 1
    lines: list[Observation] = Field(max_length=10000)
    pages: list[SourcePage] = Field(max_length=20)
    codes: list[str] = Field(default_factory=list, max_length=30)
    _codes = field_validator('codes')(Extraction.fixed_codes.__func__)

    @model_validator(mode='after')
    def bounds(self):
        pages = {page.number: page for page in self.pages}
        if len(pages) != len(self.pages) or sum(len(line.text) for line in self.lines) > 500000:
            raise ValueError('SOURCE_TEXT_LIMIT')
        for line in self.lines:
            page = pages.get(line.page)
            if not page or line.bbox[2] > page.width or line.bbox[3] > page.height:
                raise ValueError('EVIDENCE_COORDINATES_INVALID')
        return self


class Anchor(StrictModel):
    literal: str = Field(min_length=1, max_length=120)
    page: int = Field(default=1, ge=1, le=20)
    region: tuple[float, float, float, float] = (0, 0, 4000, 4000)
    _box = field_validator('region')(EvidenceField.ordered_box.__func__)

    @field_validator('literal')
    @classmethod
    def literal_text(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError('LITERAL_LABEL_INVALID')
        return value.strip()


class Rule(StrictModel):
    field: str = Field(max_length=60)
    label: str = Field(default='', max_length=120)
    mode: Literal['inline', 'below', 'right', 'region'] = 'inline'
    page: int | None = Field(default=None, ge=1, le=20)
    region: tuple[float, float, float, float] | None = None
    distance: int = Field(default=60, ge=1, le=200)
    required: bool = True
    date_format: Literal['iso', 'mdy', 'dmy'] = 'iso'
    expected_unit: str | None = Field(default=None, max_length=12)
    _box = field_validator('region')(EvidenceField.ordered_box.__func__)

    @model_validator(mode='after')
    def semantics(self):
        if self.field not in HEADER_FIELDS and self.field not in {f'services.*.{key}' for key in SERVICE_FIELDS}:
            raise ValueError('LOCAL_RULE_FIELD_INVALID')
        # These are explicit layout metadata, never untrusted inferred defaults.
        if self.field in {'provider', 'document_kind', 'supplier_only', 'delivery_only',
                          'services.*.utility_type', 'services.*.quantity_treatment'}:
            raise ValueError('LOCAL_RULE_METADATA_FIELD')
        if self.mode == 'region' and self.region is None or self.mode != 'region' and not self.label.strip():
            raise ValueError('LOCAL_RULE_LOCATOR_REQUIRED')
        if any(ord(c) < 32 for c in self.label):
            raise ValueError('LITERAL_LABEL_INVALID')
        if self.expected_unit is not None:
            if not self.field.endswith('_unit') or normalize('consumption_unit', self.expected_unit) != self.expected_unit:
                raise ValueError('LOCAL_RULE_UNIT_INVALID')
        if self.date_format != 'iso' and self.field.split('.')[-1] not in DATE_FIELDS:
            raise ValueError('LOCAL_RULE_DATE_FORMAT_INVALID')
        return self


class Definition(StrictModel):
    format: Literal[1] = 1
    provider_anchor: Anchor
    layout_anchor: Anchor | None = None
    section_prefix: str | None = Field(default='Service point ', min_length=1, max_length=100)
    document_kind: Literal['invoice', 'credit', 'corrected_invoice', 'rebill', 'supporting_document'] = 'invoice'
    quantity_treatment: Literal['consumption', 'charges_only', 'delivery'] = 'consumption'
    end_date_inclusive: bool = False
    rules: list[Rule] = Field(min_length=9, max_length=34)

    @model_validator(mode='after')
    def coverage(self):
        if self.section_prefix is not None and (not self.section_prefix.strip() or any(ord(c) < 32 for c in self.section_prefix)):
            raise ValueError('LOCAL_SECTION_PREFIX_INVALID')
        keys = [rule.field for rule in self.rules]
        required = {rule.field for rule in self.rules if rule.required}
        essential = {'invoice_number', 'account_identifier', 'invoice_date', 'invoice_total'} | {
            f'services.*.{key}' for key in ('meter_identifier', 'period_start', 'period_end', 'current_charge', 'consumption_unit')}
        if self.quantity_treatment != 'charges_only':
            essential.add('services.*.' + ('delivery_quantity' if self.quantity_treatment == 'delivery' else 'consumption_quantity'))
        if len(set(keys)) != len(keys) or not essential.issubset(required):
            raise ValueError('LOCAL_LAYOUT_REQUIRED_FIELDS_MISSING')
        return self


def definition(value):
    try:
        return Definition.model_validate(value)
    except ValueError:
        raise ValidationError('LOCAL_LAYOUT_DEFINITION_INVALID') from None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def inside(line, region):
    if region is None:
        return True
    x0, y0, x1, y1 = line['bbox']
    return region[0] <= (x0 + x1) / 2 <= region[2] and region[1] <= (y0 + y1) / 2 <= region[3]


def anchor_matches(lines, anchor):
    return [line for line in lines if line['text'].strip() == anchor.literal
            and line['page'] == anchor.page and inside(line, anchor.region)]


def locate(lines, rule):
    scope = [line for line in lines if (rule.page is None or line['page'] == rule.page) and inside(line, rule.region)]
    if rule.mode == 'region':
        return [(line['text'], line) for line in scope]
    label = rule.label.strip().rstrip(':').strip()
    if rule.mode == 'inline':
        return [(line['text'][len(label) + 1:].strip(), line) for line in scope if line['text'].startswith(label + ':')]
    anchors = [line for line in scope if line['text'].strip().rstrip(':').strip() == label]
    if len(anchors) != 1:
        return [(None, line) for line in anchors] # Multiple anchors remain ambiguous.
    anchor = anchors[0]
    x0, y0, x1, y1 = anchor['bbox']
    nearby = []
    for line in lines:
        if line is anchor or line['page'] != anchor['page']:
            continue
        a, b, c, d = line['bbox']
        qualifies = (0 <= b - y1 <= rule.distance and a < x1 and c > x0) if rule.mode == 'below' else (
            0 <= a - x1 <= rule.distance and b < y1 and d > y0)
        if qualifies:
            nearby.append((line['text'], line))
    return nearby # Never guess between multiple nearby values.


def service_sections(lines, prefix):
    if prefix is None:
        return [lines], False
    positions = []
    invalid = False
    for index, line in enumerate(lines):
        content = line['text'].strip()
        if content.startswith(prefix):
            suffix = content[len(prefix):].strip()
            if not suffix.isascii() or not suffix.isdigit() or not 1 <= int(suffix) <= 50:
                invalid = True
            else:
                positions.append((index, int(suffix)))
    if not positions or len(positions) > 50 or [n for _, n in positions] != list(range(1, len(positions) + 1)):
        invalid = True
    scopes = [lines[position + 1:positions[i + 1][0] if i + 1 < len(positions) else len(lines)]
              for i, (position, _) in enumerate(positions[:50])]
    return scopes, invalid


def extract_layout(observed, provider, layout):
    """Explicit preview and automatic candidates share exactly one compiler."""
    spec = definition(layout['definition'])
    lines, pages = observed['lines'], observed['pages']
    fields = {key: EvidenceField(parser_version=LOCAL_PARSER) for key in HEADER_FIELDS}
    sections, invalid_sections = service_sections(lines, spec.section_prefix)
    for index in range(len(sections)):
        fields.update({f'services.{index}.{key}': EvidenceField(parser_version=LOCAL_PARSER) for key in SERVICE_FIELDS})
    issues = []
    if len(anchor_matches(lines, spec.provider_anchor)) != 1 or (spec.layout_anchor and len(anchor_matches(lines, spec.layout_anchor)) != 1):
        issues.append('LOCAL_LAYOUT_DRIFT')
    if invalid_sections:
        issues.append('LOCAL_SERVICE_STRUCTURE_CONFLICT')
    for rule in spec.rules:
        scopes = list(enumerate(sections)) if rule.field.startswith('services.*.') else [(None, lines)]
        for index, scope in scopes:
            path = rule.field.replace('*', str(index)) if index is not None else rule.field
            hits = locate(scope, rule)
            value, state = None, 'missing' if not hits else 'conflict'
            raw, line = hits[0] if hits else (None, None)
            if len(hits) == 1 and raw:
                try:
                    field = rule.field.split('.')[-1]
                    candidate = raw
                    if field in DATE_FIELDS and rule.date_format != 'iso':
                        candidate = datetime.strptime(raw, '%m/%d/%Y' if rule.date_format == 'mdy' else '%d/%m/%Y').date().isoformat()
                    value = normalize(field, candidate)
                    if field == 'period_end' and spec.end_date_inclusive:
                        value = (datetime.fromisoformat(value).date() + timedelta(days=1)).isoformat()
                    if rule.expected_unit is not None and value != rule.expected_unit:
                        value = None
                        issues.append('LOCAL_UNIT_CONFLICT')
                    else:
                        state = 'needs_review' if line['method'] == 'ocr' else 'high_evidence'
                except (ValueError, OverflowError):
                    pass
            if rule.required and value is None:
                issues.append('LOCAL_REQUIRED_FIELD_FAILED')
            fields[path] = EvidenceField(value=value, raw=raw[:500] if raw else None,
                page=line['page'] if line else None, bbox=line['bbox'] if line else None,
                method='ocr' if line and line['method'] == 'ocr' else 'template' if line else 'unavailable',
                template_version=layout['id'], parser_version=line.get('parser_version', LOCAL_PARSER) if line and line['method'] == 'ocr' else LOCAL_PARSER,
                state=state)
    # Defaults express the operator's reviewed layout semantics, with no source
    # value invented for a charge, date, identifier or quantity.
    metadata = {'provider': provider['label'], 'document_kind': spec.document_kind,
                'supplier_only': 'yes' if spec.quantity_treatment == 'charges_only' else 'no',
                'delivery_only': 'yes' if spec.quantity_treatment == 'delivery' else 'no'}
    for index in range(len(sections)):
        metadata.update({f'services.{index}.utility_type': provider['commodity'],
                         f'services.{index}.quantity_treatment': spec.quantity_treatment})
    for key, value in metadata.items():
        fields[key] = EvidenceField(value=value, method='unavailable', template_version=layout['id'],
                                     parser_version=LOCAL_PARSER, state='needs_review')
    methods = {page['method'] for page in pages}
    kind = 'mixed' if {'native_text', 'ocr'} <= methods else 'scanned' if 'ocr' in methods else 'digital_text' if 'native_text' in methods else 'unreadable'
    codes = list(dict.fromkeys([*observed['codes'], *issues]))
    result = Extraction(pdf_kind=kind, provider_key=provider['id'], provider_fingerprint=sha256(provider['id'].encode()).hexdigest(),
        layout_fingerprint=digest([(key, value.page, tuple(int(n // 36) for n in value.bbox))
                                   for key, value in fields.items() if value.bbox]), template_version=layout['id'],
        layout_state='known' if not issues else 'known_provider_unknown_layout',
        document_type='supporting_document' if spec.document_kind == 'supporting_document' else 'invoice',
        fields=fields, pages=pages, codes=codes, parser_version=LOCAL_PARSER).model_dump(mode='json')
    return result


def select_layout(observed, providers, layouts, damaged=False):
    fallback = parse_lines(observed['lines'], observed['pages'], observed['codes'])
    recognized = {layout['provider_id'] for layout in layouts
                  if anchor_matches(observed['lines'], definition(layout['definition']).provider_anchor)}
    if len(recognized) > 1:
        fallback['codes'].append('AMBIGUOUS_PROVIDER')
        fallback.update(template_version=None, layout_state='unknown_provider')
        return fallback, None, None, 'ambiguous'
    if not recognized:
        if damaged:
            fallback['codes'].append('LOCAL_TEMPLATE_DAMAGED_MANUAL_REVIEW')
        return fallback, None, None, 'damaged' if damaged else 'unmatched'
    provider_id = next(iter(recognized))
    provider = next(p for p in providers if p['id'] == provider_id)
    candidates = [(layout, extract_layout(observed, provider, layout)) for layout in layouts
                  if layout['provider_id'] == provider_id and layout['state'] == 'active']
    if not candidates:
        fallback.update(provider_key=provider_id, template_version=None, layout_state='known_provider_unknown_layout')
        fallback['codes'] = list(dict.fromkeys([*fallback['codes'], 'LOCAL_LAYOUT_NOT_ACTIVE_REVIEW_REQUIRED']))
        return fallback, provider_id, None, 'inactive'
    matches = [(layout, result) for layout, result in candidates if result['layout_state'] == 'known']
    if len(matches) == 1:
        layout, result = matches[0]
        return result, provider_id, layout['id'], 'matched'
    fallback.update(provider_key=provider_id, template_version=None, layout_state='known_provider_unknown_layout')
    fallback['codes'] = list(dict.fromkeys([*fallback['codes'], 'AMBIGUOUS_LAYOUT' if len(matches) > 1 else 'LOCAL_LAYOUT_DRIFT']))
    return fallback, provider_id, None, 'ambiguous' if len(matches) > 1 else 'drift'
