# Local document extraction decision — 2026-09-06

## Evaluated components

Versions and requirements were read from the projects' current PyPI metadata,
maintainer documentation and downloaded wheel metadata. Only public software
metadata and fictional probe documents were used. No provider records were sent
to any service.

| Project | Evaluated release / license | Fit and decision |
|---|---|---|
| pdfplumber | 0.11.10, MIT; June 2026 release | Selected for native PDF text and character/line coordinates. Its small Python interface supplies actual page evidence. It is designed for digital text and does not claim OCR. |
| invoice2data | 1.0.1, MIT; August 2026 release | Evaluated in an isolated environment. Its reusable provider templates are useful, but the text-template interface does not preserve our per-field coordinates; its number parser returns float. Adapting evidence, exact decimals and layout geometry would duplicate most of the small required adapter. Use independent literal-label templates in this project; no code or built-in provider templates were copied. |
| Docling | 2.126.0, MIT; September 2026 release | Supports local/offline conversion and model prefetching. The current standard+VLM resolution on this Mac is 118 distributions and 409,276,440 bytes of wheels, before models. Includes Torch, torchvision, transformers, MLX, RapidOCR, OpenCV, NumPy/SciPy and document-format packages. Not selected for this bounded utility slice; no Docling inference or accuracy claim is made. |
| Granite-Docling-258M | IBM revision `982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe`, Apache-2.0 | Local document conversion model with an Apple Silicon MLX path. The model repository lists a 515,093,104-byte safetensors file, plus processor/tokenizer files. It emits candidate document structure, not authoritative utility amounts. Evaluated from the model card and file metadata; weights were not downloaded and inference was not run. |
| Tesseract through tesserocr | tesserocr 2.11.0 MIT; tested native Tesseract 5.5.1 Apache-2.0, Leptonica BSD-style | Selected as an optional small local scan fallback. The Apple Silicon wheel is 3,618,668 bytes, requires macOS 15+, and includes native libraries. A real rasterized fictional invoice recovered exact probe amounts and usage. Corpus accuracy must be measured separately. |

Sources: [pdfplumber](https://github.com/jsvine/pdfplumber),
[invoice2data source and readers](https://github.com/invoice-x/invoice2data),
[Docling package metadata](https://pypi.org/project/docling/2.126.0/),
[Docling offline and remote-service controls](https://docling-project.github.io/docling/usage/advanced_options/),
[IBM model card](https://huggingface.co/ibm-granite/granite-docling-258M),
[tesserocr](https://github.com/sirfz/tesserocr),
[Tesseract](https://github.com/tesseract-ocr/tesseract).

Docling's larger pipeline may become useful for complex tables or layouts that
the measured narrow parser cannot handle. That requires a separate corpus-based
comparison. Budget at least the measured wheel download plus the selected model
files, and additional space for the expanded environment and inference; a 2 GB
staging allowance is an estimate, not a measured Docling installation footprint.
No remote services, model server or AI runtime is added merely for possible
future use. Unknown layouts continue to require staff review/manual completion.

## Selected dependency closure and licensing

The added digital path is pdfplumber 0.11.10, pdfminer.six 20260107 (MIT), Pillow
12.3.0 (MIT-CMU), pypdfium2 5.13.0 (Apache-2.0/BSD-3-Clause and bundled dependency
notices), charset-normalizer 3.5.1 (MIT), cryptography 50.0.1
(Apache-2.0 OR BSD-3-Clause), cffi 2.1.1 (MIT-0), and pycparser 3.0 (BSD-3-Clause).
Wheels are available for the tested Python 3.13 / Apple Silicon environment.
pypdfium2's tested wheel requires macOS 13+. It supplies page rasterization;
no PyMuPDF, MuPDF or AGPL dependency is used.

The PDFium wheel's notices cover PDFium, FreeType, ICU, JPEG/PNG/TIFF/WebP-related
components, zlib and other permissively licensed dependencies. These notices
must remain with their wheels. The package advisory scan does not independently
audit every bundled native library. Bound parsing work and repeat upstream
native-engine/advisory review before school installation.

Optional tesserocr adds cysignals 1.12.6, **LGPL-3.0**. This is a separately
installed, replaceable Python extension; the source ZIP vendors neither library
nor wheel. Retain upstream licenses, allow replacement, and obtain corresponding
upstream source with any redistributed wheelhouse. A later self-contained binary
distribution must review these obligations again. See
[cysignals source/license](https://github.com/sagemath/cysignals) and
[tesserocr wheel metadata](https://pypi.org/project/tesserocr/2.11.0/).

ReportLab 5.0.1 is development-only, BSD licensed, for deterministic fictional
PDF generation. The corpus uses standard Helvetica/Courier; it does not use or
embed the separately licensed DarkGarden font shipped in ReportLab. ReportLab,
invoice2data experiments and audit tooling are not required for staff operation.
[ReportLab metadata](https://pypi.org/project/reportlab/5.0.1/).

All new direct projects had current maintenance/releases at review except the
deliberately stable trained English model. Current pins, wheel-only setup and
offline preparation avoid running source-install scripts. The initial external
probe environment inherited Python's older pip bootstrap; its scan found only
that already-known installer issue. It was upgraded to the project's reviewed
pip 26.2.1. Final application and optional-OCR advisory results belong in
`VERIFICATION.md`; no advisory is silently ignored.

## Local model and offline preparation

The chosen model is Tesseract `tessdata_fast` English LSTM, Apache-2.0, revision
`87416418657359cb625c412a48b6e1d6d41c29bd`. Its `eng.traineddata` is 4,113,088 bytes,
SHA-256 `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.
The [pinned upstream model](https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/eng.traineddata)
can be prepared on a staging computer and copied to an approved local model
directory with its [license](https://github.com/tesseract-ocr/tessdata_fast/blob/main/LICENSE).
No training, fine tuning, account, paid inference or automatic weight download
is required. Runtime must accept only the reviewed model hash and run without
network access. An absent or invalid model leaves digital extraction and manual
review available. Neither model files nor private document text belong in the
source release or diagnostic bundle.

## Measured footprint and native-engine review

On this Mac the eight added digital-path distributions occupy **48,376,338 bytes**
including installed Python bytecode. Optional tesserocr/cysignals add **9,820,454
bytes**, plus **4,113,088 bytes** for the reviewed English model. Development-only
ReportLab adds 8,353,157 bytes. These are measured incremental package footprints,
not total interpreter, working-memory, backup or source-document requirements.
Reserve at least 250 MB for a base code/environment staging area, another 50 MB
for OCR staging, and adequate independent source/backup space. Those headroom
figures are engineering allowances; actual total installation is measured in
`VERIFICATION.md`. No GPU, Torch, MLX runtime or separate model server is required
for the selected path. The tested optional arm64 wheel requires macOS 15+; digital
PDF rendering requires the tested macOS 13+ wheel. Other OS/Python combinations
need matching wheels and native acceptance before use.

Native inspection found PDFium **153.0.7999.0**, matching the selected
[pypdfium2 release](https://pypdfium2.readthedocs.io/en/stable/changelog.html).
The optional wheel contains Tesseract **5.5.1** and Leptonica **1.85.0**, not the
newer upstream Tesseract 5.5.3. The
[5.5.3 release](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.3)
includes traineddata memory-safety and LSTM-deserialization fixes. This matters:
UtilityOS permits only the fixed, verified English LSTM model and accepts no
uploaded/custom models or language/config selection. It supplies locally rendered
images to the API, never Tesseract's URL/image-file CLI. This limits exposure to
untrusted model deserialization; it does not make the native engine generally
safe for arbitrary model files. A newer wheel or privately built patched native
engine requires new provenance, license and benchmark review before changing the
pin. The optional path remains an experimentally tested development capability.

`otool -L` confirmed that the apparent zlib 1.2.12 dependency is **Apple's system
`/usr/lib/libz.1.dylib`**, not a vendored zlib wheel. Apple documents its fix for
CVE-2022-37434 in the
[Ventura 13 security update](https://support.apple.com/en-ae/102853).
A system library version string alone does not prove an unpatched upstream copy;
school IT must maintain the target OS. The wheel also links system libcurl; the
selected API path does not use network image retrieval. Its bundled image
libraries report libjpeg-turbo 3.2.0, libpng 1.6.58, libtiff 4.7.2 and libwebp 1.6.0;
linked zstd is 1.5.7. Keep all shipped notices. Python-package advisory scans do
not replace review of these native/OS libraries or hostile-document testing.

The optional closure is not silently called fully current just because its
Python wrapper is current. Upstream also reports OCR regressions on some inputs;
our small fictional corpus cannot disprove those. This supports always-reviewed
OCR candidates and a preserved manual path, not broad OCR accuracy claims.
[Maintainer issue #4523](https://github.com/tesseract-ocr/tesseract/issues/4523).
