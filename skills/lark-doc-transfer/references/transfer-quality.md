# 迁移质量说明 / Transfer Quality Notes

迁移脚本有两个质量层级 / The transfer script has two quality tiers:

1. 原生 Wiki 节点复制：源空间允许 `wiki +node-copy` 时保真度最高。 / Native Wiki node copy: best fidelity when the source space permits `wiki +node-copy`.
2. 完整 XML 重建：适用于可读取的 Docx 或 Wiki-Docx 文档，但并非逐字节克隆。 / Full-XML rebuild: reliable for readable Docx or Wiki-Docx documents, but not a byte-for-byte clone.

## 已知限制 / Known Limitations

- 写入 API 无法重建 `synced-source` 包装器。脚本会移除包装器，并将子块保留为普通内容。 / The write API cannot recreate `synced-source` wrappers. The script removes the wrapper and keeps child blocks as ordinary content.
- 无法重建 `readonly-block` 占位块。脚本会移除并报告该变化。 / `readonly-block` placeholders cannot be recreated. The script removes and reports them.
- 写入 API 不接受图片 `crop` 属性。脚本会移除并报告该变化。 / Image `crop` attributes are rejected by the write API. The script removes and reports them.
- 即使源 XML 中存在，图片 `alt` 文本也可能被写入 API 丢弃。 / Image `alt` text may be dropped by the write API even when present in source XML.
- 图片、PDF、PPTX 和视频的资源 Token 会在新文档中重新生成；数量一致比 Token 相同更重要。 / Resource tokens for images, PDFs, PPTX, and videos are regenerated; count parity matters more than token equality.

## 建议验收标准 / Recommended Success Criteria

- `headings_match` 为 `true`。 / `headings_match` is `true`.
- 除非用户接受特定损失，否则 `img`、`source`、`cite`、`button` 和 `callout` 数量应一致。 / `img`, `source`, `cite`, `button`, and `callout` counts match unless the user accepts a specific loss.
- `degradations` 只包含已知的完整 XML 重建限制。 / `degradations` contains only known full-XML limitations.
