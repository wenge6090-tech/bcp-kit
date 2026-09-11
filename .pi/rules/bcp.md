# bcp 域避坑（范式机械件：check.py / evolve.py / memory-gate / bcp.toml）

> memory-gate 首触 `bcp/`、`.pi/extensions/` 时注入。格式：模式页（问题+根因+证据+规避句，README §5.5）。
>
> **目录**（看此判断相关性，无需整读）：
> 1. gate↔evolve 字段契约错位——改单端 = 域统计全 `?` 假域 → 两端同步
> 2. 自产运行时文件触发 R5——ledger 未豁免 = 新项目首跑 FAIL → 留在 ignore_prefixes
> 3. 真实账本破坏性测试——append-only 不可回滚 → 沙盒 + `--ledger` 空文件
> 4. git porcelain 含空格文件名带引号——解析不剥 = 双向对碰两头错 → strip 引号
> 5. 计划 accept 命令引号嵌套——JSON→shell 双层转义拆命令 → 只用简单词/grep -E
> 6. 删除型任务与 R6 files 冲突——存在性断言与删除验收必矛盾 → 删除目标走 accept
> 7. 跨任务未提交变更集污染对碰——git status 全量对账 → 先提交或共声明（SKILL.md 共声明触发 R7）
> 8. gate 改动无冒烟 = 静默死亡——异常被 catch 吞成 fail-open → 改后必跑契约向量 + 真件冒烟
> 9. 账本多态 mode 按 mode 取值——裁决记录无 commits = 基线静默清零 → 按字段判别
> 10. 计划机械约束三条——interfaces 扫描面 / yaml 围栏 / excludes 豁免 → 见条目

## 模式 1：gate↔evolve 字段契约错位

- **问题**：只改 memory-gate 或 evolve 单端的域注入字段，域统计全为 `?` 假域、死重误判、§4.6 冷启动保护失效。
- **根因**：两件各自消费对方写入的字段（gate 按 §4.3 写 `{domain, file}`，evolve 只统计 `kind=domain` 且兼容读 `target`），中间无 schema 校验层，错位是静默的。
- **证据**：2026-09-11 机械件接缝修复任务实测（修复前账本 gate 事件无 domain 字段）。
- **规避句**：改 gate↔evolve 任一端字段必须同步对端并读对方消费代码确认，不许假设字段名。

## 模式 2：自产运行时文件触发 R5

- **问题**：R5 存在性断言打到范式自产运行时文件 `bcp/ledger.jsonl`，新项目从零建 `bcp/` 首跑即 FAIL。
- **根因**：ledger 靠首次 append 才存在，文档引用它时文件尚不存在——文档断言与运行时文件的先后依赖。
- **证据**：同上任务实测；glob 零匹配静默跳过为模板常态（储层待积累）。
- **规避句**：`bcp/ledger.jsonl` 必须留在 bcp.toml `ignore_prefixes`；新增自产运行时文件时同步补豁免。

## 模式 3：真实账本破坏性测试

- **问题**：在真实 ledger.jsonl 上验证冷启动/空账本行为，污染不可回滚的证据流。
- **根因**：append-only 是 §4.3 法律，测试写入会永久混入 evolve 生产统计。
- **证据**：同上任务沙盒流程验证（cp 仓库→git init→重建空 ledger）。
- **规避句**：机械件测试一律沙盒；evolve 验冷启动用 `--ledger` 指空文件，勿碰真实账本。沙盒向量必须含畸形记录（schema 坏行/幽灵引用/重复记录）——报告器对坏 schema 必须「跳过+呈报」而非崩溃或静默混入（2026-09-11 ⑧ 审查实测：list 型 verdicts 直接 AttributeError 崩溃）。

## 模式 4：git porcelain 对含空格文件名加引号

- **问题**：R6 collision 对含空格/特殊字符路径报双向矛盾（「声明未改动」与「改动未声明」同时出现）。
- **根因**：git status --porcelain 对此类路径输出 C 风格引号包裹（`?? "a b.md"`），ln[3:] 不剥引号则与 files 声明永远不等。
- **证据**：2026-09-12 外部文档吸收任务（含空格文件名触发，改名消根 + strip 引号双修）。
- **规避句**：解析 git porcelain 输出必须 strip 引号；仓库文件名避免空格（消边缘 case 优于加代码）。

## 模式 6：删除型任务与 R6 files 存在性断言冲突

- **问题**：删除文件的任务（git rm）把删除目标写进计划 files，对碰必 FAIL——三个检查互相矛盾（files 存在性要文件在、accept `test ! -f` 要文件删、改动检测要声明删除），无时点可同时满足。
- **根因**：R6 files 语义 = 修改/新建的现存文件（存在性断言），无「删除目标」表达。
- **证据**：2026-09-12 去外部化清洗任务实测（先删后碰 2 FAIL；恢复后碰 3 FAIL；failure 已入账）。
- **规避句**：删除型任务 files 只列修改/新建目标；删除验收走 accept（`test ! -f`）；对碰在删除 staged 后跑（R6 已排除 porcelain D 状态）。

## 模式 7：跨任务未提交变更集污染对碰

- **问题**：上一任务的未提交改动（如新结晶的技能文件）留在工作树，本任务计划对碰报「改动未声明」FAIL，两任务互不相关也中招。
- **根因**：R6 collision 的 changed 集来自 git status 全量工作树（跨任务累积），declared 集只含当前计划 files——变更集未提交时两集必然错位。
- **证据**：2026-09-11 元技能 README 对齐任务实测（SKILL.md 未提交，首轮 FAIL；同会话还因 `;` 连接致 FAIL 后仍删了计划文件，被迫重建）。
- **规避句**：对碰前先提交上一任务，或在计划 files 中共声明同处变更集的文件（excludes 内路径除外，见模式 10）；共声明 SKILL.md 会触发 R7 强制 mode: explore（内容源须为元批准/裸跑，非先验召回）；check 后续动作用 && 链，FAIL 不续跑。

## 模式 8：gate 改动无冒烟 = 静默死亡

- **问题**：memory-gate 两处缺陷长期潜伏无人知觉：①域注入读规则用游离变量 `cwd`，ReferenceError 被 catch 吞成 fail-open——闸门①实际已死；② skill-recall 正则无捕获组，JS `dm[1]`=undefined → target 静默丢失，evolve 统计成 `?` 假域。TypeScript 能加载 ≠ 行为正确。
- **根因**：fail-open 律是双刃剑——不死锁的代价是一切异常都伪装成「规则缺失放行」；且召回事件从未发生过（召回=0），缺陷无自然触发机会。
- **证据**：2026-09-11 宿主契约抽取任务：契约向量集一跑即抓出（参考实现复现 IndexError；账本两处 FAIL_OPEN 为前者尾迹）；ledger 无任何 skill-recall 事件为后者佐证。
- **规避句**：改 memory-gate 后必跑两者——`python3 kit/host-contract.test.py`（15 向量：规则在/缺、捕获组、优先级序、冷启动文案）+ `.pi/gate-smoke.mjs`（真件导入 + mkdtemp 沙盒，测参考实现测不到的账本真实解析，真账本不触碰）；不许只信 TypeScript 加载成功。

## 模式 9：账本多态 mode 按 mode 取值 = 基线静默清零

- **问题**：sleep 闸与 `check.py --selfcheck` 读活动量基线时只判 `mode == "evolve"` 便取 `commits`；而 `mode=evolve` 是三态混用（REPORT 带 `commits`；PROMOTED/REJECTED 裁决记录无该字段）——末条裁决记录把基线读成 0，周期误报超阈，且文案谎称「液态经验在积压」。
- **根因**：账本 schema 里 `mode` 是「记录族」而非「记录类型」，类型靠字段存在性隐式区分；消费端按 mode 取值 = 字段契约错位（模式 1 同族，发生在同一文件内）。
- **证据**：2026-09-13 真件沙盒复现（REPORT `commits=30` 后追加 PROMOTED，32 commit 时闸门误报；空账本 +31 commit 谎称积压）。
- **规避句**：读账本统计必须**按字段判别而非按 mode 判别**（「mode=evolve 且 commits 为数值」）；新增裁决/控制类记录前先 grep 谁按 mode 取值。

## 模式 10：计划机械约束三条（扫描面 / 围栏 / excludes）

- **问题**：① 给 `.pi/`、`kit/` 里的文件写 `interfaces` 必 FAIL——R6 只在 `src/**/*.rs` 与 `bcp/**/*.py` 里找签名；② 计划头不套 yaml 围栏（三反引号 + yaml）→ 「未找到计划 YAML 头」；③ 误判「工作树脏必然 R6 FAIL」——`bcp.toml [rule.plan_collision] excludes` 中的路径不强制声明。
- **根因**：R6 的扫描面与豁免面是硬编码配置，plan.md schema 未显式提示。
- **证据**：2026-09-13 sleep 基线语义任务规划期实测（围栏缺失、interfaces 未命中、excludes 误判三连；实际 excludes 含 `bcp/`、`.pi/`、`README.md`、`AGENTS.md`、`Blueprint.md`）。
- **规避句**：`interfaces` 只用于 `src/*.rs`/`bcp/*.py`，其余文件用 accept grep（简单词）；计划头必须套 yaml 围栏（三反引号 + yaml）；excludes 内路径不必共声明（但声明了就必须真改动）。

## 模式 5：计划 accept 命令的引号纪律

- **问题**：accept 命令含嵌套引号/正则转义时，R6 报「shell 语法错误未真正执行」或静默匹配失败。
- **根因**：计划文件是 JSON 嵌套 shell，`'\\|'` 双层转义后成字面 `\\|`；单引号内带逗号空格的短语被 bash -c 拆裂。
- **证据**：同上任务，T1/T4 首轮对碰即抓出（阴对碰的正常工作，不是 bug）。
- **规避句**：accept 用简单词（grep -q Word）或 grep -E 交替符；需复杂断言时写脚本文件再引用。
