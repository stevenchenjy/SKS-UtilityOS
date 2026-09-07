"""Deterministic provider recognition and evidence-preserving PDF candidates."""
from decimal import Decimal
from hashlib import sha256
import re
from .extraction_schema import (Extraction, EvidenceField, HEADER_FIELDS, SERVICE_FIELDS,
                                MONEY_FIELDS, NUMBER_FIELDS, DATE_FIELDS)
from .provider_templates import TEMPLATES, PROVIDERS, HEADER_LABELS, SERVICE_LABELS, V2_HEADER, V2_SERVICE
from .parsers import blank_bill, cents, decimal_value, iso_date, text

PARSER_VERSION = 'utilityos-labels-1/pdfplumber-0.11.10'
UNIT_ALIASES = {'kwh': 'kWh', 'gal': 'gal', 'gallons': 'gal', 'm3': 'm3', 'ccf': 'CCF',
                'mcf': 'Mcf', 'therm': 'therm', 'therms': 'therm', 'mmbtu': 'MMBtu',
                'kw': 'kW', 'kva': 'kVA', 'lb': 'lb', 'ton_h': 'ton_h'}


def normalize(name, raw):
    value = text(raw)
    if name in MONEY_FIELDS | NUMBER_FIELDS:
        if name in MONEY_FIELDS:
            value = value.removeprefix('$').strip()
        if ',' in value:
            if not re.fullmatch(r'-?\d{1,3}(,\d{3})+(\.\d+)?', value):
                raise ValueError('NUMBER_GROUPING_INVALID')
            value = value.replace(',', '')
        if name in MONEY_FIELDS:
            return format(Decimal(cents(value)) / 100, '.2f')
        return format(decimal_value(value, nonnegative=False), 'f')
    if name in DATE_FIELDS:
        return iso_date(value)
    if name.endswith('_unit'):
        if value.lower() not in UNIT_ALIASES:
            raise ValueError('UNIT_UNSUPPORTED')
        return UNIT_ALIASES[value.lower()]
    if name in {'supplier_only', 'delivery_only'}:
        if value.lower() not in {'yes', 'no'}:
            raise ValueError('BOOLEAN_UNSUPPORTED')
        return value.lower()
    if name in {'utility_type', 'quantity_treatment', 'reading_type', 'document_kind'}:
        value = value.lower().replace(' ', '_')
        from .parsers import UNITS
        allowed = {'utility_type':set(UNITS), 'quantity_treatment':{'consumption','charges_only','delivery'},
                   'reading_type':{'actual','estimated','unknown'},
                   'document_kind':{'invoice','credit','corrected_invoice','rebill','supporting_document'}}
        if value not in allowed[name]:
            raise ValueError('FIELD_SEMANTICS_UNSUPPORTED')
        return value
    return value


def empty_extraction(code='PDF_UNREADABLE_MANUAL_ENTRY'):
    return Extraction(pdf_kind='unreadable', layout_state='unreadable', document_type='unknown',
                      fields={key: EvidenceField(parser_version=PARSER_VERSION) for key in HEADER_FIELDS},
                      codes=[code], parser_version=PARSER_VERSION).model_dump(mode='json')


def parse_lines(lines, pages, codes=(), templates=TEMPLATES):
    """Input lines are native/OCR observations; labels alone drive reuse hashes.

    Never execute instructions in a document, fetch its links or choose a match
    using private identifiers. Ambiguous matches do not select a template.
    """
    provider_keys = [key for key, name in PROVIDERS.items()
                     if any(line['text'] in (name, 'Provider: ' + name) for line in lines)]
    provider_key = provider_keys[0] if len(provider_keys) == 1 else None
    matches = [template for template in templates if template.active and template.provider_key == provider_key
               and any(line['text'] == template.anchor and line['page'] == 1
                       and template.anchor_top[0] <= line['bbox'][1] <= template.anchor_top[1] for line in lines)]
    selected = matches[0] if len(matches) == 1 else None
    # Layout anchors include several critical field labels and public geometry.
    # A renamed/moved required label invalidates the old template even when its
    # title survives. Identifier values are never used here.
    if selected:
        required = [selected.header_labels[k] for k in ('invoice_number', 'account_identifier', 'invoice_date')]
        if not all(any(line['text'].startswith(label + ':') and line['page'] == 1
                       and 80 <= line['bbox'][1] <= 360 for line in lines) for label in required):
            selected = None
    state = 'known' if selected else 'known_provider_unknown_layout' if provider_key else 'unknown_provider'
    codes = list(codes)
    if len(provider_keys) > 1:
        codes.append('AMBIGUOUS_PROVIDER')
    if len(matches) > 1:
        codes.append('AMBIGUOUS_LAYOUT')
    if state != 'known':
        codes.append('KNOWN_PROVIDER_UNKNOWN_LAYOUT' if provider_key else 'UNKNOWN_PROVIDER')
    fields = {key: EvidenceField(parser_version=PARSER_VERSION) for key in HEADER_FIELDS}
    headers = selected.header_labels if selected else None
    services = selected.service_labels if selected else None
    observations = {}
    public_shape = []
    current_service = None
    service_count = 0
    for line in lines:
        match = re.fullmatch(r'Service point (\d{1,2})', line['text'])
        if match and 1 <= int(match[1]) <= 50:
            current_service = int(match[1]) - 1
            service_count = max(service_count, current_service + 1)
            continue
        sets = [(headers, None)] if headers else [(HEADER_LABELS, None), (V2_HEADER, None)]
        if current_service is not None:
            sets += [(services, current_service)] if services else [(SERVICE_LABELS, current_service), (V2_SERVICE, current_service)]
        seen = set()
        for labels, index in sets:
            for key, label in labels.items():
                if not line['text'].startswith(label + ':'):
                    continue
                path = key if index is None else f'services.{index}.{key}'
                if path in seen:
                    continue
                seen.add(path)
                raw = line['text'][len(label) + 1:].strip()
                observations.setdefault(path, []).append((raw, line))
                # Only public labels and coarse positions, no field values.
                public_shape.append((label, line['page'], int(line['bbox'][0] // 36), int(line['bbox'][1] // 36)))
    for index in range(service_count):
        fields.update({f'services.{index}.{key}': EvidenceField(parser_version=PARSER_VERSION) for key in SERVICE_FIELDS})
    for path, observed in observations.items():
        raw, line = observed[0]
        ocr = line['method'] == 'ocr'
        value, quality = None, 'conflict'
        if len(observed) == 1:
            try:
                value = normalize(path.split('.')[-1], raw)
                quality = 'high_evidence' if selected and not ocr else 'needs_review'
            except ValueError:
                pass
        fields[path] = EvidenceField(value=value, raw=raw[:500], page=line['page'], bbox=line['bbox'],
                                     method='ocr' if ocr else 'template' if selected else 'native_text',
                                     template_version=selected.version if selected else None,
                                     parser_version=line.get('parser_version', PARSER_VERSION), state=quality)
    kind = fields['document_kind'].value
    document_type = 'invoice' if kind in {'invoice', 'credit', 'corrected_invoice', 'rebill'} else 'supporting_document' if kind == 'supporting_document' else 'unknown'
    if document_type == 'supporting_document':
        codes.append('SUPPORTING_DOCUMENT_REQUIRES_REVIEW')
    methods = {page['method'] for page in pages}
    pdf_kind = 'digital_text' if methods == {'native_text'} else 'scanned' if 'native_text' not in methods else 'mixed'
    return Extraction(pdf_kind=pdf_kind, provider_key=provider_key,
                      provider_fingerprint=sha256(PROVIDERS[provider_key].encode()).hexdigest() if provider_key else None,
                      layout_fingerprint=sha256(repr(sorted(set(public_shape))).encode()).hexdigest(),
                      layout_state=state, template_version=selected.version if selected else None,
                      document_type=document_type, fields=fields, pages=pages, codes=list(dict.fromkeys(codes)),
                      parser_version=PARSER_VERSION).model_dump(mode='json')


HEADER_TO_BILL = {'provider': 'provider', 'invoice_number': 'invoice_number', 'account_identifier': 'account_alias',
                  'invoice_date': 'bill_date', 'invoice_total': 'current_total'}
SERVICE_TO_BILL = {'meter_identifier': 'meter_code', 'building': 'building', 'utility_type': 'commodity',
                   'period_start': 'period_start', 'period_end': 'period_end', 'consumption_quantity': 'usage',
                   'consumption_unit': 'unit', 'quantity_treatment': 'usage_role', 'reading_type': 'read_type',
                   'current_charge': 'current_charge'}


def proposed_bill(extraction):
    values = {key: field['value'] or '' for key, field in extraction['fields'].items()}
    bill = blank_bill()
    for source, target in HEADER_TO_BILL.items():
        bill[target] = values.get(source, '')
    indices = sorted({int(path.split('.')[1]) for path in values if path.startswith('services.')})
    if indices:
        bill['lines'] = []
        for index in indices:
            value = lambda key: values.get(f'services.{index}.{key}', '')
            line = {target: value(source) for source, target in SERVICE_TO_BILL.items()}
            line['read_type'] = line['read_type'] or 'unknown'
            if line['usage_role'] == 'delivery':
                line['usage'] = value('delivery_quantity')
            if values.get('supplier_only') == 'yes' or line['usage_role'] == 'charges_only':
                line['usage_role'], line['usage'] = 'charges_only', '0'
            bill['lines'].append(line)
    return bill
