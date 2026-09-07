"""One bounded PDF task per child process. Source data never enters logs.

No network reader, external command from a document, or persistent page cache.
The parent enforces a wall deadline and kills this process on expiration.
"""
import base64
import io
import json
import logging
from pathlib import Path
import sys
from hashlib import sha256

MODEL_SHA256 = '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2'
MODEL_BYTES = 4113088
MAX_PAGES = 20
MAX_PIXELS = 12_000_000


def model_available(directory):
    if not directory:
        return False
    path = Path(directory) / 'eng.traineddata'
    return (not path.is_symlink() and path.is_file() and path.stat().st_size == MODEL_BYTES
            and sha256(path.read_bytes()).hexdigest() == MODEL_SHA256)


def render(raw, number, rotation=0, scale=1.5):
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(raw) as document:
        if not 1 <= len(document) <= MAX_PAGES or not 1 <= number <= len(document):
            raise ValueError('PDF_PAGE_LIMIT')
        page = document[number - 1]
        try:
            width, height = page.get_size()
            if not 0 < width <= 4000 or not 0 < height <= 4000 or width * height * scale * scale > MAX_PIXELS:
                raise ValueError('PDF_RESOURCE_LIMIT')
            bitmap = page.render(scale=scale, rotation=rotation)
            try:
                return bitmap.to_pil().copy()
            finally:
                bitmap.close()
        finally:
            page.close()


def ocr_page(raw, number, directory):
    import tesserocr
    from importlib.metadata import version
    from .provider_templates import PROVIDERS, HEADER_LABELS, SERVICE_LABELS, V2_HEADER, V2_SERVICE
    labels = set(HEADER_LABELS.values()) | set(SERVICE_LABELS.values()) | set(V2_HEADER.values()) | set(V2_SERVICE.values())
    parser_version = f'{tesserocr.tesseract_version().splitlines()[0]}/tesserocr-{version("tesserocr")}/tessdata-fast-87416418657359cb625c412a48b6e1d6d41c29bd'
    best = (0, [], 0, (612, 792))
    # Controlled rotations handle landscape scans. No probabilistic confidence
    # is exposed: every OCR candidate always requires source comparison.
    for rotation in (0, 90, 180, 270):
        image = render(raw, number, rotation, scale=2.5)
        try:
            lines = []
            with tesserocr.PyTessBaseAPI(path=directory, lang='eng', oem=tesserocr.OEM.LSTM_ONLY,
                                       psm=tesserocr.PSM.AUTO) as engine:
                engine.SetVariable('debug_file', '/dev/null' if sys.platform != 'win32' else 'NUL')
                engine.SetImage(image)
                engine.Recognize()
                iterator = engine.GetIterator()
                if iterator:
                    for item in tesserocr.iterate_level(iterator, tesserocr.RIL.TEXTLINE):
                        content = (item.GetUTF8Text(tesserocr.RIL.TEXTLINE) or '').strip()
                        box = item.BoundingBox(tesserocr.RIL.TEXTLINE)
                        if content and box:
                            lines.append({'text': content, 'page': number, 'bbox': [v / 2.5 for v in box],
                                          'method': 'ocr', 'parser_version': parser_version})
            score = sum(any(line['text'].startswith(label + ':') for label in labels) for line in lines) + sum(
                10 for line in lines if line['text'] in PROVIDERS.values())
            if score > best[0]:
                best = (score, lines, rotation, (image.width / 2.5, image.height / 2.5))
            if score >= 20:
                break
        finally:
            image.close()
    return best[1:]


def extract(raw, model_dir=None):
    import pdfplumber
    from .extraction import parse_lines
    lines, pages, codes = [], [], []
    available = model_available(model_dir)
    with pdfplumber.open(io.BytesIO(raw), strict_metadata=False) as document:
        if not 1 <= len(document.pages) <= MAX_PAGES:
            raise ValueError('PDF_PAGE_LIMIT')
        for page in document.pages:
            if not 0 < page.width <= 4000 or not 0 < page.height <= 4000 or len(page.chars) > 50000:
                raise ValueError('PDF_RESOURCE_LIMIT')
            extracted = page.extract_text_lines(layout=False, strip=True, return_chars=False)
            if sum(len(row['text']) for row in extracted) > 100000:
                raise ValueError('SOURCE_TEXT_LIMIT')
            text_length = sum(len(row['text']) for row in extracted)
            image_coverage = sum(max(0,image['x1']-image['x0'])*max(0,image['bottom']-image['top']) for image in page.images)/(page.width*page.height)
            # A digital footer over a scanned bill is still a scan. Do not let
            # a short branding/accessibility layer suppress the OCR fallback.
            native = text_length >= 60 and not (image_coverage > .5 and text_length < 400)
            if native:
                lines.extend({'text': row['text'], 'page': page.page_number,
                              'bbox': [row['x0'], row['top'], row['x1'], row['bottom']], 'method': 'native_text'}
                             for row in extracted)
                pages.append({'number': page.page_number, 'width': page.width, 'height': page.height, 'method': 'native_text'})
            else:
                try:
                    if not available:
                        raise ImportError()
                    scanned, rotation, dimensions = ocr_page(raw, page.page_number, str(model_dir))
                    lines.extend(scanned)
                    pages.append({'number': page.page_number, 'width': dimensions[0], 'height': dimensions[1],
                                  'rotation': rotation, 'method': 'ocr'})
                    codes.append('OCR_REVIEW_REQUIRED')
                except ImportError:
                    pages.append({'number': page.page_number, 'width': page.width, 'height': page.height, 'method': 'unavailable'})
                    codes.append('OCR_UNAVAILABLE_MANUAL_ENTRY')
    if len(lines) > 10000 or sum(len(row['text']) for row in lines) > 500000:
        raise ValueError('SOURCE_TEXT_LIMIT')
    return parse_lines(lines, pages, codes)


def main():
    logging.disable(logging.CRITICAL)
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
        resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
    except (ImportError, ValueError, OSError):
        pass
    from .extraction import empty_extraction
    try:
        request = json.loads(sys.stdin.buffer.read(12 * 1024 * 1024))
        raw = base64.b64decode(request['data'], validate=True)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('PDF_RESOURCE_LIMIT')
        if request.get('action') == 'render':
            image = render(raw, request['page'], request.get('rotation', 0))
            try:
                output = io.BytesIO()
                image.save(output, format='PNG')
                result = {'png': base64.b64encode(output.getvalue()).decode()}
            finally:
                image.close()
        else:
            result = extract(raw, request.get('model_dir'))
    except ImportError:
        result = empty_extraction('EXTRACTION_DEPENDENCY_UNAVAILABLE')
    except Exception as exc:
        # Exception messages can contain source text; only literal local codes
        # are accepted and no traceback is written to either output stream.
        code = str(exc) if type(exc) is ValueError and str(exc) in {'PDF_PAGE_LIMIT', 'PDF_RESOURCE_LIMIT', 'SOURCE_TEXT_LIMIT'} else 'PDF_UNREADABLE_MANUAL_ENTRY'
        result = empty_extraction(code)
    sys.stdout.write(json.dumps(result))


if __name__ == '__main__':
    main()
