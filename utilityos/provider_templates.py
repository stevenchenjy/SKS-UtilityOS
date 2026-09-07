"""Version-controlled literal-label templates, with no executable template code.

All providers here are fictional. Positions check public layout anchors only.
Template retirement changes future matching, never historical extraction rows.
"""
from dataclasses import dataclass

HEADER_LABELS = {
    'provider': 'Provider', 'invoice_number': 'Invoice reference', 'account_identifier': 'Account',
    'service_address': 'Service address', 'invoice_date': 'Invoice date', 'due_date': 'Due date',
    'currency': 'Currency', 'invoice_total': 'Current charges', 'previous_balance': 'Previous balance',
    'amount_due': 'Amount due', 'document_kind': 'Document kind', 'supplier_only': 'Supplier only',
    'delivery_only': 'Delivery only',
}
SERVICE_LABELS = {
    'meter_identifier': 'Meter', 'building': 'Building', 'utility_type': 'Utility',
    'period_start': 'Period start', 'period_end': 'End (exclusive)',
    'consumption_quantity': 'Usage', 'consumption_unit': 'Usage unit',
    'demand_quantity': 'Demand', 'demand_unit': 'Demand unit', 'delivery_quantity': 'Delivered volume',
    'quantity_treatment': 'Quantity treatment', 'reading_type': 'Reading type',
    'previous_reading': 'Previous reading', 'current_reading': 'Current reading',
    'current_charge': 'Service charge', 'supply_charge': 'Supply charge',
    'delivery_charge': 'Delivery charge', 'demand_charge': 'Demand charge',
    'taxes': 'Taxes', 'fees': 'Fees', 'credits': 'Credits',
}
V2_HEADER = {**HEADER_LABELS, 'invoice_number': 'Bill reference', 'account_identifier': 'Customer account',
             'invoice_date': 'Issued on', 'invoice_total': 'New charges'}
V2_SERVICE = {**SERVICE_LABELS, 'meter_identifier': 'Service identifier',
              'period_start': 'Service from', 'period_end': 'Service until (exclusive)',
              'consumption_quantity': 'Billed quantity', 'current_charge': 'Line total'}


@dataclass(frozen=True)
class Template:
    version: str
    provider_key: str
    provider_name: str
    anchor: str
    header_labels: dict
    service_labels: dict
    active: bool = True
    # Main anchor must remain in this public header band (PDF points).
    anchor_top: tuple[int, int] = (35, 110)


PROVIDERS = {
    'example_valley': 'Example Valley Electric',
    'fictional_springs': 'Fictional Springs Water',
    'sample_flame': 'Sample Flame Gas',
    'imaginary_fuels': 'Imaginary Fuels Cooperative',
    'example_supply': 'Example Supply Company',
}
TEMPLATES = tuple(
    Template(f'{key}_v{version}', key, name, f'Utility statement layout {version}',
             HEADER_LABELS if version == 1 else V2_HEADER,
             SERVICE_LABELS if version == 1 else V2_SERVICE)
    for key, name in PROVIDERS.items() for version in (1, 2)
) + (Template('example_valley_legacy_v0', 'example_valley', PROVIDERS['example_valley'],
              'Retired trial layout', HEADER_LABELS, SERVICE_LABELS, active=False),)
