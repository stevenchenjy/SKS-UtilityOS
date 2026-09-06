"""Explicit current mapping edits with private before/after audit records."""
from .audit import now, event
from .parsers import ValidationError, text
from .lifecycle import reason_text


class InventoryEditing:
    def edit_inventory(self, kind, entity_id, before, value, reason, acknowledge=False):
        if kind not in {'building', 'meter'}:
            raise ValidationError('INVENTORY_EDIT_KIND_INVALID')
        if acknowledge is not True:
            raise ValidationError('CONFIRM_MAPPING_REPORTING_EFFECT')
        value = text(value, required=kind == 'building')
        before = text(before, required=False)
        reason = reason_text(reason)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if kind == 'building':
                row = db.execute('SELECT name FROM buildings WHERE id=?', (entity_id,)).fetchone()
                current = row['name'] if row else None
            else:
                row = db.execute('SELECT COALESCE(b.name,\'\') name FROM meters m LEFT JOIN buildings b ON b.id=m.building_id WHERE m.id=?', (entity_id,)).fetchone()
                current = row['name'] if row else None
            if current is None:
                raise ValidationError('INVENTORY_ITEM_NOT_FOUND')
            if current != before:
                raise ValidationError('MAPPING_CHANGED_REOPEN_INVENTORY')
            if current == value:
                raise ValidationError('MAPPING_UNCHANGED')
            if kind == 'building':
                if db.execute('SELECT 1 FROM buildings WHERE name=? AND id<>?', (value, entity_id)).fetchone():
                    raise ValidationError('BUILDING_LABEL_ALREADY_EXISTS')
                db.execute('UPDATE buildings SET name=? WHERE id=?', (value, entity_id))
            else:
                building_id = None
                if value:
                    db.execute('INSERT OR IGNORE INTO buildings(name) VALUES (?)', (value,))
                    building_id = db.execute('SELECT id FROM buildings WHERE name=?', (value,)).fetchone()[0]
                db.execute('UPDATE meters SET building_id=? WHERE id=?', (building_id, entity_id))
            history_id = db.execute('''INSERT INTO inventory_history(at,kind,entity_id,before_value,after_value,reason)
                VALUES (?,?,?,?,?,?)''', (now(), kind, entity_id, before, value, reason)).lastrowid
            event(db, 'EDIT_BUILDING_LABEL' if kind == 'building' else 'EDIT_METER_MAPPING', subject_kind='inventory_change', subject_id=history_id)
        return self.inventory()
