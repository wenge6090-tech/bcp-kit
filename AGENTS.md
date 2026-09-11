# bcp-kit 核心索引（自动加载）

> 本仓库 = BCP 范式工具包（模板），自身亦按该范式运作（自举验证）。范式 spec：`README.md`；工作流：`.pi/APPEND_SYSTEM.md`；使用说明：`README.md`。

## 结构

| 件 | 本质 |
|----|------|
| `README.md` / `plan.md` | 范式 spec + 计划 schema（工具包主体，宿主无关） |
| `Blueprint.md` | 范式自身设计蓝图（自举实例层：为什么/取舍/被拒方案）；范式变更第一步 /bcp 落章节，计划锚 `Blueprint§x.y` |
| `bcp/` | check.py（对碰器）+ bcp.toml（模板配置）+ evolve.py + ledger.jsonl |
| `.pi/` | pi 宿主适配层：APPEND_SYSTEM.md 工作流 + memory-gate（四闸门）/bcp-check 扩展 + prompts（含 /sleep） |
| `kit/` | 分发件：AGENTS.template.md（实例骨架，不随项目复制）+ pre-commit（提交闸门） |
| `.pi/rules/` | 按域避坑储层（bcp 域），memory-gate 首触注入 |
| `bcp/plans/` | 本仓库自己的计划（实例层） |

## 规则域映射

bcp←`bcp/`、`.pi/extensions/`（`.pi/rules/bcp.md`；与 memory-gate ROUTES 同步）

## 硬约束

- 工具包件（README.md/plan.md/bcp//.pi//kit/）变更 = 范式变更：先在 `Blueprint.md` 落设计章节（/bcp 两图+编号），计划锚引用后再动 spec；会话内给用户看 diff 概览再落，范式层变更需人批准。
- `bcp/check.py` 与 `bcp/bcp.toml` 改规则必须同步两处（R 注释标章节号）。
- 模板件内不得残留项目专属逻辑。
- 提交前 check 自动跑（pre-commit），FAIL 不落库。
