# Transfer Quality Notes

The transfer script has two quality tiers:

1. Native wiki node copy: best fidelity when the source space permits `wiki +node-copy`.
2. Full-XML rebuild: reliable fallback for readable docx/wiki-docx documents, but not a byte-for-byte clone.

Known full-XML rebuild limitations:

- `synced-source` wrappers cannot be recreated by the write API. The script strips the wrapper and keeps its child blocks as ordinary content.
- `readonly-block` placeholders cannot be recreated. The script removes them and reports the removal.
- Image `crop` attributes are not accepted by the write API. The script removes them and reports the removal.
- Image `alt` text may be dropped by the write API even if present in source XML.
- Resource tokens for images, PDFs, PPTX, and videos are regenerated in the new document. Count parity matters more than token equality.

Recommended success criteria:

- `headings_match` is `true`.
- `img`, `source`, `cite`, `button`, and `callout` counts match unless the user accepts a specific loss.
- `degradations` contains only known full-XML limitations.
