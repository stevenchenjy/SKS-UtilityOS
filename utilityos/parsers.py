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
    parsed = urlsplit(urljoin(base, value))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', ''))


def parse_greenbutton(raw: bytes):
    """Limited DMD importer: forward, incremental electricity, Wh -> kWh.

    Traverses Atom links to resolve ReadingType per MeterReading. Stores UTC epoch
    seconds and source quality codes. Unsupported metadata fails closed. This is
    an independent subset implementation, without a certification claim.
    """
    try:
        root = ET.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception:
        raise ValidationError('XML_UNSAFE_OR_MALFORMED')
    if root.tag != A+'feed':
        raise ValidationError('GREEN_BUTTON_ATOM_FEED_REQUIRED')
    base = root.attrib.get('{http://www.w3.org/XML/1998/namespace}base','https://offline.invalid/')
    resources = {}
    blocks = []
    for entry in root.findall(A+'entry'):
        entry_base = entry.attrib.get('{http://www.w3.org/XML/1998/namespace}base',base)
        links = [(l.get('rel',''), uri(l.get('href',''),entry_base)) for l in entry.findall(A+'link')]
        self_links = [url for rel,url in links if rel=='self']
        content = entry.find(A+'content')
        if content is None or len(content)!=1:
            continue
        obj = content[0]
        if obj.tag in {E+'ReadingType', E+'MeterReading', E+'IntervalBlock'}:
            if len(self_links)!=1 or self_links[0] in resources:
                raise ValidationError('XML_RESOURCE_ID_MISSING_OR_DUPLICATE')
            resources[self_links[0]] = (obj,links)
            if obj.tag==E+'IntervalBlock':
                blocks.append((self_links[0],obj,links))
    if not blocks:
        raise ValidationError('XML_NO_INTERVAL_BLOCKS')
    channels = {}
    total = 0
    for block_uri, block, links in blocks:
        # The up link may identify the IntervalBlock collection. Resolve its parent.
        parents = []
        for rel, href in links:
            candidate = href.rsplit('/IntervalBlock',1)[0]
            if rel=='up' and candidate in resources and resources[candidate][0].tag==E+'MeterReading':
                parents.append(candidate)
        if len(parents)!=1:
            raise ValidationError('XML_METER_READING_RELATION_UNRESOLVED')
        meter_uri = parents[0]
        meter, mlinks = resources[meter_uri]
        rtypes = [href for rel,href in mlinks if rel=='related' and href in resources and resources[href][0].tag==E+'ReadingType']
        if len(rtypes)!=1:
            raise ValidationError('XML_READING_TYPE_RELATION_UNRESOLVED')
        reading, _ = resources[rtypes[0]]
        def number(name, default=None):
            value = reading.findtext(E+name, default)
            try:
                return int(value)
            except (ValueError,TypeError):
                raise ValidationError('XML_READING_TYPE_FIELD_MISSING_OR_INVALID')
        metadata = {key:number(key) for key in ['commodity','uom','powerOfTenMultiplier','flowDirection','accumulationBehaviour','kind']}
        if metadata['commodity']!=1 or metadata['uom']!=72 or metadata['kind']!=12:
            raise ValidationError('XML_V01_SUPPORTS_ELECTRICITY_WH_ONLY')
        if metadata['flowDirection']!=1 or metadata['accumulationBehaviour']!=4:
            raise ValidationError('XML_REQUIRES_FORWARD_INCREMENTAL_ENERGY')
        exponent = metadata['powerOfTenMultiplier']
        if not -12<=exponent<=12:
            raise ValidationError('XML_MULTIPLIER_OUT_OF_RANGE')
        metadata['defaultQuality'] = reading.findtext(E+'defaultQuality','unknown')
        metadata['intervalLength'] = number('intervalLength', '0')
        channel = channels.setdefault(meter_uri, {'source_channel':meter_uri, 'meter_code':'', 'unit':'kWh',
                                                   'metadata':metadata, 'readings':[], 'seen':set()})
        for ir in block.findall(E+'IntervalReading'):
            total += 1
            if total>20000:
                raise ValidationError('XML_EXCEEDS_20000_INTERVALS')
            period = ir.find(E+'timePeriod')
            try:
                start = int(period.findtext(E+'start'))
                duration = int(period.findtext(E+'duration'))
            except (ValueError,TypeError,AttributeError):
                raise ValidationError('XML_INTERVAL_TIME_INVALID')
            if not 631152000<=start<=4102444800 or not 1<=duration<=2678400:
                raise ValidationError('XML_INTERVAL_TIME_OUT_OF_RANGE')
            if metadata['intervalLength'] and metadata['intervalLength'] != duration:
                raise ValidationError('XML_INTERVAL_DURATION_MISMATCH')
            if start in channel['seen']:
                raise ValidationError('XML_DUPLICATE_INTERVAL_START')
            channel['seen'].add(start)
            value = decimal_value(ir.findtext(E+'value',''))
            quantity = value * (Decimal(10)**exponent) / 1000
            if quantity>Decimal('1000000000'):
                raise ValidationError('XML_QUANTITY_OUT_OF_RANGE')
            quality = [q.findtext(E+'quality','unknown') for q in ir.findall(E+'ReadingQuality')]
            channel['readings'].append({'start_utc':start,'duration_s':duration,
                                         'quantity':format(quantity,'f'),'quality':','.join(quality) or metadata['defaultQuality']})
    for channel in channels.values():
        del channel['seen']
        channel['readings'].sort(key=lambda row:row['start_utc'])
        if not channel['readings']:
            raise ValidationError('XML_EMPTY_CHANNEL')
        previous_end = None
        for row in channel['readings']:
            if previous_end is not None and row['start_utc']<previous_end:
                raise ValidationError('XML_OVERLAPPING_INTERVALS')
            previous_end = row['start_utc']+row['duration_s']
    return list(channels.values())


def blank_bill():
    return {'provider':'','account_alias':'','invoice_number':'','bill_date':'','current_total':'',
            'lines':[{'meter_code':'','building':'','commodity':'electricity','period_start':'','period_end':'',
                      'usage':'','unit':'kWh','current_charge':'','usage_role':'consumption','read_type':'unknown'}]}
