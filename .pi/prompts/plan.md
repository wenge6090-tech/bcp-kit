---
description: 按根 plan.md 的 schema 生成实现计划，保存到 bcp/plans/
argument-hint: "[补充说明，可省略]"
---
# 实现计划

读根目录 `plan.md` 的 schema，生成计划。补充说明：${@:-无}

1. 项目有 `Blueprint.md` 则读之定位设计章节；接口签名经 `AGENTS.md` 索引到代码文件确认，不发明。
2. 计划保存到 `bcp/plans/<slug>.plan.md`：YAML 头 + 简短正文。
3. accept 必须是可执行命令（cargo test / grep / 冒烟），禁止散文。
4. 蓝图假设落不了地（拆分不合理 / 类型不满足 / 依赖环），当场指出阻塞点。

产出后等用户确认；确认后按依赖顺序实现，完成后跑 /check。
