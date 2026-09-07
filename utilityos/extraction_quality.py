"""Local template-quality counts, distinct from safe operational diagnostics."""
from collections import Counter
import json
from .intake_storage import get_extraction
from .provider_templates import TEMPLATES, PROVIDERS
from .extraction_schema import HEADER_FIELDS, SERVICE_FIELDS


def report(store):
    counts=Counter()
    templates={template.version for template in TEMPLATES}
    fields=set(HEADER_FIELDS)|set(SERVICE_FIELDS)
    with store.connect() as db:
        for row in db.execute('SELECT document_id FROM document_extractions'):
            extraction=get_extraction(db,row[0])
            provider=extraction['provider_key'] if extraction['provider_key'] in PROVIDERS else 'unknown'
            template=extraction['template_version'] if extraction['template_version'] in templates else 'none'
            counts[(provider,template,'documents','')]+=1
            if extraction['layout_state']=='known_provider_unknown_layout':counts[(provider,template,'suspected_layout_drift','')]+=1
            if extraction['pdf_kind']=='unreadable':counts[(provider,template,'extraction_failure','')]+=1
        # Count only the final approved revision per invoice, not every save or
        # keystroke. Superseded/cancelled revisions remain historical evidence.
        for row in db.execute('''SELECT r.differences,s.document_id FROM intake_reviews r JOIN staged s ON s.id=r.staged_id
                             WHERE s.status='approved' AND r.revision=s.revision'''):
            extraction=get_extraction(db,row[1])
            provider=extraction['provider_key'] if extraction['provider_key'] in PROVIDERS else 'unknown'
            for difference in json.loads(row[0]):
                field=difference.get('field','').split('.')[-1]
                template=difference.get('template_version') if difference.get('template_version') in templates else 'none'
                if field in fields:counts[(provider,template,'field_correction',field)]+=1
    return {'format':'utilityos-extraction-quality-v1','contains_source_values':False,
            'automatic_template_changes':False,
            'rows':[{'provider_key':provider,'template_version':template,'kind':kind,'field':field,'count':count,
                     'candidate_improvement':kind=='suspected_layout_drift' or kind=='field_correction' and count>=2}
                    for (provider,template,kind,field),count in sorted(counts.items())]}
