---
description: 画设计蓝图（Mermaid 总装图 + 部件图），先读 Blueprint.md（项目设计定论文档，无则先建）
argument-hint: "[变更描述，可省略]"
---
# 设计蓝图

目标：${@:-以当前会话上下文中的目标为准}

1. 读 `Blueprint.md` 相关章节，按 `AGENTS.md` 路径索引查代码确认现状。
2. 输出两张 Mermaid 图：总装图（flowchart：模块边界 / 调用关系 / 数据流）+ 部件图（classDiagram：关键 struct/enum/trait）。每图带标题。
3. 附简短说明：职责划分、风险点、涉及 Blueprint.md 哪些章节。

约束：只画图，不写代码；与 `Blueprint.md` 冲突以它为准，命名以代码为准。
新设计必须落章节编号。用户确认后：先把新章节写回 `Blueprint.md`，再走 /plan。
