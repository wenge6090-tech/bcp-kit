# bcp 域避坑（范式机械件：check.py / evolve.py / memory-gate / bcp.toml）

> memory-gate 首触 `bcp/`、`.pi/extensions/` 时注入。格式：模式页（问题+根因+证据+规避句，README §5.5）。
>
> **目录**（看此判断相关性，无需整读）：
> 1. gate↔evolve 字段契约错位——改单端 = 域统计全 `?` 假域 → 两端同步
> 2. 自产运行时文件触发 R5——ledger 未豁免 = 新项目首跑 FAIL → 留在 ignore_prefixes
> 3. 真实账本破坏性测试——append-only 不可回滚 → 沙盒 + `--ledger` 空文件
> 4. git porcelain 含空格文件名带引号——解析不剥 = 双向对碰两头错 → strip 引号
> 5. 计划 accept 命令引号嵌套——JSON→shell 双层转义拆命令 → 只用简单词/grep -E

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
- **规避句**：机械件测试一律沙盒；evolve 验冷启动用 `--ledger` 指空文件，勿碰真实账本。

## 模式 4：git porcelain 对含空格文件名加引号

- **问题**：R6 collision 对含空格/特殊字符路径报双向矛盾（「声明未改动」与「改动未声明」同时出现）。
- **根因**：git status --porcelain 对此类路径输出 C 风格引号包裹（`?? "a b.md"`），ln[3:] 不剥引号则与 files 声明永远不等。
- **证据**：2026-09-12 外部文档吸收任务（含空格文件名触发，改名消根 + strip 引号双修）。

## 模式 6：删除型任务与 R6 files 存在性断言冲突

- **问题**：删除文件的任务（git rm）把删除目标写进计划 files，对碰必 FAIL——三个检查互相矛盾（files 存在性要文件在、accept `test ! -f` 要文件删、改动检测要声明删除），无时点可同时满足。
- **根因**：R6 files 语义 = 修改/新建的现存文件（存在性断言），无「删除目标」表达。
- **证据**：2026-09-12 去外部化清洗任务实测（先删后碰 2 FAIL；恢复后碰 3 FAIL；failure 已入账）。
- **规避句**：删除型任务 files 只列修改/新建目标；删除验收走 accept（`test ! -f`）；对碰在删除 staged 后跑（R6 已排除 porcelain D 状态）。
- **规避句**：解析 git porcelain 输出必须 strip 引号；仓库文件名避免空格（消边缘 case 优于加代码）。

## 模式 5：计划 accept 命令的引号纪律

- **问题**：accept 命令含嵌套引号/正则转义时，R6 报「shell 语法错误未真正执行」或静默匹配失败。
- **根因**：计划文件是 JSON 嵌套 shell，`'\\|'` 双层转义后成字面 `\\|`；单引号内带逗号空格的短语被 bash -c 拆裂。
- **证据**：同上任务，T1/T4 首轮对碰即抓出（阴对碰的正常工作，不是 bug）。
- **规避句**：accept 用简单词（grep -q Word）或 grep -E 交替符；需复杂断言时写脚本文件再引用。
