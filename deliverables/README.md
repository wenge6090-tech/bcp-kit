# 技能储层（固相资产，可选轨道）

液态经验（`.pi/rules/` 模式页、explore 裸跑轨迹、失败典藏）反复被召回/验证后，
经门控结晶为固态技能：`<name>/SKILL.md`。

结构契约（R8-skill-contract 机械校验，Blueprint §3.1）：

- frontmatter 三件套：`name`（标识）、`description`（一行式目录——pi 常驻系统提示，
  命中才读正文 = 渐进披露）、`validation`（验证命令或 `manual`——结晶凭证）
- 正文两节：`## 适用条件`（何时用/何时不用）、`## 溯源`（源自哪条失败模式/规则/任务，
  对应 ledger PROMOTED 记录）

召回：pi 宿主经 `.pi/settings.json` 挂载本目录；每次正文被读，memory-gate 追加
`kind=skill-recall` 事件，evolve ⑦ 节统计召回计数（召回=0 的技能是死重候选）。

**元技能**（面向元的技能变体，双螺旋另一股）：description 触发语义面向反馈访谈/裁决
呈报而非任务组装，注入时机随之；内容 = 元的归因模式/裁决偏好/流程程序性知识，
**只预填不代填**（书记员纪律）。同一 R8/召回/注册轨道，无新字段；活性 = skill-recall
（访谈中读正文）+ 确认率（judged.prefill，evolve ⑧，低于阈值呈降级候选）。
冷启动期零元技能是常态——先让账本攒确认数据。
