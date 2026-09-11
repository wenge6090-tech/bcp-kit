# BCP 宿主行为契约（注入层）v1

> 定义 §5 记忆分层 + §6 墙纪律在宿主侧执行体（pi 中为 `.pi/extensions/memory-gate.ts`）
> 的行为契约——**换宿主重写等价机械层时的对碰面，不猜适配层源码**。
> 本契约只覆盖注入层；对碰器/报告器（`bcp/check.py`、`bcp/evolve.py`）由 README §8.1
> 最小契约覆盖（Python 3.11+ 标准库，直接复制）。

## 1. 宿主必须提供的钩子

| 钩子 | 用途 |
|---|---|
| 工具调用前拦截 | read/edit/write 三工具的 path 参数（拦截在执行前，被拦调用不落盘） |
| 会话生命周期 | session_start（重置一次性状态）、session_compact（置压缩标志） |
| 用户提示 notify | fail-open/压缩等非阻断提示 |
| 账本追加 | `bcp/ledger.jsonl` 追加一行 JSON，写失败静默跳过 |
| 项目根归一化 | 从会话 cwd 向上找 `.pi/APPEND_SYSTEM.md` 特征定根；找不到回退原目录（防子目录启动把账本写分裂） |

## 2. 闸门行为表

优先级序（同一次调用命中多个时，先到先拦）：**sleep > compact-restore > big-read > domain**；
skill-recall 只记账不拦截。全部零 LLM，触发信号 = 文件路径/大小/事件等机械事实。

| 闸门 | 触发 | 动作 | 一次性语义 | fail-open | 账本事件（mode=gate） |
|---|---|---|---|---|---|
| sleep | 任意 read/edit/write，且 当前 commit 数 − 最后一条 evolve REPORT 的 commits 基准 > 阈值（缺省 30） | 拦截 + 催巡检指引（对账→列清单→元裁决） | 每会话至多一次脉冲；首个工具调用即消耗脉冲资格（无论超阈否） | 非 git / 账本不可读 = 0 → 永不触发 | kind=sleep target=pulse verdict=INJECTED |
| compact-restore | 会话压缩后首次 read/edit/write | 拦截 + 「重读计划文件对齐 Σt」指引 | 每次压缩后一次 | — | kind=compact-restore verdict=INJECTED |
| skill-recall | read 命中 `deliverables/<name>/SKILL.md` | 只记账（匹配召回，§5.5 第三层） | 每次都记 | — | kind=skill-recall target=\<name\> verdict=READ |
| big-read | read 且目标 > 阈值（缺省 20KB） | 拦截 + 「先定位再定点读」指引 | 每文件每会话一次 | stat 失败放行（让 read 自行报错） | kind=big-read verdict=INJECTED |
| domain | read/edit/write 命中 ROUTES 前缀且该域本会话未注入 | 拦截 + 注入 `.pi/rules/<域>.md` 全文 | 每域每会话一次 | 规则文件缺失：放行 + notify + FAIL_OPEN，域仍标记已处理 | kind=domain verdict=INJECTED（附 domain/file）或 FAIL_OPEN |

## 3. 全局律

1. **拦截先于执行**：被拦调用不得执行，规则先入上下文，重试同一调用才执行——无「已执行才收到规则」窗口。
2. **fail-open 律**：任何异常（读规则/读账本/stat）放行，绝不死锁；fail-open 本身落账可见。
3. **bash 是已知缺口**：拦截只作用于 read/edit/write 的 path 参数（残余风险归 AGENTS.md 坏习惯条款）。
4. **证据流失败不阻断注入**：账本写失败静默跳过。
5. **路径基准**：ROUTES 匹配与账本写入以归一化项目根为基准；相对路径解析仍按会话 cwd（agent 语义不变）。
6. 阈值/ROUTES 为项目配置（模板缺省：20KB / 空 ROUTES / 30 commit）。

## 4. 一致性对碰

`python3 kit/host-contract.test.py` —— 零 LLM 场景向量集 + 参考实现（本文件语义的可执行形式）。

移植者流程：在目标宿主实现等价闸门 → 写薄适配器把宿主的（工具调用, 路径, 大小, 事件）
喂给同一向量集 → **全绿才算等价机械层**。向量覆盖：首触注入、每域/每文件一次性语义、
规则缺失 fail-open、优先级序（sleep>compact>big-read>domain）、bash 缺口、skill 记账
不拦截、edit 不触发 big-read、sleep 阈值边界（> 与 =）、压缩后单次恢复。

## 5. 溯源

- 行为抽取自 pi 适配层 `.pi/extensions/memory-gate.ts`（2026-09-11）。
- 抽取过程即捕获一例 P0：域注入读规则文件引用了游离变量，异常被 catch 吞成
  fail-open——闸门静默死亡，账本仅剩 FAIL_OPEN 尾迹。契约显式化前此类缺陷无传感器；
  §4 向量（v_domain_first_touch / v_rules_missing / v_failopen_silent）即防复发。
