# BCP 项目开发工作流（仅本目录加载）

范式 spec：`README.md`（§5 记忆分层）。项目索引与跨域硬约束：`AGENTS.md`（自动加载）；按域避坑细则在 `.pi/rules/*.md`，由 memory-gate 扩展在首次触碰对应代码域时自动拦截注入——预期行为，吸收后重试同一调用即可，非报错。
流程：设计决定文档（`Blueprint.md`，项目可选）→ 计划（瞬态）→ 代码 → `/check` 机械检查 → 经验沉淀回 `AGENTS.md` / `Blueprint.md`。

## 1. 设计（/bcp，项目有 Blueprint.md 时）

- 先读 `Blueprint.md` 相关章节，按 `AGENTS.md` 路径索引查代码确认现状，再动笔。
- 产出两张 Mermaid 图：总装图（flowchart：模块边界、调用关系、数据流）+ 部件图（classDiagram：关键类型）。每图带标题。
- 只画图，不写实现。新设计必须落章节编号——计划的 blueprint 字段和 check.py 靠它引用。
- 用户确认后：先把新设计决定写回 `Blueprint.md` 对应章节，再走 /plan。

## 2. 计划与实现（/plan → 写代码）

- 按根目录 `plan.md` 的 schema 生成计划，保存到 `bcp/plans/<slug>.plan.md`。
- accept 必须是可执行命令；接口签名以代码为准，不发明规则。
- 用户确认计划后按依赖顺序实现。蓝图假设落不了地（拆分不合理 / 类型不满足 / 依赖环），当场指出阻塞点，不拖到实现。
- 计划头 `mode` 字段（explore | infer，缺省 infer）：产出原始轨迹 / `deliverables/SKILL.md` / 技能进化类任务必须 `explore`——组装裸跑（不读储层、不召回案例），R7 机械裁决（README §2.3）。
- 执行中随进度勾选计划条目（`[x]`）——计划文件即执行状态 Σt，compaction 后重读它即可对齐进度（过程可丢，状态落盘）。

## 3. 机械检查（/check）

- 实现完成必须跑 /check（即 `python3 bcp/check.py --plan <计划> --collision`，零 LLM）。禁止用 LLM 自查替代。
- 按每条裁决标注的修复方向处理：改代码 / 改文档 / 改计划。改完重跑，直到 PASS。
- 提交闸门：pre-commit hook 自动重跑 check，FAIL 拒绝提交（绕过 = `--no-verify`，人可见越轨）。

## 4. 沉淀

- ≤3 条避坑 → 对应 `.pi/rules/<域>.md`（无对应文件则新建并在 AGENTS.md「规则域映射」表登记，格式 = 模式页：问题+根因+证据+规避句，README §5.5）。
- 0–1 条设计决定 → `Blueprint.md`（范式层 → `README.md`，需用户批准）。
- 删除已完成任务的计划文件；失败任务的计划连同裁决留档，供换会话续跑。
- 失败典藏：FAIL 任务强制压缩一条失败模式（标题+规避句 ≤200 字符 + `repro`=当轮失败命令，须只读断言 grep/test）→ 追加 `bcp/ledger.jsonl`（mode=failure）+ 对应 `.pi/rules/<域>.md`；只回注模式，不回注尸体（README §1）。repro 供 evolve ⑧ 节回放——规避句是假设，回放才成结论。
- 晋升/拒绝 evolve 候选后，追加 ledger 裁决记录（`verdict=PROMOTED|REJECTED`，`target`=规则名，`source`=来源失败模式，`evidence`=批准所据 diff 概览/决策 ID——能垒保真探针，防橡皮图章，README §4.5）——⑥ 节回放，防重复提案；⑧ 节审计缺证据指针。
- 技能沉淀 = 液态经验/裸跑轨迹结晶为固态 `deliverables/<name>/SKILL.md`（README §2.4，液→固相变）；默认文本轨道，Python 编译仅显式 `--compile-python` 或验证集成功率 ≥95% 触发。
- Sleep 巡检（活动量触发，README §4.7）：memory-gate 催醒或手动 `/sleep`——机械对账（evolve.py + selfcheck）→ 列清单 → 呈元裁决 → 打勾 → 清单完成重跑 evolve.py 落 REPORT 即醒。
- 元反馈协议（滞后验证，README §9.1 mode=verify）：阴 PASS 是入场券非完成态——任务收尾落 claim（`state=pending`，快照 claim/items/files/accept/anchors + `commits` 活动量基准，id=日期-slug）；元报障或修改产物时先查 pending，命中即访谈闭账（judged：verdicts 逐项 verified/drift/defect + attribution 归因层 design/plan/implementation/environment/requirement——environment 不罚 AI 只更新前提 + evidence 元实况 + route）。pending 是待办标记非阻塞标记，可永久存在、不自动 verified；触发口 = sleep 批量呈报（活动量分桶，可跳过）+ 报障即闭 + `/feedback` 主动闭。预填优先引用元既往 judged 模式（「你过去 N 次对 X 都归因 Y」）；显式教学（「以后 X 按 Y」）由书记员当场起草元技能（deliverables SKILL.md，同一 R8/召回/注册轨道）走结晶能垒，不散落对话；预填出自元技能时 judged 记 `prefill={skill,agree}`——确认率进 evolve ⑧，持续偏低呈降级候选。书记员纪律：只预填不代填、不推断元的意图、元确认前不落账、不翻案机械裁决。

风格：直接、简洁、工程化；先结论，再必要说明。
