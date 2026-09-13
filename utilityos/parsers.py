"""Deterministic, offline parsers. No external URLs in XML are fetched."""
from collections import OrderedDict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO
from urllib.parse import urljoin, urlsplit, urlunsplit
import csv
import re
from defusedxml import ElementTree as ET

UNITS = {
    'electricity': {'kWh'}, 'water': {'gal', 'm3', 'CCF'},
    'natural_gas': {'therm', 'CCF', 'Mcf', 'MMBtu'},
    'heating_oil': {'gal'}, 'propane': {'gal'}, 'steam': {'lb', 'MMBtu'},
    'hot_water': {'MMBtu'}, 'chilled_water': {'ton_h', 'MMBtu'}
}
REQUIRED_CSV = {'provider','account_alias','invoice_number','bill_date','meter_code','building',
                'commodity','period_start','period_end','usage','unit','current_charge','usage_role','read_type'}
A = '{http://www.w3.org/2005/Atom}'
E = '{http://naesb.org/espi}'


class ValidationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def text(value, required=True, max_len=120):
    if not isinstance(value, str):
        raise ValidationError('TEXT_REQUIRED')
    value = value.strip()
    if (required and not value) or len(value) > max_len or any(ord(ch)<32 for ch in value):
        raise ValidationError('TEXT_FIELD_INVALID')
    return value


def decimal_value(value, nonnegative=True):
    raw = str(value).strip()
    if len(raw)>32 or not re.fullmatch(r'-?\d+(?:\.\d{1,9})?', raw):
        raise ValidationError('NUMBER_INVALID_USE_PLAIN_DECIMAL')
    try:
        val = Decimal(raw)
    except InvalidOperation:
        raise ValidationError('NUMBER_INVALID')
    if not val.is_finite() or abs(val) > Decimal('1000000000000') or (nonnegative and val<0):
        raise ValidationError('NUMBER_OUT_OF_RANGE')
    return val


def cents(value):
    val = decimal_value(value, nonnegative=False)
    if val*100 != (val*100).to_integral_value():
        raise ValidationError('MONEY_REQUIRES_AT_MOST_TWO_DECIMALS')
    return int(val*100)


def iso_date(value):
    raw = text(value, max_len=10)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
        raise ValidationError('DATE_REQUIRES_YYYY_MM_DD')
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        raise ValidationError('DATE_INVALID')
    if not 1990<=d.year<=2100:
        raise ValidationError('DATE_OUT_OF_RANGE')
    return raw


def validate_bill(payload):
    if not isinstance(payload, dict):
        raise ValidationError('BILL_OBJECT_REQUIRED')
    result = {k: text(payload.get(k,'')) for k in ('provider','account_alias','invoice_number')}
    result['bill_date'] = iso_date(payload.get('bill_date',''))
    result['current_total'] = str(Decimal(cents(payload.get('current_total','')))/100)
    lines = payload.get('lines')
    if not isinstance(lines, list) or not 1<=len(lines)<=50:
        raise ValidationError('BILL_REQUIRES_1_TO_50_LINES')
    result['lines'] = []
    line_periods = []
    meter_definitions = {}
    for entry in lines:
        if not isinstance(entry, dict):
            raise ValidationError('BILL_LINE_INVALID')
        line = {k:text(entry.get(k,'')) for k in ('meter_code','commodity','unit','usage_role','read_type')}
        line['building'] = text(entry.get('building',''), required=False)
        identity = (line['building'], line['commodity'], line['unit'])
        if line['meter_code'] in meter_definitions and meter_definitions[line['meter_code']] != identity:
            raise ValidationError('METER_IDENTITY_INCONSISTENT_WITHIN_INVOICE')
        meter_definitions[line['meter_code']] = identity
        if line['commodity'] not in UNITS or line['unit'] not in UNITS[line['commodity']]:
            raise ValidationError('UNSUPPORTED_COMMODITY_UNIT')
        if line['usage_role'] not in {'consumption','charges_only','delivery'} or line['read_type'] not in {'actual','estimated','unknown'}:
            raise ValidationError('READ_TYPE_OR_USAGE_ROLE_INVALID')
        if line['commodity'] in {'heating_oil','propane'} and line['usage_role']=='consumption':
            raise ValidationError('DELIVERED_FUEL_REQUIRES_DELIVERY_ROLE')
        line['period_start'] = iso_date(entry.get('period_start',''))
        line['period_end'] = iso_date(entry.get('period_end',''))
        days = (date.fromisoformat(line['period_end'])-date.fromisoformat(line['period_start'])).days
        if not 1<=days<=400:
            raise ValidationError('PERIOD_REQUIRES_1_TO_400_DAYS_END_EXCLUSIVE')
        line['usage'] = format(decimal_value(entry.get('usage','')), 'f')
        line['current_charge'] = str(Decimal(cents(entry.get('current_charge','')))/100)
        if line['usage_role']=='charges_only' and Decimal(line['usage'])!=0:
            raise ValidationError('CHARGES_ONLY_USAGE_MUST_BE_ZERO')
        if line['usage_role']=='consumption':
            for code, start, end in line_periods:
                if code == line['meter_code'] and line['period_start']<end and line['period_end']>start:
                    raise ValidationError('CONSUMPTION_LINES_OVERLAP_IN_INVOICE')
            line_periods.append((line['meter_code'],line['period_start'],line['period_end']))
        result['lines'].append(line)
    if sum(cents(line['current_charge']) for line in result['lines']) != cents(result['current_total']):
        raise ValidationError('CURRENT_TOTAL_DOES_NOT_MATCH_LINE_CHARGES')
    return result


def parse_csv(raw: bytes):
    try:
        source = raw.decode('utf-8-sig')
    except UnicodeError:
        raise ValidationError('CSV_REQUIRES_UTF8')
    reader = csv.DictReader(StringIO(source))
    if not reader.fieldnames or not REQUIRED_CSV.issubset(set(reader.fieldnames)):
        raise ValidationError('CSV_HEADERS_DO_NOT_MATCH_TEMPLATE')
    if len(reader.fieldnames)!=len(set(reader.fieldnames)):
        raise ValidationError('CSV_DUPLICATE_HEADERS')
    groups = OrderedDict()
    for i, row in enumerate(reader):
        if i>=2000:
            raise ValidationError('CSV_EXCEEDS_2000_LINES')
        if None in row or any(value is None for value in row.values()):
            raise ValidationError('CSV_ROW_LENGTH_INVALID')
        key = tuple(text(row.get(k,'')) for k in ('provider','account_alias','invoice_number'))
        if key not in groups:
            groups[key] = {'provider':key[0], 'account_alias':key[1], 'invoice_number':key[2],
                           'bill_date':row['bill_date'], 'current_total':row.get('current_total','').strip(), 'lines':[]}
        group = groups[key]
        if row['bill_date'] != group['bill_date'] or row.get('current_total','').strip() != group['current_total']:
            raise ValidationError('INVOICE_HEADER_INCONSISTENT_ACROSS_ROWS')
        group['lines'].append({k:row[k] for k in REQUIRED_CSV-{'provider','account_alias','invoice_number','bill_date'}})
    if not groups:
        raise ValidationError('CSV_EMPTY')
    if len(groups)>200:
        raise ValidationError('CSV_EXCEEDS_200_INVOICES')
    result = []
    for group in groups.values():
        if not group['current_total']:
            group['current_total'] = str(sum(Decimal(cents(line['current_charge']))/100 for line in group['lines']))
        result.append(validate_bill(group))
    return result


def uri(value, base='https://offline.invalid/'):
    """Resolve identifiers only; never fetch them or merge query/fragment IDs."""
    if not isinstance(value, str) or not value or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ValidationError('XML_RESOURCE_URI_INVALID')
    try:
        parsed = urlsplit(urljoin(base, value))
        if parsed.scheme not in {'http', 'https', 'urn'} or parsed.username or parsed.password:
            raise ValueError()
        if parsed.scheme in {'http', 'https'} and not parsed.netloc:
            raise ValueError()
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), parsed.query, parsed.fragment))
    except ValueError:
        raise ValidationError('XML_RESOURCE_URI_INVALID') from None


# ESPI CommodityKind / MeasurementKind / UnitSymbolKind. Values are deliberately
# enumerated; gas volume is not converted to energy. See docs/GREEN_BUTTON.md.
GREEN_BUTTON_UNITS = {
    (1, 12, 72): ('electricity', 'kWh', Decimal('1000')),
    (7, 12, 169): ('natural_gas', 'therm', Decimal('1')),
    (9, 58, 42): ('water', 'm3', Decimal('1')),
    (9, 58, 128): ('water', 'US_gal', Decimal('1')),
}
QUALITY_CODES = {'0', '7', '8', '9', '11', '14', '17', '18', '19'}
XML_BASE = '{http://www.w3.org/XML/1998/namespace}base'


def _xml_field(node, name, default=None):
    values = node.findall(E + name)
    if not values:
        return default
    if len(values) != 1 or len(values[0]) or values[0].text is None:
        raise ValidationError('XML_FIELD_MISSING_DUPLICATE_OR_INVALID')
    return values[0].text.strip()


def _xml_number(node, name, default=None):
    value = _xml_field(node, name, default)
    if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,16}', value):
        raise ValidationError('XML_READING_TYPE_FIELD_MISSING_OR_INVALID')
    return int(value)


def _quality(value):
    if value not in QUALITY_CODES:
        raise ValidationError('XML_QUALITY_UNSUPPORTED_REQUIRES_REVIEW')
    return value


def _parent_resource(links, resources, child_collection, parent_type, required=True):
    parents = []
    up_links = [href for rel, href in links if rel == 'up']
    for href in up_links:
        # Only an exact collection suffix can denote its parent. Do not accept
        # arbitrary paths containing '/IntervalBlock' as a relationship.
        parsed = urlsplit(href)
        path = parsed.path
        if path.endswith('/' + child_collection):
            candidate = urlunsplit((parsed.scheme, parsed.netloc, path[:-len(child_collection)-1], parsed.query, parsed.fragment))
        else:
            candidate = href
        if candidate in resources and resources[candidate]['object'].tag == E + parent_type:
            parents.append(candidate)
    if (len(parents) != 1 or len(up_links) != 1) and (required or up_links):
        raise ValidationError('XML_' + ('METER_READING' if parent_type == 'MeterReading' else 'USAGE_POINT') + '_RELATION_UNRESOLVED')
    return parents[0] if parents else None


def parse_greenbutton(raw: bytes):
    """Offline ESPI forward-delta energy/volume subset with retained provenance.

    Original source bytes remain authoritative. Linked resources are resolved
    strictly inside the supplied Atom feed. Cumulative, demand, reverse/net,
    unsupported qualifiers and uncertain qualities are rejected, not inferred.
    """
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise ValidationError('XML_EMPTY_OR_EXCEEDS_8_MB')
    try:
        root = ET.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception:
        raise ValidationError('XML_UNSAFE_OR_MALFORMED') from None
    if root.tag != A + 'feed':
        raise ValidationError('GREEN_BUTTON_ATOM_FEED_REQUIRED')
    base = urljoin('https://offline.invalid/', root.attrib.get(XML_BASE, ''))
    resources = {}
    blocks = []
    for entry in root.findall(A + 'entry'):
        entry_base = urljoin(base, entry.attrib.get(XML_BASE, ''))
        links = [(link.get('rel', ''), uri(link.get('href', ''), urljoin(entry_base, link.attrib.get(XML_BASE, ''))))
                 for link in entry.findall(A + 'link')]
        self_links = [url for rel, url in links if rel == 'self']
        content = entry.find(A + 'content')
        if content is None or len(content) != 1:
            continue
        obj = content[0]
        if obj.tag in {E + 'UsagePoint', E + 'ReadingType', E + 'MeterReading', E + 'IntervalBlock'}:
            if len(self_links) != 1 or self_links[0] in resources:
                raise ValidationError('XML_RESOURCE_ID_MISSING_OR_DUPLICATE')
            atom_id = entry.findtext(A + 'id', '')
            if len(atom_id) > 2048:
                raise ValidationError('XML_RESOURCE_ID_INVALID')
            resources[self_links[0]] = {'object': obj, 'links': links, 'atom_id': atom_id}
            if len(resources) > 2000:
                raise ValidationError('XML_EXCEEDS_2000_RESOURCES')
            if obj.tag == E + 'IntervalBlock':
                blocks.append(self_links[0])
    if not blocks:
        raise ValidationError('XML_NO_INTERVAL_BLOCKS')
    channels = {}
    total = 0
    for block_uri in blocks:
        block_resource = resources[block_uri]
        block = block_resource['object']
        meter_uri = _parent_resource(block_resource['links'], resources, 'IntervalBlock', 'MeterReading')
        meter_resource = resources[meter_uri]
        mlinks = meter_resource['links']
        rtypes = [href for rel, href in mlinks if rel == 'related' and href in resources
                  and resources[href]['object'].tag == E + 'ReadingType']
        if len(rtypes) != 1:
            raise ValidationError('XML_READING_TYPE_RELATION_UNRESOLVED')
        reading = resources[rtypes[0]]['object']
        metadata = {key: _xml_number(reading, key) for key in
                    ('commodity', 'uom', 'powerOfTenMultiplier', 'flowDirection', 'accumulationBehaviour', 'kind')}
        identity = (metadata['commodity'], metadata['kind'], metadata['uom'])
        if identity not in GREEN_BUTTON_UNITS:
            raise ValidationError('XML_COMMODITY_KIND_UNIT_UNSUPPORTED')
        commodity, unit, divisor = GREEN_BUTTON_UNITS[identity]
        if metadata['flowDirection'] != 1 or metadata['accumulationBehaviour'] != 4:
            raise ValidationError('XML_REQUIRES_FORWARD_INCREMENTAL_ENERGY_OR_VOLUME')
        exponent = metadata['powerOfTenMultiplier']
        if not -12 <= exponent <= 12:
            raise ValidationError('XML_MULTIPLIER_OUT_OF_RANGE')
        # Omitted qualifiers are retained as omitted. Nontrivial aggregations,
        # tariffs, phase-specific readings and time methods need a new adapter.
        supported_optional = {'dataQualifier': {0, 12}, 'phase': {0, 769},
                              'timeAttribute': {0}, 'tou': {0}, 'cpp': {0},
                              'consumptionTier': {0}, 'aggregate': {0}, 'measuringPeriod': {0}}
        for key, allowed in supported_optional.items():
            if reading.find(E + key) is not None:
                value = _xml_number(reading, key)
                if value not in allowed:
                    raise ValidationError('XML_QUALIFIER_OR_AGGREGATION_UNSUPPORTED')
                metadata[key] = value
        known = set(metadata) | set(supported_optional) | {'defaultQuality', 'intervalLength', 'currency'}
        if any(child.tag not in {E + key for key in known} for child in reading):
            raise ValidationError('XML_READING_TYPE_EXTENSION_UNSUPPORTED')
        default_quality = _xml_field(reading, 'defaultQuality')
        metadata['defaultQuality'] = _quality(default_quality) if default_quality is not None else 'unknown'
        currency = _xml_number(reading, 'currency') if reading.find(E + 'currency') is not None else None
        if currency is not None and not 0 <= currency <= 65535:
            raise ValidationError('XML_CURRENCY_CODE_INVALID')
        metadata['intervalLength'] = _xml_number(reading, 'intervalLength', '0')
        if not 0 <= metadata['intervalLength'] <= 2678400:
            raise ValidationError('XML_INTERVAL_TIME_OUT_OF_RANGE')
        # Preserve old electricity metadata exactly for previously mapped streams.
        if commodity != 'electricity':
            metadata['normalized_unit'] = unit
        has_usage_points = any(resource['object'].tag == E + 'UsagePoint' for resource in resources.values())
        usage_uri = _parent_resource(mlinks, resources, 'MeterReading', 'UsagePoint', required=has_usage_points)
        service_kind = None
        if usage_uri is not None:
            point = resources[usage_uri]['object']
            categories = point.findall(E + 'ServiceCategory')
            if len(categories) > 1:
                raise ValidationError('XML_USAGE_POINT_SERVICE_MISMATCH')
            if categories:
                service_kind = _xml_number(categories[0], 'kind')
                if service_kind != {'electricity': 0, 'natural_gas': 1, 'water': 2}[commodity]:
                    raise ValidationError('XML_USAGE_POINT_SERVICE_MISMATCH')
        relation = {'usage_point': usage_uri, 'meter_reading': meter_uri, 'reading_type': rtypes[0],
                    'service_kind': service_kind,
                    'atom_ids': {key: resources[value]['atom_id'] if value else None
                                 for key, value in [('usage_point', usage_uri), ('meter_reading', meter_uri), ('reading_type', rtypes[0])]}}
        channel = channels.setdefault(meter_uri, {'source_channel': meter_uri, 'meter_code': '',
                   'commodity': commodity, 'unit': unit, 'semantics': 'delta',
                   'metadata': metadata, 'relationships': relation, 'readings': [], 'seen': set(),
                   'provenance': {'adapter': 'green-button-espi-delta-v2', 'interval_blocks': [],
                                  'source_currency_code': currency, 'financial_fields_imported': False}})
        block_span = block.find(E + 'interval')
        block_start = _xml_number(block_span, 'start') if block_span is not None else None
        block_duration = _xml_number(block_span, 'duration') if block_span is not None else None
        if block_span is not None and (block_duration <= 0 or not 631152000 <= block_start <= 4102444800):
            raise ValidationError('XML_BLOCK_TIME_INVALID')
        channel['provenance']['interval_blocks'].append({'uri': block_uri, 'atom_id': block_resource['atom_id'],
                                                        'start_utc': block_start, 'duration_s': block_duration})
        for index, ir in enumerate(block.findall(E + 'IntervalReading'), 1):
            total += 1
            if total > 20000:
                raise ValidationError('XML_EXCEEDS_20000_INTERVALS')
            periods = ir.findall(E + 'timePeriod')
            if len(periods) != 1:
                raise ValidationError('XML_INTERVAL_TIME_INVALID')
            start = _xml_number(periods[0], 'start')
            duration = _xml_number(periods[0], 'duration')
            if not 631152000 <= start <= 4102444800 or not 1 <= duration <= 2678400:
                raise ValidationError('XML_INTERVAL_TIME_OUT_OF_RANGE')
            if metadata['intervalLength'] and metadata['intervalLength'] != duration:
                raise ValidationError('XML_INTERVAL_DURATION_MISMATCH')
            if block_span is not None and (start < block_start or start + duration > block_start + block_duration):
                raise ValidationError('XML_READING_OUTSIDE_BLOCK_PERIOD')
            if start in channel['seen']:
                raise ValidationError('XML_DUPLICATE_INTERVAL_START')
            channel['seen'].add(start)
            raw_value = _xml_field(ir, 'value', '')
            # ESPI values are signed Int48; this forward subset rejects negatives.
            if not re.fullmatch(r'\d{1,15}', raw_value) or int(raw_value) > 140737488355327:
                raise ValidationError('XML_FORWARD_VALUE_REQUIRES_NONNEGATIVE_INT48')
            quantity = Decimal(raw_value) * (Decimal(10) ** exponent) / divisor
            if quantity > Decimal('1000000000'):
                raise ValidationError('XML_QUANTITY_OUT_OF_RANGE')
            if quantity.normalize().as_tuple().exponent < -9:
                raise ValidationError('XML_QUANTITY_PRECISION_UNSUPPORTED')
            quantity_text = format(quantity, 'f')
            if '.' in quantity_text and len(quantity_text.rsplit('.', 1)[1]) > 9:
                quantity_text = format(quantity.normalize(), 'f')
            quality = [_quality(_xml_field(q, 'quality')) for q in ir.findall(E + 'ReadingQuality')]
            if len(','.join(quality)) > 120:
                raise ValidationError('XML_QUALITY_LIST_TOO_LONG')
            raw_cost = _xml_field(ir, 'cost')
            if raw_cost is not None and (not re.fullmatch(r'-?\d{1,15}', raw_cost) or not -(2 ** 47) <= int(raw_cost) < 2 ** 47):
                raise ValidationError('XML_COST_FIELD_INVALID')
            channel['readings'].append({'start_utc': start, 'duration_s': duration,
                'quantity': quantity_text, 'quality': ','.join(quality) or metadata['defaultQuality'],
                'provenance': {'interval_block': block_uri, 'interval_reading_index': index,
                               'raw_value': raw_value, 'power_of_ten_multiplier': exponent,
                               'raw_quality_codes': quality, 'raw_cost': raw_cost}})
    for channel in channels.values():
        del channel['seen']
        channel['readings'].sort(key=lambda row: row['start_utc'])
        if not channel['readings']:
            raise ValidationError('XML_EMPTY_CHANNEL')
        previous_end = None
        for row in channel['readings']:
            if previous_end is not None and row['start_utc'] < previous_end:
                raise ValidationError('XML_OVERLAPPING_INTERVALS')
            previous_end = row['start_utc'] + row['duration_s']
    return list(channels.values())


def blank_bill():
    return {'provider':'','account_alias':'','invoice_number':'','bill_date':'','current_total':'',
            'lines':[{'meter_code':'','building':'','commodity':'electricity','period_start':'','period_end':'',
                      'usage':'','unit':'kWh','current_charge':'','usage_role':'consumption','read_type':'unknown'}]}
