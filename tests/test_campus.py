"""A deterministic larger fixture reconciles costs, usage, and retained versions."""
import csv
import io
import time
from decimal import Decimal
import pytest
from scripts.synthetic_campus import seed, monthly_rows, csv_bytes
from utilityos.db import Store
from utilityos.service import Ledger
from utilityos.operations import backup,restore,check


def test_synthetic_campus_reports_history_backup_and_bounded_reads(ledger,tmp_path):
    assert csv_bytes(monthly_rows(0))==csv_bytes(monthly_rows(0))
    expected=seed(ledger)
    overview=ledger.overview()
    assert overview['stats']=={'buildings':20,'meters':60,'accounts':80,'pending':1,'approved_bills':1923}
    assert len(ledger.bills())==1927
    assert len(overview['months'])==24
    assert {r['month']:r['cents'] for r in overview['monthly']}==expected['expected_monthly_cents']
    assert len(ledger.intervals()['channels'])==3
    assert {m['commodity'] for m in ledger.inventory()['meters']}=={'electricity','water','natural_gas','heating_oil','propane'}
    rows=list(csv.DictReader(io.StringIO(ledger.export_csv().decode('utf-8-sig'))))
    assert len(rows)==1923
    assert sum(Decimal(r['current_charge']) for r in rows)==sum(expected['expected_monthly_cents'].values())/Decimal(100)
    assert all(r['usage']=='0' for r in rows if r['usage_role']=='charges_only')
    assert any(r['usage_role']=='delivery' for r in rows)
    pending=[s for s in ledger.stages() if s['status']=='pending']
    assert len(pending)==1
    assert ledger.stage(pending[0]['id'])['payload']['invoice_number']=='SYN-CAMPUS-PENDING'
    # Gross responsiveness guard, not a hardware-independent performance claim.
    start=time.perf_counter()
    for _ in range(3):ledger.overview();ledger.stages();ledger.audit_history()
    assert time.perf_counter()-start<10
    saved=backup(ledger.store);recovered=Store(tmp_path/'restored','demo');restore(recovered,saved,'demo')
    assert Ledger(recovered).export_csv()==ledger.export_csv()
    assert check(recovered)['audit']=='ok'
    with pytest.raises(ValueError,match='EMPTY_DEMO'):seed(ledger)
