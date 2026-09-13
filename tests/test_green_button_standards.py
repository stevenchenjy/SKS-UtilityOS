"""Fictional ESPI feeds exercise the documented forward-delta subset."""
import json
import pytest
from utilityos.parsers import ValidationError, parse_greenbutton, uri


def feed(commodity=9, unit=128, kind=58, service_kind=2, multiplier=-1):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://synthetic.example.invalid/espi/">
<id>urn:uuid:00000000-0000-4000-8000-000000000001</id><title>FICTIONAL ESPI TEST ONLY</title><updated>2026-09-01T00:00:00Z</updated>
<entry><id>urn:uuid:00000000-0000-4000-8000-000000000002</id><title>Fictional usage point</title><updated>2026-09-01T00:00:00Z</updated><link rel="self" href="UsagePoint/fictional"/><content type="application/xml"><UsagePoint xmlns="http://naesb.org/espi"><ServiceCategory><kind>{service_kind}</kind></ServiceCategory></UsagePoint></content></entry>
<entry><id>urn:uuid:00000000-0000-4000-8000-000000000003</id><title>Fictional reading type</title><updated>2026-09-01T00:00:00Z</updated><link rel="self" href="ReadingType/fictional"/><content type="application/xml"><ReadingType xmlns="http://naesb.org/espi"><accumulationBehaviour>4</accumulationBehaviour><commodity>{commodity}</commodity><dataQualifier>12</dataQualifier><flowDirection>1</flowDirection><intervalLength>900</intervalLength><kind>{kind}</kind><powerOfTenMultiplier>{multiplier}</powerOfTenMultiplier><uom>{unit}</uom><defaultQuality>17</defaultQuality></ReadingType></content></entry>
<entry><id>urn:uuid:00000000-0000-4000-8000-000000000004</id><title>Fictional meter reading</title><updated>2026-09-01T00:00:00Z</updated><link rel="self" href="UsagePoint/fictional/MeterReading/1"/><link rel="up" href="UsagePoint/fictional/MeterReading"/><link rel="related" href="ReadingType/fictional"/><content type="application/xml"><MeterReading xmlns="http://naesb.org/espi"/></content></entry>
<entry><id>urn:uuid:00000000-0000-4000-8000-000000000005</id><title>Fictional interval block</title><updated>2026-09-01T00:00:00Z</updated><link rel="self" href="UsagePoint/fictional/MeterReading/1/IntervalBlock/1"/><link rel="up" href="UsagePoint/fictional/MeterReading/1/IntervalBlock"/><content type="application/xml"><IntervalBlock xmlns="http://naesb.org/espi"><interval><duration>1800</duration><start>1785628800</start></interval><IntervalReading><timePeriod><duration>900</duration><start>1785628800</start></timePeriod><value>125</value><ReadingQuality><quality>17</quality></ReadingQuality></IntervalReading><IntervalReading><timePeriod><duration>900</duration><start>1785629700</start></timePeriod><value>130</value></IntervalReading></IntervalBlock></content></entry>
</feed>'''.encode()


@pytest.mark.parametrize('commodity,unit,kind,category,normalized', [(9,128,58,2,'US_gal'),(9,42,58,2,'m3'),(7,169,12,1,'therm')])
def test_standard_combinations_preserve_units_scaling_links(commodity,unit,kind,category,normalized):
    channel = parse_greenbutton(feed(commodity,unit,kind,category))[0]
    assert channel['unit'] == normalized
    assert channel['semantics'] == 'delta'
    assert channel['metadata']['normalized_unit'] == normalized
    assert channel['readings'][0]['quantity'] == '12.5'
    assert channel['readings'][1]['quality'] == '17'
    assert channel['readings'][0]['provenance']['raw_value'] == '125'
    assert channel['relationships']['service_kind'] == category
    assert channel['relationships']['usage_point'].endswith('/UsagePoint/fictional')
    assert channel['relationships']['atom_ids']['reading_type'].endswith('0003')
    assert channel['provenance']['interval_blocks'][0]['duration_s'] == 1800


def test_legacy_electricity_metadata_stays_compatible(raw_xml):
    channel = parse_greenbutton(raw_xml)[0]
    assert channel['metadata'] == {'commodity':1,'uom':72,'powerOfTenMultiplier':0,'flowDirection':1,
                                   'accumulationBehaviour':4,'kind':12,'defaultQuality':'17','intervalLength':900}
    assert channel['relationships']['usage_point'] is None
    assert channel['readings'][0]['quantity'] == '6.5'


@pytest.mark.parametrize('before,after,code', [
    (b'<uom>128',b'<uom>130','COMMODITY_KIND_UNIT'),
    (b'<kind>58',b'<kind>12','COMMODITY_KIND_UNIT'),
    (b'<commodity>9',b'<commodity>11','COMMODITY_KIND_UNIT'),
    (b'<flowDirection>1',b'<flowDirection>4','FORWARD_INCREMENTAL'),
    (b'<accumulationBehaviour>4',b'<accumulationBehaviour>3','FORWARD_INCREMENTAL'),
    (b'<dataQualifier>12',b'<dataQualifier>2','QUALIFIER_OR_AGGREGATION'),
    (b'<quality>17',b'<quality>999','QUALITY_UNSUPPORTED'),
    (b'<quality>17',b'<quality>12','QUALITY_UNSUPPORTED'),
    (b'<quality>17',b'<quality>15','QUALITY_UNSUPPORTED'),
    (b'<value>125',b'<value>-125','NONNEGATIVE_INT48'),
    (b'<value>125',b'<value>12.5','NONNEGATIVE_INT48'),
    (b'<value>125',b'<value>140737488355328','NONNEGATIVE_INT48'),
    (b'<duration>1800',b'<duration>900','OUTSIDE_BLOCK_PERIOD'),
    (b'<ServiceCategory><kind>2',b'<ServiceCategory><kind>1','SERVICE_MISMATCH'),
    (b'UsagePoint/fictional/MeterReading"',b'UsagePoint/missing/MeterReading"','USAGE_POINT_RELATION'),
    (b'MeterReading/1/IntervalBlock"',b'MeterReading/1/IntervalBlockGarbage"','METER_READING_RELATION'),
])
def test_unsupported_or_conflicting_standard_fields_fail_closed(before, after, code):
    with pytest.raises(ValidationError, match=code):
        parse_greenbutton(feed().replace(before,after))


@pytest.mark.parametrize('fragment', ['<timeAttribute>57</timeAttribute>','<tou>1</tou>',
                                    '<phase>128</phase>','<aggregate>1</aggregate>',
                                    '<argument>1</argument>','<uom>128</uom>'])
def test_unsupported_metadata_and_duplicate_fields_rejected(fragment):
    raw=feed().replace(b'</ReadingType>',fragment.encode()+b'</ReadingType>')
    with pytest.raises(ValidationError):
        parse_greenbutton(raw)


def test_parent_resolution_obeys_nested_xml_base():
    raw=feed().replace(b'<entry><id>',b'<entry xml:base="nested/"><id>')
    channel=parse_greenbutton(raw)[0]
    assert '/espi/nested/UsagePoint/' in channel['relationships']['usage_point']


def test_query_and_fragment_ids_are_not_merged():
    assert uri('https://synthetic.example.invalid/a?revision=1') != uri('https://synthetic.example.invalid/a?revision=2')
    assert uri('https://synthetic.example.invalid/a#one') != uri('https://synthetic.example.invalid/a#two')


@pytest.mark.parametrize('uri_value', ['', 'file:///etc/passwd', 'https://user:password@synthetic.example.invalid/resource'])
def test_resource_uri_rejects_credentials_and_non_identifiers(uri_value):
    with pytest.raises(ValidationError):
        uri(uri_value)


def test_mixed_different_usage_points_do_not_collapse():
    first=feed(); second=feed(7,169,12,1)
    entries=second.split(b'<entry>',1)[1].rsplit(b'</feed>',1)[0]
    entries=b'<entry>'+entries.replace(b'fictional',b'second')
    parsed=parse_greenbutton(first.replace(b'</feed>',entries+b'</feed>'))
    assert [(p['commodity'],p['unit']) for p in parsed] == [('water','US_gal'),('natural_gas','therm')]


def test_missing_quality_kept_unknown_not_actual():
    raw=feed().replace(b'<defaultQuality>17</defaultQuality>',b'').replace(b'<ReadingQuality><quality>17</quality></ReadingQuality>',b'')
    assert all(r['quality']=='unknown' for r in parse_greenbutton(raw)[0]['readings'])


def test_new_files_do_not_change_stable_metadata():
    old=parse_greenbutton(feed())[0]
    new=parse_greenbutton(feed().replace(b'/IntervalBlock/1',b'/IntervalBlock/2'))[0]
    assert old['metadata']==new['metadata']
    assert old['provenance']!=new['provenance']


@pytest.mark.parametrize('commodity,unit,kind,category,meter_unit',[(9,128,58,2,'gal'),(9,42,58,2,'m3'),(7,169,12,1,'therm')])
def test_non_electricity_operational_approval_retains_evidence_without_charges(ledger,commodity,unit,kind,category,meter_unit):
    semantic='water' if commodity==9 else 'natural_gas'
    with ledger.store.connect() as db:
        db.execute('INSERT INTO meters(code,commodity,unit) VALUES (?,?,?)',('SYN-METER',semantic,meter_unit))
    raw=feed(commodity,unit,kind,category)
    stage=ledger.import_file('fixture.xml',raw)['staged_ids'][0]
    assert ledger.overview()['total_cents']==0
    assert ledger.approve_intervals(stage,'SYN-METER')['inserted']==2
    summary=ledger.intervals('SYN-METER')
    assert summary['total_readings']==2
    assert summary['selected']['unit']==('US_gal' if unit==128 else meter_unit)
    assert ledger.overview()['stats']['approved_bills']==0
    assert ledger.overview()['quantities']==[]
    assert next(ledger.store.sources.iterdir()).read_bytes()==raw
    duplicate=ledger.import_file('repeat.xml',raw+b'\n')['staged_ids'][0]
    assert ledger.approve_intervals(duplicate,'SYN-METER')['identical_readings_skipped']==2
    revised=ledger.import_file('revised.xml',raw.replace(b'<value>125',b'<value>126'))['staged_ids'][0]
    with pytest.raises(ValidationError,match='REVISION_CONFLICT'):
        ledger.approve_intervals(revised,'SYN-METER')
    assert ledger.stage(revised)['status']=='pending'
    assert ledger.intervals('SYN-METER')['readings'][0]['quantity']=='12.5'


def test_legacy_pending_draft_shape_and_quantities_are_still_approvable(ledger,raw_xml):
    with ledger.store.connect() as db:
        db.execute("INSERT INTO meters(code,commodity,unit) VALUES ('SYN-LEGACY','electricity','kWh')")
    stage=ledger.import_file('legacy.xml',raw_xml)['staged_ids'][0]
    parsed=parse_greenbutton(raw_xml)[0]
    legacy={k:parsed[k] for k in ('source_channel','meter_code','unit','metadata','readings')}
    legacy['readings']=[{k:r[k] for k in ('start_utc','duration_s','quantity','quality')} for r in parsed['readings']]
    assert legacy['readings'][0]['quantity']=='6.5'
    with ledger.store.connect() as db:
        db.execute('UPDATE staged SET payload=? WHERE id=?',(json.dumps(legacy),stage))
    assert ledger.approve_intervals(stage,'SYN-LEGACY')['inserted']==96


def test_extra_unresolved_parent_is_not_ignored():
    raw=feed().replace(b'<link rel="up" href="UsagePoint/fictional/MeterReading"/>',
        b'<link rel="up" href="UsagePoint/fictional/MeterReading"/><link rel="up" href="UsagePoint/missing/MeterReading"/>')
    with pytest.raises(ValidationError,match='USAGE_POINT_RELATION_UNRESOLVED'):
        parse_greenbutton(raw)


def test_supplied_usage_point_cannot_be_silently_left_unresolved():
    raw=feed().replace(b'<link rel="up" href="UsagePoint/fictional/MeterReading"/>',b'')
    with pytest.raises(ValidationError,match='USAGE_POINT_RELATION_UNRESOLVED'):
        parse_greenbutton(raw)


def test_small_scaled_values_fail_before_creating_damaged_review_draft(ledger,raw_xml):
    raw=raw_xml.replace(b'<powerOfTenMultiplier>0',b'<powerOfTenMultiplier>-12')
    with pytest.raises(ValidationError,match='XML_QUANTITY_PRECISION_UNSUPPORTED'):
        ledger.import_file('too-precise.xml',raw)
    assert ledger.stages()==[]


def test_trailing_zero_precision_is_normalized_without_rounding():
    raw=feed(multiplier=-12).replace(b'<value>125',b'<value>1000').replace(b'<value>130',b'<value>2000')
    parsed=parse_greenbutton(raw)[0]
    assert [r['quantity'] for r in parsed['readings']]==['0.000000001','0.000000002']


def test_quality_list_length_is_bounded_before_review(ledger):
    quality=b'<ReadingQuality><quality>17</quality></ReadingQuality>'
    raw=feed().replace(quality,quality*41)
    with pytest.raises(ValidationError,match='XML_QUALITY_LIST_TOO_LONG'):
        ledger.import_file('too-many-qualities.xml',raw)
    assert ledger.stages()==[]


def test_currency_and_cost_remain_provenance_without_financial_posting(ledger):
    raw=feed().replace(b'</ReadingType>',b'<currency>840</currency></ReadingType>')
    raw=raw.replace(b'<value>125</value>',b'<value>125</value><cost>98765</cost>')
    parsed=parse_greenbutton(raw)[0]
    assert parsed['provenance']['source_currency_code']==840
    assert parsed['provenance']['financial_fields_imported'] is False
    assert parsed['readings'][0]['provenance']['raw_cost']=='98765'
    assert parsed['readings'][0]['quantity']=='12.5'
    ledger.import_file('currency-evidence.xml',raw)
    assert ledger.overview()['total_cents']==0 and ledger.overview()['stats']['approved_bills']==0
    for fragment in (b'<currency>USD</currency>',b'<currency>65536</currency>',b'<currency>840</currency><currency>840</currency>'):
        with pytest.raises(ValidationError):
            parse_greenbutton(feed().replace(b'</ReadingType>',fragment+b'</ReadingType>'))


def test_distinct_query_resource_references_resolve_without_collision():
    raw=feed().replace(b'ReadingType/fictional',b'ReadingType/fictional?version=1')
    original=raw.split(b'<entry>',2)[2].split(b'</entry>',1)[0]
    second=b'<entry>'+original.replace(b'?version=1',b'?version=2').replace(b'<uom>128',b'<uom>42')+b'</entry>'
    parsed=parse_greenbutton(raw.replace(b'</feed>',second+b'</feed>'))[0]
    assert parsed['unit']=='US_gal'
    assert parsed['relationships']['reading_type'].endswith('?version=1')
