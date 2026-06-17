# Lark Doc Transfer Skill

Codex skill for transferring Feishu/Lark wiki or docx documents into the current user's own Feishu space.

The skill prefers native wiki copy when available, falls back to a rebuilt docx flow when needed, and emits a validation report so quality loss is explicit.

## Contents

- `skills/lark-doc-transfer/SKILL.md` - skill instructions
- `skills/lark-doc-transfer/scripts/transfer_lark_docs.py` - transfer automation
- `skills/lark-doc-transfer/references/transfer-quality.md` - quality and fallback notes
- `skills/lark-doc-transfer/agents/openai.yaml` - Codex agent metadata

## Install

Use Codex's skill installer with this repository path:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo zhangxiangbei/lark-doc-transfer-skill --path skills/lark-doc-transfer
```

On Windows, run the same installer from your local Codex skills directory, or ask Codex:

```text
Use $skill-installer to install lark-doc-transfer from https://github.com/zhangxiangbei/lark-doc-transfer-skill/tree/main/skills/lark-doc-transfer
```

## Usage

After installation, ask Codex:

```text
Use $lark-doc-transfer to transfer these Feishu/Lark document links into my personal space and report any degradation.
```

The transfer script expects `lark-cli` to be installed and authenticated for the target Feishu/Lark account.

## Notes

This repository intentionally excludes generated cache files and transfer reports.
