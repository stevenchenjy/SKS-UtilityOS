"""Read-only building scopes shared by dashboard and invoice drill-down.

Scopes follow current meter mappings. Split invoices contribute only matching
line charges; no allocation, calendarization or new accounting state is created.
"""
import re
from .parsers import ValidationError


def reporting_month(month):
    if month is not None and (not isinstance(month, str) or
            not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', month) or month[:4] == '0000'):
        raise ValidationError('INVOICE_MONTH_INVALID')
    return month


def building_scope(db, building=None):
    selected = 'all' if building is None else str(building)
    options = [{'id': 'all', 'name': 'All buildings'},
               *[{'id': str(r['id']), 'name': r['name']} for r in
                 db.execute('SELECT id,name FROM buildings ORDER BY name,id')],
               {'id': 'unassigned', 'name': 'Unassigned / shared'}]
    option = next((item for item in options if item['id'] == selected), None)
    if option is None:
        raise ValidationError('BUILDING_FILTER_INVALID')
    if selected == 'all':
        clause, params = '1=1', ()
    elif selected == 'unassigned':
        clause, params = 'm.building_id IS NULL', ()
    else:
        clause, params = 'm.building_id=?', (int(selected),)
    return option, options, clause, params
