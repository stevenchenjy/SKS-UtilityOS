from copy import deepcopy
from decimal import Decimal
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import pytest
from utilityos.parsers import ValidationError,parse_csv,parse_greenbutton,validate_bill,cents


def test_csv_parses_decimal_and_keeps_dates(raw_csv):
    bill=parse_csv(raw_csv)[0]
    assert bill['current_total']=='579.8'
    assert bill['lines'][0]['period_end']=='2026-09-01'
    assert bill['lines'][0]['usage']=='2860'

@pytest.mark.parametrize('value',["NaN","Infinity","1e6","$1,234.50","-5"])
def test_usage_rejects_ambiguous_or_invalid_numeric(bill,value):
    bill['lines'][0]['usage']=value
    with pytest.raises(ValidationError):validate_bill(bill)

@pytest.mark.parametrize('value',['2026-02-30','08/01/2026','2026-9-1',''])
def test_dates_require_iso_dates(bill,value):
    bill['bill_date']=value
    with pytest.raises(ValidationError):validate_bill(bill)

def test_current_charges_require_line_reconciliation(bill):
    bill['current_total']='580.00'
    with pytest.raises(ValidationError,match='CURRENT_TOTAL_DOES_NOT_MATCH'):validate_bill(bill)

def test_money_uses_integer_cents():
    assert cents('0.29')==29
    assert cents('-12.34')==-1234
    with pytest.raises(ValidationError):cents('1.001')

def test_end_date_is_exclusive_and_requires_positive_period(bill):
    bill['lines'][0]['period_end']=bill['lines'][0]['period_start']
    with pytest.raises(ValidationError):validate_bill(bill)

def test_units_are_checked_against_commodity(bill):
    bill['lines'][0]['unit']='gal'
    with pytest.raises(ValidationError,match='UNSUPPORTED_COMMODITY_UNIT'):validate_bill(bill)

def test_delivered_fuel_requires_purchase_label(bill):
    bill['lines'][0].update(commodity='heating_oil',unit='gal')
    with pytest.raises(ValidationError,match='DELIVERED_FUEL'):validate_bill(bill)

def test_charges_only_cannot_repeat_consumption(bill):
    bill['lines'][0]['usage_role']='charges_only'
    with pytest.raises(ValidationError,match='CHARGES_ONLY_USAGE'):validate_bill(bill)

def test_intra_invoice_usage_overlap_is_rejected(bill):
    bill['lines'].append(deepcopy(bill['lines'][0]))
    bill['current_total']='1159.6'
    with pytest.raises(ValidationError,match='CONSUMPTION_LINES_OVERLAP'):validate_bill(bill)

def test_meter_identity_must_be_consistent_in_invoice(bill):
    other=deepcopy(bill['lines'][0]);other.update(commodity='water',unit='gal')
    bill['lines'].append(other);bill['current_total']='1159.6'
    with pytest.raises(ValidationError,match='METER_IDENTITY_INCONSISTENT'):validate_bill(bill)

def test_csv_requires_known_template():
    with pytest.raises(ValidationError,match='CSV_HEADERS'):parse_csv(b'Random,Fields\n1,2\n')

def test_xml_applies_wh_to_kwh_multiplier(raw_xml):
    channel=parse_greenbutton(raw_xml)[0]
    assert len(channel['readings'])==96
    assert Decimal(channel['readings'][0]['quantity'])==Decimal('6.5')
    scaled=parse_greenbutton(raw_xml.replace(b'<powerOfTenMultiplier>0',b'<powerOfTenMultiplier>3'))[0]
    assert Decimal(scaled['readings'][0]['quantity'])==Decimal('6500')

def test_xml_preserves_utc_duration_and_quality(raw_xml):
    reading=parse_greenbutton(raw_xml)[0]['readings'][0]
    assert reading['duration_s']==900
    assert reading['start_utc']==int(datetime(2026,8,2,tzinfo=timezone.utc).timestamp())
    assert reading['quality']=='17'

def test_dst_repeated_local_hour_keeps_distinct_utc_readings():
    zone=ZoneInfo('America/New_York')
    a=datetime(2026,11,1,5,30,tzinfo=timezone.utc)
    b=datetime(2026,11,1,6,30,tzinfo=timezone.utc)
    assert a.astimezone(zone).hour==b.astimezone(zone).hour==1
    assert a.timestamp()!=b.timestamp()

@pytest.mark.parametrize('old,new',[(b'<uom>72',b'<uom>38'),(b'<commodity>1',b'<commodity>7'),(b'<flowDirection>1',b'<flowDirection>4'),(b'<accumulationBehaviour>4',b'<accumulationBehaviour>3')])
def test_xml_unsupported_measurements_fail_closed(raw_xml,old,new):
    with pytest.raises(ValidationError):parse_greenbutton(raw_xml.replace(old,new))

def test_xml_rejects_doctype_external_entity():
    evil=b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><x>&secret;</x>'
    with pytest.raises(ValidationError,match='XML_UNSAFE'):parse_greenbutton(evil)

def test_xml_relation_must_resolve(raw_xml):
    changed=raw_xml.replace(b'rel="related" href="https://synthetic.example.invalid/espi/1_1/resource/ReadingType/1"',b'rel="related" href="https://synthetic.example.invalid/unknown"')
    with pytest.raises(ValidationError,match='RELATION_UNRESOLVED'):parse_greenbutton(changed)

def test_xml_multiple_reading_types_use_links(raw_xml):
    raw=raw_xml.decode()
    entries=raw[raw.index('<entry>'):raw.rindex('</feed>')]
    second=entries.replace('/ReadingType/1','/ReadingType/2').replace('/MeterReading/1','/MeterReading/2').replace('<powerOfTenMultiplier>0','<powerOfTenMultiplier>3')
    mixed=raw.replace('</feed>',second+'</feed>').encode()
    channels=parse_greenbutton(mixed)
    assert len(channels)==2
    assert Decimal(channels[1]['readings'][0]['quantity'])==1000*Decimal(channels[0]['readings'][0]['quantity'])
