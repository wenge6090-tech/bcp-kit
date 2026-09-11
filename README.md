# bcp-kit

**BCP（蓝图完形协议）**——让 LLM 主导的开发形成「设计 → 计划 → 代码 → 机械验证 → 经验沉淀」闭环的范式工具包：人（元）只做裁决，LLM（阳）完形产出，脚本（阴）机械对碰并记账。

> 📐 **设计文档（范式 spec、机械契约、全部设计论证）：[Blueprint.md](Blueprint.md)**

## 是什么

一套零 LLM 的机械件 + 提示词工作流，装进任何由 agent 开发的项目：

| 件 | 作用 |
|---|---|
| `bcp/check.py` | 机械对碰器：计划↔代码双向对账、文档引用完整性、技能结构闸（R1–R8） |
| `bcp/evolve.py` | 演化报告器：从证据账本产出规则晋升/降级候选 |
| `bcp/ledger.jsonl` | append-only 证据账本（所有裁决的数据源） |
| `.pi/` | pi 宿主适配层：memory-gate 四闸门注入 + 工作流提示词 + pre-commit |
| `deliverables/` | 技能资产轨道（可选），自带旗舰示例 systems-engineering-meta |

范式全貌与适用边界（什么场景该用/不该用）→ **[Blueprint.md §8](Blueprint.md)**

## 快速开始

```bash
# 1. 复制宿主无关件 + pi 适配层到项目根（已有仓库）或以本仓库为模板新建
cp -r README.md plan.md Blueprint.md bcp .pi <项目根>/

# 2. 填实例层
#    - AGENTS.md：按 kit/AGENTS.template.md 骨架填项目索引（≤6KB）
#    - bcp/bcp.toml：按需启用 R1–R4 项目专属规则（缺省跳过）
#    - .pi/extensions/memory-gate.ts：填 ROUTES 路径→域映射（空表 = 域注入空转）
# 3. 装提交闸门（hook 从源仓库 kit/ 取，kit/ 本身不进项目）
cp <bcp-kit>/kit/pre-commit <项目根>/.git/hooks/pre-commit && chmod +x <项目根>/.git/hooks/pre-commit
# 4. 范式健康自检：确认各闸门非空转（IDLE = 依赖缺失，形同虚设）
python3 bcp/check.py --selfcheck
# 5. 重启 pi 会话（.pi/ 变更需重启生效），再跑一次 --selfcheck 确认
```

## 许可证与贡献

- **许可证**：暂未声明（内部使用；如需开源请先补 LICENSE）。
- **贡献**：走 BCP 工作流——/bcp 设计落 Blueprint 章节（两图 + 编号，需元批准）→ /plan 计划锚引用 → 实现 → `/check` 机械对碰全绿。详见 [Blueprint.md](Blueprint.md) 变更工作流。
