# bcp 域避坑（范式机械件：check.py / evolve.py / memory-gate / bcp.toml）

> memory-gate 首触 `bcp/`、`.pi/extensions/` 时注入。来源：2026-09-11 机械件接缝修复任务实测。

- gate↔evolve 字段契约是 §4.3 `{domain, file}`：memory-gate 域注入须写 `{domain, file}`（kind/target 为兼容字段），evolve 只统计 `kind=domain` 且兼容读 target——改任一端必须同步对端，错位 = 域统计全为 `?` 假域、死重误判、§4.6 冷启动保护失效。
- R5 存在性断言会打到范式自产运行时文件：`bcp/ledger.jsonl` 必须留在 bcp.toml ignore_prefixes，否则新项目从零建 `bcp/` 首跑即 FAIL；glob 无匹配 = 储层待积累（模板常态），静默跳过不算告警。
- 机械件测试用沙盒（cp 仓库 → git init → 重建空 ledger），evolve 验冷启动用 `--ledger` 指空文件；勿在真实账本做破坏性测试（append-only 证据流不可回滚）。
