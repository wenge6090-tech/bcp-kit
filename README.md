# bcp-kit — 项目开发范式工具包（pi 宿主适配）

BCP（蓝图完形协议）的可移植实现：**范式工具包**（宿主无关协议 + 机械闸门）与**项目实例层**（各项目自养）分离。设计定论全在 `BCP.md`，本 README 只讲怎么用。

## 适用边界

BCP 的三相循环（蓝图→计划→完形→对碰→回流）为「人不在场 + 无现成裁判」的开放域设计（BCP §7.7 域错配）：

| 适用 | 不适用 |
|------|-------|
| 需求模糊、无现成测试、LLM 需独立完成多轮迭代的域 | 有完整 CI/CD + 测试覆盖的成熟代码库（自带裁判器） |
| 人只给蓝图、无法逐行 review 的场景 | 人可实时结对 / 逐行 review 的场景 |
| 需要跨会话、跨模型、跨人员的经验累积 | 一次性脚本、探索性原型 |

装错域 = 给自带裁判器的域上重机制，白付对碰税。

## 两层结构（诚实边界）

| 层 | 件 | 归属 |
|---|---|---|
| 工具包 · **真宿主无关** | `BCP.md` · `plan.md` · `bcp/`（check.py / bcp.toml / evolve.py / ledger） | 复制到任何项目，只依赖 Python 3.11+ 标准库（§8.1 最小契约） |
| 工具包 · **pi 专属适配** | `.pi/`（APPEND_SYSTEM 工作流 + memory-gate 三闸门 + bcp-check + prompts） | **换宿主 = 必须重写等价的机械注入层**，否则 §5 四层记忆分层与 §6 墙纪律只落地一半 |
| 项目实例 | `AGENTS.md`（项目索引） · `Blueprint.md`（可选） · `.pi/rules/*.md` · `bcp/plans/` | 各项目自养 |

`kit/` 为分发件（实例骨架 + pre-commit 模板），**不随项目复制**（防副本腐烂，§7.4）。

## 新项目快速开始

```bash
# 1. 复制宿主无关件 + pi 适配层到项目根（已有仓库）或以本仓库为模板新建
cp -r BCP.md plan.md bcp .pi <项目根>/

# 2. 填实例层
#    - AGENTS.md：按 kit/AGENTS.template.md 骨架填项目索引（≤6KB，check 不强制但墙纪律要求）
#    - bcp/bcp.toml：按需启用 R1–R4 项目专属规则（缺省跳过）
#    - .pi/extensions/memory-gate.ts：填 ROUTES 路径→域映射（空表 = 域注入空转）
# 3. 装提交闸门（hook 从源仓库 kit/ 取，kit/ 本身不进项目）
cp <bcp-kit>/kit/pre-commit <项目根>/.git/hooks/pre-commit && chmod +x <项目根>/.git/hooks/pre-commit
# 4. 范式健康自检：确认各闸门非空转（IDLE = 依赖缺失，形同虚设）
python3 bcp/check.py --selfcheck
# 5. 重启 pi 会话（.pi/ 变更需重启生效），再跑一次 --selfcheck 确认
```

## 机械闸门（零 LLM，不靠自觉）

| 闸门 | 触发 | 作用 |
|---|---|---|
| memory-gate 域注入 | 首次触碰 ROUTES 域文件 | block + 注入 `.pi/rules/<域>.md` 全文 |
| memory-gate 大文件附注 | read >20KB（每文件一次） | 提示先 grep 定位再 offset/limit 定点读 |
| memory-gate compaction 恢复 | `session_compact` 后首次工具调用 | 注入"重读计划文件"（计划 = 执行状态 Σt） |
| /check（R5–R7 通用，R1–R4 按需） | 手动或实现完成时 | 机械裁决，FAIL 带修复方向 |
| pre-commit | 每次 git commit | **只跑 static 规则集**（R5 等）；R6 计划对碰靠工作流中 /check 触发——失败留档的计划合法存在于 `bcp/plans/`，故提交闸门不跑 --plan（已知缝隙）。绕过 = `--no-verify`（人可见越轨） |
| evolve.py | 定期手动 | 晋升/降级候选数据，裁决权在人（§4.5） |

**开箱即用 ≠ 装完即安全**：R5 的保护范围 = docs 配置中文档的路径断言；R6 只在计划声明 blueprint 锚时对碰；R7 只在 files 含 SKILL.md 或 `skill_evolution: true` 时触发。空转的 check 比没有 check 更危险（虚假安全感）——装完先跑 `--selfcheck`。

## 宿主与循环

pi 宿主不改内部循环（仅 `tool_call` 可 block）——编排强制靠上述闸门焊在必经之路上，而非改循环。**换宿主触发条件**（§8.3，防摇摆）：仅当 ① 现宿主钩子无法机械化的关键编排需求，且 ② 测量确认价值 > 迁移成本时评估；全插件 harness 为候选之一，也是无人值守瘦内核（V83 复苏路线）的底座选项。

## 沿革

范式与机械裁决经验源自 taiji 认知内核项目（已冻结，tag `v82-frozen`）；定论沿革 V80–V83 见 taiji 仓库 `Blueprint.md`。
