"""Local source dispatch. Detection selects a review queue, never approval."""
import csv
import io
from pathlib import Path
from .parsers import REQUIRED_CSV, ValidationError
from .usage import UsageImport

ADAPTERS = (
    {'id': 'pdf_invoice', 'label': 'PDF invoice', 'kind': 'financial'},
    {'id': 'invoice_csv', 'label': 'Canonical invoice CSV', 'kind': 'financial'},
    {'id': 'green_button', 'label': 'Green Button XML', 'kind': 'operational'},
    {'id': 'usage_csv', 'label': 'Mapped usage CSV', 'kind': 'operational'},
    {'id': 'usage_xlsx', 'label': 'Mapped usage spreadsheet', 'kind': 'operational'},
)


def identify(filename, raw=None):
    extension = Path(filename).suffix.lower()
    if extension == '.pdf':
        return 'pdf_invoice'
    if extension == '.xml':
        return 'green_button'
    if extension == '.xlsx':
        return 'usage_xlsx'
    if extension == '.csv':
        if raw is None:
            return 'csv'
        try:
            headers = next(csv.reader(io.StringIO(raw.decode('utf-8-sig')), strict=True), [])
        except (UnicodeError, csv.Error):
            raise ValidationError('CSV_REQUIRES_UTF8') from None
        # An incomplete invoice-shaped file must fail invoice validation, rather
        # than silently become meter evidence through a different adapter.
        return 'invoice_csv' if REQUIRED_CSV.issubset(headers) or {'invoice_number', 'current_charge'} & set(headers) else 'usage_csv'
    raise ValidationError('SUPPORTED_FILES_CSV_XML_PDF_XLSX')


class SourceAdapters:
    def __init__(self, ledger):
        self.ledger = ledger
        self.usage = UsageImport(ledger)

    def import_file(self, filename, raw):
        adapter = identify(filename, raw)
        if adapter in {'usage_csv', 'usage_xlsx'}:
            result = self.usage.import_file(filename, raw)
            return {**result, 'adapter': adapter, 'usage_ids': [result['import_id']],
                    'staged_ids': [], 'count': 0 if result['duplicate_source'] else 1}
        return {**self.ledger.import_file(filename, raw), 'adapter': adapter, 'usage_ids': []}
