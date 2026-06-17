---
name: lark-doc-transfer
description: Transfer Feishu/Lark wiki or docx documents into the current user's own Feishu space with lark-cli, using native copy when possible and a full-XML rebuild fallback with validation. Use when the user asks to save, copy, mirror, archive, batch transfer, or preserve multiple Feishu/Lark documents or wiki links in their personal document library, especially when repeated links need low-token automation and degradation reporting.
---

# Lark Doc Transfer

## Purpose

Use this skill to transfer one or more Feishu/Lark wiki/docx links into the current user's own Feishu space. Prefer the bundled script so large document XML stays out of the model context.

The script automates the workflow learned from real transfer attempts:

1. Verify `lark-cli` auth and required scopes.
2. Inspect each source link.
3. Try native wiki node copy into the target wiki space.
4. If native copy is denied, fetch full DocxXML and rebuild in `my_library`.
5. Convert unsupported `synced-source` wrappers into ordinary child blocks.
6. Remove unsupported readonly placeholders and image crop attributes.
7. Validate title/outline and block counts, then print a JSON report.

## Quick Start

From the installed skill directory, run:

```bash
python scripts/transfer_lark_docs.py "https://example.feishu.cn/wiki/xxxx"
```

Batch from a UTF-8 text file with one URL per line:

```bash
python scripts/transfer_lark_docs.py --input-file links.txt --report transfer-report.json
```

Transfer a wiki node and all descendants under a target wiki node:

```bash
python scripts/transfer_lark_docs.py --source-tree-url "https://source.feishu.cn/wiki/root" --target-parent-url "https://target.feishu.cn/wiki/parent" --report transfer-tree-report.json
```

When you already know native copy is blocked, skip it:

```bash
python scripts/transfer_lark_docs.py --skip-native-copy --input-file links.txt
```

For tree transfers, `--skip-native-copy` bypasses the native whole-tree copy attempt and previews or executes the XML rebuild fallback while preserving the source hierarchy:

```bash
python scripts/transfer_lark_docs.py --source-tree-url "https://source.feishu.cn/wiki/root" --target-parent-url "https://target.feishu.cn/wiki/parent" --skip-native-copy --dry-run
```

Preview without creating documents:

```bash
python scripts/transfer_lark_docs.py --dry-run "https://example.feishu.cn/wiki/xxxx"
```

Dry-run previews request shape. It does not prove that the source space will allow native copy at execution time. Use `--dry-run --skip-native-copy` to preview the XML rebuild path.

## Operating Rules

- Use `--as user` by default. Personal document libraries are user resources.
- Default target is `my_library`; override with `--target-position` only when the user asks.
- Use `--target-parent-url` for recursive wiki tree transfers so rebuilt children can be reattached to their recreated parent node.
- Keep URLs as opaque strings. Do not rewrite or decode Feishu URL query strings.
- Do not paste full XML into chat. Read the JSON report and summarize only important results.
- If auth or scopes are missing, follow the normal `lark-cli auth login --scope ...` split-flow from the Lark shared guidance.
- For a batch, save a report with `--report` so the user can review source-to-new URL mappings.

## Report Reading

Treat `items[].ok=true` as the success flag for each source.

Important fields:

- `method`: `native_wiki_copy`, `xml_rebuild`, or dry-run variants.
- `new_url`: the transferred document URL.
- `degradations`: expected fidelity differences.
- `warnings`: warnings returned by `lark-cli`.
- `validation.headings_match`: should be `true`.
- `validation.source_counts` and `validation.new_counts`: compare resource and formatting block counts.

For degradation meanings, read [references/transfer-quality.md](references/transfer-quality.md).

## When To Escalate

Stop and ask the user before deleting or replacing existing user documents. This script creates new documents only.

If a source is not `docx` or wiki-backed `docx`, native copy may still work; XML rebuild will report unsupported type. In that case, use the matching Lark skill for the underlying type.
