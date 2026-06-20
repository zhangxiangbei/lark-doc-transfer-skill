# 飞书文档迁移技能 / Lark Doc Transfer Skill

[中文说明](#中文说明) | [English Guide](#english-guide)

用于将飞书/Lark Wiki 或 Docx 文档迁移到当前用户自己的飞书空间，并对迁移质量进行验证的 Codex Skill。

A Codex Skill for transferring Feishu/Lark Wiki or Docx documents into the current user's own space with migration-quality validation.

原生 Wiki 复制可用时，技能会优先使用原生复制；权限不允许时，则使用完整 DocxXML 重建，并明确报告已知的格式降级。

The skill prefers native Wiki copy when available. When permissions block native copy, it falls back to a full DocxXML rebuild and explicitly reports known fidelity degradation.

## 中文说明

### 主要能力

- 迁移单个或批量飞书/Lark Wiki、Docx 链接。
- 递归迁移 Wiki 节点及其子节点，并保留层级关系。
- 优先尝试原生 Wiki 节点复制，以获得最佳保真度。
- 原生复制失败时自动回退到 DocxXML 重建。
- 验证标题、目录和资源块数量，并输出 JSON 报告。
- 支持 `--dry-run` 预览和 `--report` 保存迁移映射。

### 安装

让 Codex 使用技能安装器安装：

```text
使用 $skill-installer 从 https://github.com/zhangxiangbei/lark-doc-transfer-skill/tree/main/skills/lark-doc-transfer 安装 lark-doc-transfer。
```

也可以运行：

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo zhangxiangbei/lark-doc-transfer-skill --path skills/lark-doc-transfer
```

### 使用示例

```text
使用 $lark-doc-transfer 将这些飞书/Lark 文档链接迁移到我的个人空间，并报告任何质量损失。
```

脚本依赖已安装并完成目标飞书/Lark 账号认证的 `lark-cli`。

## English Guide

### Features

- Transfer individual or batch Feishu/Lark Wiki and Docx links.
- Recursively transfer Wiki nodes and descendants while preserving hierarchy.
- Prefer native Wiki node copy for the best fidelity.
- Fall back to a full DocxXML rebuild when native copy is blocked.
- Validate titles, outlines, and resource-block counts, then emit a JSON report.
- Support `--dry-run` previews and `--report` source-to-target mappings.

### Installation

Ask Codex to install the skill with the skill installer:

```text
Use $skill-installer to install lark-doc-transfer from https://github.com/zhangxiangbei/lark-doc-transfer-skill/tree/main/skills/lark-doc-transfer.
```

Or run:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo zhangxiangbei/lark-doc-transfer-skill --path skills/lark-doc-transfer
```

### Usage Example

```text
Use $lark-doc-transfer to transfer these Feishu/Lark document links into my personal space and report any degradation.
```

The script requires `lark-cli` to be installed and authenticated for the target Feishu/Lark account.

## Repository Contents / 仓库内容

- `skills/lark-doc-transfer/SKILL.md` - 技能说明 / Skill instructions
- `skills/lark-doc-transfer/scripts/transfer_lark_docs.py` - 迁移自动化 / Transfer automation
- `skills/lark-doc-transfer/references/transfer-quality.md` - 质量与降级说明 / Quality and fallback notes
- `skills/lark-doc-transfer/agents/openai.yaml` - Codex 界面元数据 / Codex interface metadata

生成的缓存、迁移报告和用户文档内容不会提交到本仓库。

Generated caches, transfer reports, and user document content are intentionally excluded from this repository.
