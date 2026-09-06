"""Validate persisted review data before it can enter the financial ledger."""
import json
from .parsers import ValidationError, blank_bill, text, decimal_value


def decode(raw, kind):
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        if kind == 'bill':
            template = blank_bill()
            if set(value) != set(template) or not isinstance(value['lines'], list) or not 1 <= len(value['lines']) <= 50:
                raise ValueError()
            for key in template.keys() - {'lines'}:
                text(value[key], required=False)
            for line in value['lines']:
                if not isinstance(line, dict) or set(line) != set(template['lines'][0]):
                    raise ValueError()
                for item in line.values():
                    text(item, required=False)
        else:
            if not isinstance(value['metadata'], dict) or not isinstance(value['source_channel'], str):
                raise ValueError()
            readings = value['readings']
            if not isinstance(readings, list) or not 1 <= len(readings) <= 20000:
                raise ValueError()
            end = None
            for item in readings:
                if type(item['start_utc']) is not int or type(item['duration_s']) is not int or item['duration_s'] <= 0:
                    raise ValueError()
                if end is not None and item['start_utc'] < end:
                    raise ValueError()
                end = item['start_utc'] + item['duration_s']
                decimal_value(item['quantity'])
                text(item['quality'])
        return value
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValidationError('DRAFT_DATA_DAMAGED_RECOVERY_REQUIRED') from None


def payload(row, db=None):
    raw = (row['review_payload'] or row['payload']) if row['kind'] == 'bill' else row['payload']
    if db is not None and row['kind'] == 'bill' and row['review_payload'] and row['revision'] > 0:
        saved = db.execute('SELECT payload FROM draft_history WHERE staged_id=? AND revision=?', (row['id'], row['revision'])).fetchone()
        if not saved or saved[0] != row['review_payload']:
            raise ValidationError('DRAFT_DATA_DAMAGED_RECOVERY_REQUIRED')
    return decode(raw, row['kind'])
