---
name: lark-doc-transfer
description: "使用 lark-cli 将飞书/Lark Wiki 或 Docx 文档迁移到当前用户自己的飞书空间，优先原生复制，并在需要时使用完整 XML 重建和质量验证。用于用户要求保存、复制、镜像、归档、批量迁移或保留多个飞书/Lark 文档或 Wiki 链接，尤其适合需要低 Token 自动化和降级报告的重复迁移。 / Transfer Feishu/Lark Wiki or Docx documents into the current user's own Feishu space with lark-cli, using native copy when possible and a full-XML rebuild fallback with validation. Use for saving, copying, mirroring, archiving, batch transferring, or preserving Feishu/Lark documents and Wiki links, especially when repeated links need low-token automation and degradation reporting."
---

# 飞书文档迁移 / Lark Doc Transfer

## 用途 / Purpose

使用此技能将一个或多个飞书/Lark Wiki 或 Docx 链接迁移到当前用户自己的飞书空间。优先运行随附脚本，避免大型文档 XML 进入模型上下文。

Use this skill to transfer one or more Feishu/Lark Wiki or Docx links into the current user's own space. Prefer the bundled script so large document XML stays out of the model context.

脚本执行以下流程 / The script performs this workflow:

1. 验证 `lark-cli` 认证和所需权限。 / Verify `lark-cli` authentication and required scopes.
2. 检查每个源链接。 / Inspect each source link.
3. 尝试将 Wiki 节点原生复制到目标空间。 / Try native Wiki node copy into the target space.
4. 原生复制被拒绝时，获取完整 DocxXML 并在 `my_library` 中重建。 / If native copy is denied, fetch full DocxXML and rebuild in `my_library`.
5. 将不支持的 `synced-source` 包装器转换为普通子块。 / Convert unsupported `synced-source` wrappers into ordinary child blocks.
6. 移除不支持的只读占位块和图片裁剪属性。 / Remove unsupported readonly placeholders and image crop attributes.
7. 验证标题、目录和块数量，然后输出 JSON 报告。 / Validate titles, outlines, and block counts, then print a JSON report.

## 快速开始 / Quick Start

迁移单个链接 / Transfer one link:

```bash
python scripts/transfer_lark_docs.py "https://example.feishu.cn/wiki/xxxx"
```

从 UTF-8 文本文件批量迁移，每行一个 URL / Batch from a UTF-8 file with one URL per line:

```bash
python scripts/transfer_lark_docs.py --input-file links.txt --report transfer-report.json
```

递归迁移 Wiki 节点及全部子节点 / Transfer a Wiki node and all descendants:

```bash
python scripts/transfer_lark_docs.py --source-tree-url "https://source.feishu.cn/wiki/root" --target-parent-url "https://target.feishu.cn/wiki/parent" --report transfer-tree-report.json
```

已知原生复制不可用时直接使用 XML 重建 / Skip native copy when it is already known to be blocked:

```bash
python scripts/transfer_lark_docs.py --skip-native-copy --input-file links.txt
```

预览递归重建流程并保留源层级 / Preview a tree rebuild while preserving source hierarchy:

```bash
python scripts/transfer_lark_docs.py --source-tree-url "https://source.feishu.cn/wiki/root" --target-parent-url "https://target.feishu.cn/wiki/parent" --skip-native-copy --dry-run
```

仅预览，不创建文档 / Preview without creating documents:

```bash
python scripts/transfer_lark_docs.py --dry-run "https://example.feishu.cn/wiki/xxxx"
```

`--dry-run` 只预览请求结构，不能证明正式执行时源空间允许原生复制。使用 `--dry-run --skip-native-copy` 可预览 XML 重建路径。

`--dry-run` previews request shape only; it does not prove that the source space will allow native copy at execution time. Use `--dry-run --skip-native-copy` to preview the XML rebuild path.

## 操作规则 / Operating Rules

- 默认使用 `--as user`；个人文档库属于用户资源。 / Use `--as user` by default; personal document libraries are user resources.
- 默认目标为 `my_library`；仅在用户明确要求时设置 `--target-position`。 / Default to `my_library`; set `--target-position` only when requested.
- 递归迁移使用 `--target-parent-url`，使重建后的子节点重新挂载到对应父节点。 / Use `--target-parent-url` for recursive transfers so rebuilt children attach to their recreated parent.
- 将 URL 视为不透明字符串；不要改写或解码飞书 URL 查询参数。 / Treat URLs as opaque strings; do not rewrite or decode Feishu URL query strings.
- 不要在对话中粘贴完整 XML；读取 JSON 报告并只总结重要结果。 / Do not paste full XML into chat; read the JSON report and summarize only important results.
- 认证或权限不足时，遵循 Lark shared guidance 中的 `lark-cli auth login --scope ...` 分步流程。 / If auth or scopes are missing, follow the `lark-cli auth login --scope ...` split flow from the Lark shared guidance.
- 批量迁移时使用 `--report` 保存源 URL 到新 URL 的映射。 / For batches, use `--report` to save source-to-new URL mappings.

## 读取报告 / Report Reading

以 `items[].ok=true` 作为每个源文档的成功标志。 / Treat `items[].ok=true` as the success flag for each source.

重要字段 / Important fields:

- `method`：`native_wiki_copy`、`xml_rebuild` 或 dry-run 变体。 / `native_wiki_copy`, `xml_rebuild`, or a dry-run variant.
- `new_url`：迁移后的文档链接。 / The transferred document URL.
- `degradations`：预期的保真差异。 / Expected fidelity differences.
- `warnings`：`lark-cli` 返回的警告。 / Warnings returned by `lark-cli`.
- `validation.headings_match`：应为 `true`。 / Should be `true`.
- `validation.source_counts` 与 `validation.new_counts`：比较资源和格式块数量。 / Compare resource and formatting block counts.

需要了解降级含义时，读取 [references/transfer-quality.md](references/transfer-quality.md)。

Read [references/transfer-quality.md](references/transfer-quality.md) for degradation meanings.

## 何时升级处理 / When To Escalate

删除或替换用户现有文档前必须停止并询问用户。此脚本只创建新文档。

Stop and ask the user before deleting or replacing existing documents. This script creates new documents only.

如果源对象不是 Docx 或 Wiki 内的 Docx，原生复制仍可能成功，但 XML 重建会报告类型不受支持。此时使用与底层资源类型匹配的 Lark Skill。

If a source is not Docx or Wiki-backed Docx, native copy may still work, but XML rebuild reports an unsupported type. Use the matching Lark Skill for the underlying resource type.
