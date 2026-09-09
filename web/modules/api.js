let csrf = '';
export function setCsrf(value) { csrf = value; }
export async function api(path, options = {}) {
  const method = options.method || 'GET';
  const headers = { ...(options.headers || {}) };
  if (method === 'POST') headers['X-CSRF-Token'] = csrf;
  let body = options.body;
  if (body && !(body instanceof File) && !(body instanceof Blob)) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(body);
  }
  const response = await fetch(`/api${path}`, { method, headers, body, credentials: 'same-origin', cache: 'no-store' });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || 'REQUEST_FAILED');
    error.status = response.status;
    throw error;
  }
  return data;
}
export function message(code) {
  const messages = {
    EXTRACTION_BUSY_RETRY_IMPORT: 'Another local PDF operation is finishing. Retry this file; it has not been saved as an empty draft.',
    SOURCE_EVIDENCE_REVIEW_REQUIRED: 'Confirm the extracted values against the original source before approving. Extraction alone does not verify a bill.',
    ACTIVE_ORIGINAL_INVOICE_REQUIRED: 'The original invoice is no longer active. Reopen its history and use the current version, or reject this draft.',
    PENDING_CORRECTION_ALREADY_EXISTS: 'A correction for this invoice is already awaiting review. Open it in the review queue.',
    DRAFT_CHANGED_REOPEN_REVIEW: 'This draft changed in another view. Reopen it before saving or approving.',
    MAPPING_CHANGED_REOPEN_INVENTORY: 'This mapping changed in another view. Reopen inventory before editing.',
    MAPPING_UNCHANGED: 'The mapping is unchanged. Close this form or enter the corrected label.',
    DUPLICATE_SOURCE_DOCUMENT: 'This exact file is already in the local ledger. Open its existing review item.',
    DUPLICATE_INVOICE: 'This provider, account, and invoice reference already exist in the approved ledger.',
    CURRENT_TOTAL_DOES_NOT_MATCH_LINE_CHARGES: 'Current charges must equal the sum of the line charges. Exclude balances carried forward.',
    APPROVED_CONSUMPTION_PERIOD_OVERLAP: 'This consumption period overlaps an approved reading for the same meter. Review the existing bill; use charges-only for a separate supplier charge.',
    EXISTING_METER_UNIT_OR_COMMODITY_MISMATCH: 'This meter already has a different utility type or unit. Correct the draft or use a separate service point.',
    EXISTING_METER_BUILDING_MISMATCH: 'The building name differs from this meter’s saved mapping. Use the saved building name; mapping changes require review.',
    NEW_METER_VERIFY_BUILDING_ASSIGNMENT: 'A new meter will be created. Verify its building assignment against the source.',
    UNASSIGNED_OR_SHARED_METER: 'This meter has no single building assigned. Its costs remain in Unassigned / shared.',
    DAILY_USAGE_ABOVE_150_PERCENT_OF_RECENT_MEDIAN: 'Daily usage exceeds 150% of the median of the previous three recorded periods. Check the reading and operating conditions.',
    ESTIMATED_READING: 'The supplier marked this reading as estimated.',
    DELIVERED_QUANTITY_IS_A_PURCHASE: 'Fuel deliveries represent purchased volume. Tank inventory is needed to calculate fuel consumed.',
    FUTURE_INVOICE_DATE: 'The invoice date is in the future. Check the source date.',
    CREDIT_VERIFY_CURRENT_CHARGES: 'This line includes a credit. Confirm its sign and accounting period.',
    FILL_REQUIRED_INVOICE_FIELDS: 'Complete the invoice fields using the original source.',
    CSV_HEADERS_DO_NOT_MATCH_TEMPLATE: 'This CSV has different columns. Use the supplied template; provider-specific mapping comes after a sample is reviewed.',
    XML_V01_SUPPORTS_ELECTRICITY_WH_ONLY: 'The pilot XML importer accepts incremental electricity measured in Wh. Other XML types need a tested adapter.',
    XML_REQUIRES_FORWARD_INCREMENTAL_ENERGY: 'This XML describes a different measurement type, such as export, net, cumulative, or demand. It needs a reviewed adapter.',
    CHARGES_ONLY_USAGE_MUST_BE_ZERO: 'Set usage to zero on a charges-only line. Record consumption once on the meter’s primary bill.',
    LOGIN_REQUIRED: 'Your local session expired. Sign in again.',
    PASSPHRASE_INCORRECT: 'The local app passphrase is incorrect.',
    DEMO_REQUIRES_SYNTHETIC_DATA_CONFIRMATION: 'Use synthetic files in demonstration mode and confirm the checkbox.',
    REVIEW_WARNINGS_AND_ACKNOWLEDGE: 'Review the warnings and confirm the source-check checkbox.'
  };
  return messages[code] || code.toLowerCase().replaceAll('_', ' ').replace(/^./, c => c.toUpperCase()) + '.';
}
