# bcp-kit — 项目开发范式工具包（pi 宿主适配）

BCP（蓝图完形协议）的可移植实现：**范式工具包**（宿主无关协议 + 机械闸门）与**项目实例层**（各项目自养）分离。设计定论全在 `BCP.md`，本 README 只讲怎么用。

## 两层结构

| 层 | 件 | 归属 |
|---|---|---|
| 工具包（本仓库） | `BCP.md` · `plan.md` · `bcp/`（check.py / bcp.toml / evolve.py / ledger） · `.pi/`（工作流 + 扩展 + prompts） · `kit/`（模板 + hook） | 复制到任何项目 |
| 项目实例 | `AGENTS.md`（项目索引） · `Blueprint.md`（设计定论，可选） · `.pi/rules/*.md`（项目代码域） · `bcp/plans/` | 各项目自养 |

## 新项目快速开始

```bash
# 1. 复制工具包到项目根（已有仓库）或以本仓库为模板新建
cp -r BCP.md plan.md bcp .pi kit <项目根>/

# 2. 填实例层
#    - AGENTS.md：按 kit/AGENTS.template.md 骨架填项目索引（≤6KB，check 不强制但墙纪律要求）
#    - bcp/bcp.toml：按需启用 R1–R4 项目专属规则（缺省跳过）
#    - .pi/extensions/memory-gate.ts：填 ROUTES 路径→域映射
# 3. 装提交闸门
cp kit/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# 4. 重启 pi 会话（.pi/ 变更需重启生效）
```

## 机械闸门（零 LLM，不靠自觉）

| 闸门 | 触发 | 作用 |
|---|---|---|
| memory-gate 域注入 | 首次触碰 ROUTES 域文件 | block + 注入 `.pi/rules/<域>.md` 全文 |
| memory-gate 大文件附注 | read >20KB（每文件一次） | 提示先 grep 定位再 offset/limit 定点读 |
| memory-gate compaction 恢复 | `session_compact` 后首次工具调用 | 注入"重读计划文件"（计划 = 执行状态 Σt） |
| /check（R5–R7 通用，R1–R4 按需） | 手动或实现完成时 | 机械裁决，FAIL 带修复方向 |
| pre-commit | 每次 git commit | check FAIL 拒绝提交（绕过 = `--no-verify`，人可见越轨） |
| evolve.py | 定期手动 | 晋升/降级候选数据，裁决权在人（§12.3） |

## 宿主与循环

pi 宿主不改内部循环（仅 `tool_call` 可 block）——编排强制靠上述闸门焊在必经之路上，而非改循环。**换宿主触发条件**（§13，防摇摆）：仅当 ① 现宿主钩子无法机械化的关键编排需求，且 ② 测量确认价值 > 迁移成本时评估；全插件 harness 为候选之一，也是无人值守瘦内核（V83 复苏路线）的底座选项。

## 沿革

范式与机械裁决经验源自 taiji 认知内核项目（已冻结，tag `v82-frozen`）；定论沿革 V80–V83 见 taiji 仓库 `Blueprint.md`。
