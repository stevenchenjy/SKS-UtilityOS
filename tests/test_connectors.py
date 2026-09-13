"""No external API calls: the deterministic connector rehearsal is local only."""
import json
import socket
from hashlib import sha256
import pytest
from utilityos.connectors import (PortfolioManagerBoundary, PortfolioFixtureRehearsal,
    FixturePortfolioClient, FixturePage, FixtureMeter, normalize_portfolio_fixture)
from utilityos.parsers import ValidationError


def response(usage='123.5', record='1001', updated='2026-09-01T00:00:00Z', estimated='false'):
    return f'''<meterData><meterConsumption estimatedValue="{estimated}"><id>{record}</id>
    <audit><createdBy>FICTIONAL_PRIVATE_SENTINEL</createdBy><lastUpdatedDate>{updated}</lastUpdatedDate></audit>
    <startDate>2026-08-01</startDate><endDate>2026-09-01</endDate><usage>{usage}</usage>
    <cost>9999.99</cost></meterConsumption></meterData>'''.encode()


def selection(meter='fixture-water',property_id='fixture-school'):
    return {'property_id':property_id,'meter_id':meter,'commodity':'water','unit':'US_gal'}


def configured(pages, selections=None):
    client=FixturePortfolioClient(pages)
    rehearsal=PortfolioFixtureRehearsal(client)
    rehearsal.configure({'enabled':True,'synthetic_only':True,'selections':selections or [selection()]})
    return rehearsal


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch):
    def fail(*a,**k):
        raise AssertionError('Connector tests must never open a socket')
    monkeypatch.setattr(socket,'create_connection',fail)
    monkeypatch.setattr(socket.socket,'connect',fail)


def test_live_boundary_disabled_rejects_credentials_and_manual_sync():
    b=PortfolioManagerBoundary()
    before=b.status()
    with pytest.raises(ValidationError,match='SCHOOL_AUTHORIZATION'):
        b.configure(username='SECRET_USERNAME',password='SECRET_PASSWORD',enabled=True)
    with pytest.raises(ValidationError,match='SCHOOL_AUTHORIZATION'):
        b.manual_sync()
    assert b.disconnect()==before
    assert not before['credentials_stored'] and not before['manual_sync_available']
    assert 'SECRET' not in json.dumps(b.status())


def test_mock_requires_explicit_synthetic_configuration():
    run=PortfolioFixtureRehearsal(FixturePortfolioClient({}))
    with pytest.raises(ValidationError,match='DISABLED'):
        run.manual_sync(at='2026-09-13T00:00:00Z')
    for config in ({'enabled':True}, {'enabled':True,'synthetic_only':False,'selections':[selection()]},
                   {'enabled':True,'synthetic_only':True,'selections':[selection()],'token':'SECRET'}):
        with pytest.raises(ValidationError):
            run.configure(config)
    with pytest.raises(ValidationError,match='FICTIONAL_SELECTION'):
        run.configure({'enabled':True,'synthetic_only':True,'selections':[selection('real-meter-id')]})


def test_only_local_concrete_client_admitted():
    class AccidentalRemote:
        def consumption(self,*args):
            raise AssertionError('Must never be called')
    with pytest.raises(ValidationError,match='LOCAL_FIXTURE'):
        PortfolioFixtureRehearsal(AccidentalRemote())


def test_repeated_selected_pull_idempotent_and_evidence_retained():
    raw=response()
    run=configured({('fixture-school','fixture-water',1):FixturePage(raw),
                    ('unselected','unselected',1):FixturePage(response('999'))})
    first=run.manual_sync(at='2026-09-13T00:00:00Z')
    second=run.manual_sync(at='2026-09-13T00:01:00Z')
    assert first['candidates_added']==1 and second['duplicates']==1
    assert len(run.queue.revisions)==1
    assert list(run.queue.evidence.values())==[raw]
    candidate=next(iter(run.queue.revisions.values()))[0]['candidate']
    assert candidate['approval_state']=='pending_operational_review'
    assert candidate['kind']=='operational_usage' and candidate['unit']=='US_gal'
    assert candidate['time_basis']=='provider_date_period_uninterpreted'
    assert candidate['provenance']['source_sha256']==sha256(raw).hexdigest()
    assert 'cost' not in candidate and 'current_charge' not in candidate
    assert run.high_water[('fixture-school','fixture-water')]=='2026-09-01T00:00:00+00:00'
    assert all(x[:2]==('fixture-school','fixture-water') for x in run.client.requests)


def test_old_period_correction_is_queued_for_revision_review():
    run=configured({('fixture-school','fixture-water',1):FixturePage(response())})
    run.manual_sync(at='2026-09-13T00:00:00Z')
    run.client.pages[('fixture-school','fixture-water',1)]=FixturePage(response('125',updated='2026-09-02T00:00:00Z'))
    result=run.manual_sync(at='2026-09-13T00:01:00Z')
    assert result['revisions_pending_review']==1
    versions=next(iter(run.queue.revisions.values()))
    assert len(versions)==2 and versions[1]['replaces']==versions[0]['fingerprint']
    assert versions[0]['candidate']['quantity']=='123.5'
    assert versions[1]['candidate']['quantity']=='125'
    assert len(run.queue.evidence)==2


def test_partial_failure_does_not_advance_failed_meter_or_lose_success():
    run=configured({('fixture-school','fixture-water',1):FixturePage(response()),
                    ('fixture-school','fixture-other',1):FixturePage(response('50'),next_page=2)},
                   [selection(),selection('fixture-other')])
    first=run.manual_sync(at='2026-09-13T00:00:00Z')
    assert first['candidates_added']==1 and len(first['failed_meters'])==1
    assert ('fixture-school','fixture-other') not in run.high_water
    assert run.last_successful_sync is None
    assert len(run.queue.revisions)==1
    run.client.pages[('fixture-school','fixture-other',2)]=FixturePage(response('60',record='1002'))
    second=run.manual_sync(at='2026-09-13T00:01:00Z')
    assert second['candidates_added']==2 and second['duplicates']==1
    assert second['status']['last_successful_sync']=='2026-09-13T00:01:00+00:00'
    assert len(run.queue.revisions)==3


def test_conflicting_or_cyclic_pull_does_not_partially_queue_meter():
    run=configured({('fixture-school','fixture-water',1):FixturePage(response(),next_page=2),
                    ('fixture-school','fixture-water',2):FixturePage(response('888'))})
    assert run.manual_sync(at='2026-09-13T00:00:00Z')['failed_meters']
    assert not run.queue.revisions and not run.queue.evidence and not run.high_water
    run.client.pages[('fixture-school','fixture-water',2)]=FixturePage(response('888'),next_page=1)
    assert run.manual_sync(at='2026-09-13T00:01:00Z')['failed_meters']
    assert not run.queue.revisions


def test_disconnect_clears_configuration_but_retains_review_evidence():
    run=configured({('fixture-school','fixture-water',1):FixturePage(response())})
    run.manual_sync(at='2026-09-13T00:00:00Z')
    state=run.disconnect()
    assert not state['enabled'] and state['selected_meter_count']==0
    assert not run.high_water and len(run.queue.evidence)==1
    with pytest.raises(ValidationError):
        run.manual_sync(at='2026-09-13T00:01:00Z')
    assert state['scheduled_sync_available'] is False


def test_status_allowlist_excludes_selection_values_original_text_and_quantities():
    run=configured({('fixture-school','fixture-water',1):FixturePage(response())})
    result=run.manual_sync(at='2026-09-13T00:00:00Z')
    output=json.dumps(result)
    for private in ('FICTIONAL_PRIVATE_SENTINEL','fixture-school','fixture-water','123.5','9999.99','1001'):
        assert private not in output
    assert set(run.status())=={'environment','enabled','selected_meter_count','last_attempt','last_successful_sync',
        'failed_meter_count','manual_sync_available','scheduled_sync_available','credentials_stored','external_test_verified'}


@pytest.mark.parametrize('raw', [b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><meterData>&e;</meterData>',
    b'<meterData><meterDelivery/></meterData>',response(estimated='unknown'),response(usage='-5'),
    response().replace(b'<endDate>2026-09-01',b'<endDate>2026-07-01'),
    response(updated='2026-09-01T00:00:00')])
def test_unsupported_response_semantics_are_rejected(raw):
    with pytest.raises(ValidationError):
        normalize_portfolio_fixture(raw,FixtureMeter(**selection()))
