"""Financial approval requires affirmative review and a current HTTP revision."""
from copy import deepcopy
import pytest
from utilityos.parsers import ValidationError, validate_bill


def warning_free_draft(ledger, raw_csv):
    first = ledger.import_file('synthetic-first.csv', raw_csv)['staged_ids'][0]
    ledger.approve_bill(first, ledger.stage(first)['payload'], True, revision=0)
    second = ledger.import_file('synthetic-next.csv', raw_csv + b'\n')['staged_ids'][0]
    payload = ledger.stage(second)['payload']
    payload['invoice_number'] = 'SYN-NEXT-PERIOD'
    payload['lines'][0].update(period_start='2026-09-01', period_end='2026-10-01')
    saved = ledger.save_draft(second, payload, 0)
    assert ledger.validate_draft(saved['payload'], second)['flags'] == []
    return second, saved


def database_state(ledger):
    with ledger.store.connect() as db:
        return tuple(db.iterdump())


INVALID_ACKNOWLEDGEMENTS = [
    {}, {'acknowledge': False}, {'acknowledge': None}, {'acknowledge': 0},
    {'acknowledge': 1}, {'acknowledge': 'true'}, {'acknowledge': 'false'},
    {'acknowledge': []}, {'acknowledge': {}},
]


@pytest.mark.parametrize('confirmation', INVALID_ACKNOWLEDGEMENTS)
def test_warning_free_service_approval_requires_literal_true(ledger, raw_csv, confirmation):
    item, saved = warning_free_draft(ledger, raw_csv)
    before = database_state(ledger)
    with pytest.raises(ValidationError, match='REVIEW_WARNINGS_AND_ACKNOWLEDGE'):
        ledger.approve_bill(item, saved['payload'], revision=saved['revision'], **confirmation)
    assert database_state(ledger) == before


@pytest.mark.parametrize('confirmation', INVALID_ACKNOWLEDGEMENTS)
def test_warning_free_http_approval_requires_literal_true(authenticated, raw_csv, confirmation):
    ledger = authenticated.app.state.ledger
    item, saved = warning_free_draft(ledger, raw_csv)
    before = database_state(ledger)
    response = authenticated.post(f'/api/staged/{item}/approve', json={
        'payload': saved['payload'], 'revision': saved['revision'], **confirmation,
    })
    assert response.status_code == 422
    assert 'REVIEW_WARNINGS_AND_ACKNOWLEDGE' in response.text
    assert database_state(ledger) == before


@pytest.mark.parametrize('revision', [
    {}, {'revision': None}, {'revision': False}, {'revision': True},
    {'revision': '0'}, {'revision': '1'}, {'revision': -1}, {'revision': 1.0},
    {'revision': []}, {'revision': {}},
])
@pytest.mark.parametrize('saved_review', [False, True])
def test_http_approval_rejects_missing_or_malformed_revision_without_changes(
        authenticated, raw_csv, revision, saved_review):
    ledger = authenticated.app.state.ledger
    item = ledger.import_file('synthetic.csv', raw_csv)['staged_ids'][0]
    original = ledger.stage(item)['payload']
    if saved_review:
        edited = deepcopy(original)
        edited['current_total'] = edited['lines'][0]['current_charge'] = '600.00'
        ledger.save_draft(item, edited, 0)
    before = database_state(ledger)
    response = authenticated.post(f'/api/staged/{item}/approve', json={
        'payload': original, 'acknowledge': True, **revision,
    })
    assert response.status_code == 422
    assert 'DRAFT_REVISION_REQUIRED' in response.text
    assert database_state(ledger) == before


def test_stale_approval_preserves_saved_values_then_current_revision_posts(authenticated, raw_csv):
    ledger = authenticated.app.state.ledger
    item, saved = warning_free_draft(ledger, raw_csv)
    original = deepcopy(saved['payload'])
    saved['payload']['current_total'] = saved['payload']['lines'][0]['current_charge'] = '600.00'
    current = ledger.save_draft(item, saved['payload'], saved['revision'])
    before = database_state(ledger)
    stale = authenticated.post(f'/api/staged/{item}/approve', json={
        'payload': original, 'acknowledge': True, 'revision': saved['revision'],
    })
    assert stale.status_code == 422
    assert 'DRAFT_CHANGED_REOPEN_REVIEW' in stale.text
    assert database_state(ledger) == before
    approved = authenticated.post(f'/api/staged/{item}/approve', json={
        'payload': current['payload'], 'acknowledge': True, 'revision': current['revision'],
    })
    assert approved.status_code == 200, approved.text
    assert ledger.stage(item)['bill']['current_total_cents'] == 60000
    assert ledger.stage(item)['payload'] == validate_bill(current['payload'])
