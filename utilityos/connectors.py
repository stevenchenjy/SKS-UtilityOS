"""Disabled remote acquisition boundary and deterministic, local-only rehearsal.

There is intentionally no HTTP implementation, authentication loader or schedule.
The fixture client models documented EPA XML consumption responses; it is not an
EPA TEST connection. Date periods remain candidates until their time basis and
meter mapping have been reviewed. No financial writes are exposed here.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Protocol
from defusedxml import ElementTree as ET
from .parsers import ValidationError, decimal_value, iso_date


class PortfolioManagerBoundary:
    """Only production-facing connector currently available to the application."""

    @staticmethod
    def status():
        return {'provider': 'ENERGY STAR Portfolio Manager', 'mode': 'disabled',
                'enabled': False, 'reason_code': 'SCHOOL_AUTHORIZATION_REQUIRED',
                'last_successful_sync': None, 'next_action': 'school_review',
                'manual_sync_available': False, 'scheduled_sync_available': False,
                'credentials_stored': False, 'external_test_verified': False}

    @staticmethod
    def configure(*_args, **_kwargs):
        raise ValidationError('EXTERNAL_CONNECTOR_DISABLED_SCHOOL_AUTHORIZATION_REQUIRED')

    @staticmethod
    def manual_sync():
        raise ValidationError('EXTERNAL_CONNECTOR_DISABLED_SCHOOL_AUTHORIZATION_REQUIRED')

    @staticmethod
    def disconnect():
        # No credential loader or persistent credential store exists in rc3.
        return PortfolioManagerBoundary.status()


@dataclass(frozen=True)
class FixtureMeter:
    property_id: str
    meter_id: str
    commodity: str
    unit: str


@dataclass(frozen=True)
class FixturePage:
    original: bytes
    next_page: int | None = None


class UsageConnectorClient(Protocol):
    """A future reviewed implementation must supply exact response evidence."""

    def consumption(self, meter: FixtureMeter, page: int) -> FixturePage: ...


class FixturePortfolioClient:
    """In-memory fictional responses only; no endpoints or secrets accepted."""

    def __init__(self, pages):
        self.pages = dict(pages)
        self.requests = []

    def consumption(self, meter, page):
        key = (meter.property_id, meter.meter_id, page)
        self.requests.append(key)
        response = self.pages.get(key)
        if not isinstance(response, FixturePage):
            raise ValidationError('CONNECTOR_FIXTURE_PAGE_UNAVAILABLE')
        return response


def _field(node, name):
    children = node.findall(name)
    if len(children) != 1 or len(children[0]) or not children[0].text:
        raise ValidationError('CONNECTOR_RESPONSE_FIELD_INVALID')
    value = children[0].text.strip()
    if len(value) > 120 or any(ord(c) < 32 for c in value):
        raise ValidationError('CONNECTOR_RESPONSE_FIELD_INVALID')
    return value


def _updated(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})', value):
        raise ValidationError('CONNECTOR_AUDIT_TIME_REQUIRES_OFFSET')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    except ValueError:
        raise ValidationError('CONNECTOR_AUDIT_TIME_INVALID') from None


def normalize_portfolio_fixture(raw, meter):
    """Normalize the documented metered-consumption subset, not bulk deliveries.

    Meter units come from explicitly selected fixture metadata, never guessed
    from numerical values or dates. Provider dates are retained without making
    an unsupported assumption about timezone or inclusive end dates.
    """
    if not isinstance(raw,bytes) or len(raw) > 1024 * 1024 or not raw:
        raise ValidationError('CONNECTOR_RESPONSE_SIZE_INVALID')
    allowed = {'electricity': {'kWh'}, 'natural_gas': {'therm'}, 'water': {'US_gal','m3'}}
    if meter.commodity not in allowed or meter.unit not in allowed[meter.commodity]:
        raise ValidationError('CONNECTOR_METER_UNIT_UNSUPPORTED')
    try:
        root = ET.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception:
        raise ValidationError('CONNECTOR_RESPONSE_XML_UNSAFE') from None
    if root.tag != 'meterData' or any(n.tag != 'meterConsumption' for n in root):
        raise ValidationError('CONNECTOR_METERED_CONSUMPTION_REQUIRED')
    if len(root) > 120:
        raise ValidationError('CONNECTOR_PAGE_EXCEEDS_120_RECORDS')
    candidates = []
    for entry in root:
        identifier = _field(entry, 'id')
        if not re.fullmatch(r'-?\d{1,20}', identifier):
            raise ValidationError('CONNECTOR_RECORD_ID_INVALID')
        if entry.attrib.get('estimatedValue') not in {'true','false'}:
            raise ValidationError('CONNECTOR_ESTIMATION_STATUS_REQUIRED')
        start, end = iso_date(_field(entry, 'startDate')), iso_date(_field(entry, 'endDate'))
        if end <= start:
            raise ValidationError('CONNECTOR_PERIOD_INVALID')
        audits = entry.findall('audit')
        if len(audits) != 1:
            raise ValidationError('CONNECTOR_AUDIT_REQUIRED')
        updated = _updated(_field(audits[0], 'lastUpdatedDate'))
        candidates.append({'kind': 'operational_usage', 'semantics': 'delta',
            'provider_record_id': identifier, 'property_id': meter.property_id, 'source_meter': meter.meter_id,
            'commodity': meter.commodity, 'unit': meter.unit,
            'period_start': start, 'period_end': end, 'time_basis': 'provider_date_period_uninterpreted',
            'quantity': format(decimal_value(_field(entry,'usage')), 'f'),
            'quality': 'estimated' if entry.attrib['estimatedValue'] == 'true' else 'provider_reported',
            'provider_updated_at': updated, 'approval_state': 'pending_operational_review'})
    return candidates


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',',':')).encode()).hexdigest()


class FixtureReviewQueue:
    """Disposable local mock sink; retains exact source bytes and every revision.

    This is not production persistence or an authoritative usage import. Keeping
    the sink separate lets later approved integration reuse existing source and
    operational-review services without gaining access to invoice approval.
    """

    def __init__(self):
        self.evidence = {}
        self.revisions = {}

    def accept_meter(self, candidates, originals):
        pending = deepcopy(self.revisions)
        retained = dict(self.evidence)
        for original in originals:
            retained[sha256(original).hexdigest()] = original
        inserted = duplicates = revisions = 0
        seen = {}
        for candidate in candidates:
            key = (candidate['property_id'], candidate['source_meter'], candidate['provider_record_id'])
            semantic = {k:v for k,v in candidate.items() if k not in {'provenance','provider_updated_at'}}
            fingerprint = _digest(semantic)
            if key in seen and seen[key] != fingerprint:
                raise ValidationError('CONNECTOR_CONFLICTING_RECORD_WITHIN_PULL')
            seen[key] = fingerprint
            history = pending.setdefault(key, [])
            if history and history[-1]['fingerprint'] == fingerprint:
                duplicates += 1
                continue
            prior = history[-1]['fingerprint'] if history else None
            history.append({'fingerprint': fingerprint, 'replaces': prior,
                            'candidate': deepcopy(candidate), 'requires_revision_review': prior is not None})
            inserted += 1
            revisions += int(prior is not None)
        self.evidence, self.revisions = retained, pending
        return {'candidates_added': inserted, 'duplicates': duplicates, 'revisions_pending_review': revisions}


class PortfolioFixtureRehearsal:
    """Explicit synthetic-only, manual rehearsal of selection and pull behavior."""

    def __init__(self, client, queue=None):
        # Accept only the concrete local client; no accidental remote transport
        # injection through the application or a broad duck-typed object.
        if type(client) is not FixturePortfolioClient:
            raise ValidationError('CONNECTOR_LOCAL_FIXTURE_CLIENT_REQUIRED')
        self.client = client
        self.queue = queue if queue is not None else FixtureReviewQueue()
        self.enabled = False
        self.meters = ()
        self.high_water = {}
        self.last_successful_sync = None
        self.last_attempt = None
        self.error_count = 0

    def configure(self, configuration):
        if (not isinstance(configuration,dict) or set(configuration) != {'enabled','synthetic_only','selections'}
            or configuration['enabled'] is not True or configuration['synthetic_only'] is not True):
            raise ValidationError('CONNECTOR_EXPLICIT_SYNTHETIC_CONFIGURATION_REQUIRED')
        selected = configuration['selections']
        if not isinstance(selected,list) or not 1 <= len(selected) <= 50:
            raise ValidationError('CONNECTOR_SELECTED_METERS_REQUIRED')
        meters = []
        for row in selected:
            if (not isinstance(row,dict) or set(row) != {'property_id','meter_id','commodity','unit'}
                or any(not isinstance(v,str) or not 1 <= len(v) <= 80 or any(ord(c)<33 for c in v) for v in row.values())
                or not row['property_id'].startswith('fixture-') or not row['meter_id'].startswith('fixture-')):
                raise ValidationError('CONNECTOR_FICTIONAL_SELECTION_REQUIRED')
            meter = FixtureMeter(**row)
            normalize_portfolio_fixture(b'<meterData/>',meter)
            meters.append(meter)
        if len({(m.property_id,m.meter_id) for m in meters}) != len(meters):
            raise ValidationError('CONNECTOR_DUPLICATE_SELECTION')
        if self.enabled:
            raise ValidationError('CONNECTOR_DISCONNECT_BEFORE_RECONFIGURING')
        self.meters, self.enabled = tuple(meters), True
        return self.status()

    def manual_sync(self, *, at):
        if not self.enabled:
            raise ValidationError('CONNECTOR_REHEARSAL_DISABLED')
        at = _updated(at)
        self.last_attempt = at
        errors = []
        counts = {'candidates_added':0,'duplicates':0,'revisions_pending_review':0}
        for meter in self.meters:
            key = (meter.property_id,meter.meter_id)
            candidates, originals, pages = [], [], set()
            page = 1
            try:
                while page is not None:
                    if type(page) is not int or page < 1 or page in pages or len(pages) >= 100:
                        raise ValidationError('CONNECTOR_PAGINATION_INVALID')
                    pages.add(page)
                    response = self.client.consumption(meter,page)
                    original = response.original
                    records = normalize_portfolio_fixture(original,meter)
                    for record in records:
                        record['provenance'] = {'adapter':'portfolio-manager-local-fixture-v1',
                                                'source_sha256':sha256(original).hexdigest(), 'page':page,
                                                'environment':'local_fixture'}
                    candidates.extend(records)
                    originals.append(original)
                    page = response.next_page
                result = self.queue.accept_meter(candidates,originals)
                for name in counts:
                    counts[name] += result[name]
                if candidates:
                    high_water = max(c['provider_updated_at'] for c in candidates)
                    self.high_water[key] = max(high_water,self.high_water.get(key,high_water))
            except ValidationError:
                # Fixed public error only: exception contents may contain private
                # remote text in a future implementation and must never escape.
                errors.append({'selection_index':self.meters.index(meter)+1,'code':'CONNECTOR_METER_PULL_FAILED'})
        self.error_count = len(errors)
        if not errors:
            self.last_successful_sync = at
        return {**counts, 'failed_meters': errors, 'status': self.status()}

    def status(self):
        return {'environment':'local_fixture', 'enabled':self.enabled,
                'selected_meter_count':len(self.meters), 'last_attempt':self.last_attempt,
                'last_successful_sync':self.last_successful_sync, 'failed_meter_count':self.error_count,
                'manual_sync_available':self.enabled, 'scheduled_sync_available':False,
                'credentials_stored':False, 'external_test_verified':False}

    def disconnect(self):
        self.enabled = False
        self.meters = ()
        self.high_water.clear()
        self.last_attempt = self.last_successful_sync = None
        self.error_count = 0
        return self.status()
