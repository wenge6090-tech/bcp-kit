# plan — 计划 schema（唯一来源）

> 本文件只定义计划的 schema，不要把具体计划写进本文件。
> 具体计划保存到 `bcp/plans/<slug>.plan.md`：任务完成后删除；失败任务的计划连同检查记录留档。
> 机械校验：`./bcp/check.py --plan <计划文件> --collision`。范式背景见 `README.md`。

## schema

YAML 头（机器校验用）+ 简短正文（给人看）：

```yaml
goal: 一句话说清要做什么
mode: infer                   # 可选：explore | infer（缺省 infer）；产出 deliverables/SKILL.md 或 skill_evolution 任务必须 explore（R7，README §2.3）
items:
  - id: P1
    blueprint: §5.2            # 必填：设计章节锚 `§x.y`（默认 Blueprint.md）或 `文件§x.y`（如 README.md§2.3）；悬空 = FAIL
    files:                     # 必填：改哪些文件，精确到文件；声明了没改 / 改了没声明都算 FAIL（删除目标不进 files——用 accept 断言 test ! -f，§9.2）
      - src/orchestration/compile.rs
    interfaces:                # 推荐：关键签名，到代码文件里确认
      - "pub fn enqueue_compile_task"
    depends: []                # 依赖顺序，上游先做
    accept:                    # 必填：可执行命令（cargo test / grep / 冒烟），禁止散文
      - cargo test compile
```

## 生成规则

1. 项目有 `Blueprint.md` 则先读之定位设计章节；无则按 AGENTS.md 现状直接规划。
2. 对照 `AGENTS.md` 核对现状；接口签名引用既有契约，不发明。
3. 用户确认计划后才进入实现。
4. 技能进化 / 原始轨迹采集任务必须 `mode: explore`（组装相位裸跑，禁先验注入，README §2.3）；可复用成功轨迹按 README §2.4 结晶为固态技能（液→固相变，编译不默认）。

## 阻塞点（当场提出，不拖到实现）

- 模块拆分与 Blueprint.md 架构冲突；
- 接口签名与现有代码契约冲突；
- 依赖成环。

## 收尾

- 完成后：删除计划文件；避坑沉淀到 `AGENTS.md`，设计决定回写 `Blueprint.md`（需用户批准）。
- 失败时：计划连同裁决记录留档，供换会话续跑。
