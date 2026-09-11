# bcp-kit 核心索引（自动加载）

> 本仓库 = BCP 范式工具包（模板），自身亦按该范式运作（自举验证）。范式 spec：`README.md`；工作流：`.pi/APPEND_SYSTEM.md`；使用说明：`README.md`。

## 结构

| 件 | 本质 |
|----|------|
| `README.md` | 门面（一句话/安装/入口；液态，外部受众，变更无垒） |
| `plan.md` | 计划 schema（宿主无关） |
| `Blueprint.md` | 范式 spec + 设计（B 相位：边界/接口/约束/验收 + 机械契约；元批准结晶，R6 锚点对象） |
| `bcp/` | check.py（对碰器）+ bcp.toml（模板配置）+ evolve.py + ledger.jsonl |
| `.pi/` | pi 宿主适配层：APPEND_SYSTEM.md 工作流 + memory-gate（四闸门）/bcp-check 扩展 + prompts（含 /sleep） |
| `kit/` | 分发件：AGENTS.template.md（实例骨架）+ pre-commit（提交闸门）+ host-contract（宿主契约 + 15 向量）+ evolve-smoke（报告器冒烟）；不随项目复制 |
| `.pi/rules/` | 按域避坑储层（bcp 域），memory-gate 首触注入 |
| `bcp/plans/` | 本仓库自己的计划（实例层） |

## 规则域映射

bcp←`bcp/`、`.pi/extensions/`（`.pi/rules/bcp.md`；与 memory-gate ROUTES 同步）

## 硬约束

- 范式件（`Blueprint.md`/`plan.md`/`bcp/`/`.pi/`/`kit/`）变更 = 范式变更：先在 `Blueprint.md` 落设计章节（/bcp 两图+编号），计划锚引用后再动；会话内给用户看 diff 概览再落，需人批准。`README.md` = 门面（液态）：安装/入口类变更无需能垒。
- `bcp/check.py` 与 `bcp/bcp.toml` 改规则必须同步两处（R 注释标章节号）。
- 模板件内不得残留项目专属逻辑。
- 提交前 check 自动跑（pre-commit），FAIL 不落库。
