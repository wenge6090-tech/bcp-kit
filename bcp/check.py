#!/usr/bin/env python3
"""BCP 机械检查器 v0 —— 零 LLM（范式背景见 README.md）。

用法：
  ./bcp/check.py                    # 静态规则集（R1-R5）
  ./bcp/check.py --plan FILE        # + 计划引用解析与 accept 判据（R6）
  ./bcp/check.py --plan FILE --collision   # + git diff 双向对碰（实现完成后）
  ./bcp/check.py --no-exec          # R6 只解析不执行 accept

失败路由（每条 finding 标注修复方向）：
  R1-R4          → 改代码
  R5             → 改文档
  R6 引用/对碰类  → 改计划
  R6 accept 失败  → 改代码
  R7             → 改计划
每次运行追加证据账本 bcp/ledger.jsonl。
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    print("需要 Python 3.11+（tomllib）", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
CFG = tomllib.loads((ROOT / "bcp" / "bcp.toml").read_text(encoding="utf-8"))
LEDGER = ROOT / "bcp" / "ledger.jsonl"

findings: list[tuple[str, str, str]] = []  # (rule, severity, message)


def fail(rule: str, msg: str) -> None:
    findings.append((rule, "FAIL", msg))


def warn(rule: str, msg: str) -> None:
    findings.append((rule, "WARN", msg))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def ident_boundary(name: str) -> str:
    # ASCII 词边界（CJK 算非分隔符两侧之外的任意字符——「用read工具」也要命中）
    return rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])"


def _strip_rs_comments(text: str) -> str:
    # 消费检测只认代码：注释里提及死字段（如教学性解释「恒空」）不算引用
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _unquote(s: str) -> str:
    """仅当首尾成对引号时剥掉——保护 `bash -c '...'` 这类尾引号命令。"""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


# ---------------------------------------------------------------- R1 六触点（示例源自 taiji 分流案例，README.md §5.4）
def r1_builtin_touchpoints() -> None:
    rule = "R1-builtin-touchpoints"
    cfg = CFG.get("rule", {}).get("builtin_touchpoints")
    if not cfg:
        return  # 未配置 = 未启用（R1–R4 为项目专属结构性规则，模板项目按需配置）
    for name in cfg["builtins"]:
        exec_file = ROOT / cfg["exec_dir"] / f"{name}.rs"
        if not exec_file.exists():
            fail(rule, f"①执行体缺失: {cfg['exec_dir']}/{name}.rs")
        for reg in cfg["registries"]:
            text = read(ROOT / reg)
            if not re.search(ident_boundary(name), text):
                fail(rule, f"触点未注册 {name!r} → {reg}")


# ---------------------------------------------------------------- R2 类别子集同步（示例源自 taiji 分流案例）
def _fn_string_literals(text: str, fn_name: str) -> set[str]:
    m = re.search(rf"fn {re.escape(fn_name)}\b.*?^}}", text, re.S | re.M)
    if not m:
        return set()
    return set(re.findall(r'"([A-Za-z0-9_-]+)"', m.group(0)))


def r2_category_subset() -> None:
    rule = "R2-category-subset"
    cfg = CFG.get("rule", {}).get("category_subset")
    if not cfg:
        return  # 未配置 = 未启用
    text = read(ROOT / cfg["file"])
    kind_ids = _fn_string_literals(text, cfg["kind_fn"])
    cat_ids = _fn_string_literals(text, cfg["category_fn"])
    if not kind_ids:
        fail(rule, f"未提取到 {cfg['kind_fn']}() 判据集（函数改名？同步 bcp.toml）")
        return
    if not cat_ids:
        fail(rule, f"未提取到 {cfg['category_fn']}() 类别集（函数改名？同步 bcp.toml）")
        return
    for i in sorted(kind_ids - cat_ids):
        fail(rule, f"判据 {i!r} 在 {cfg['kind_fn']} 而不在 {cfg['category_fn']}")


# ---------------------------------------------------------------- R3 死字段禁止（示例源自 taiji 分流案例）
def r3_dead_fields() -> None:
    rule = "R3-dead-fields"
    cfg = CFG.get("rule", {}).get("dead_fields")
    if not cfg:
        return  # 未配置 = 未启用
    allow = set(cfg["allow_files"])
    for f in sorted((ROOT / "src").rglob("*.rs")):
        rel = f.relative_to(ROOT).as_posix()
        if rel in allow:
            continue
        text = _strip_rs_comments(read(f))
        for field in cfg["fields"]:
            if re.search(ident_boundary(field), text):
                fail(rule, f"死字段 {field} 在白名单外被引用: {rel}")


# ---------------------------------------------------------------- R4 措辞禁令（示例源自 taiji 分流案例）
def r4_wording() -> None:
    rule = "R4-wording-scope"
    cfg = CFG.get("rule", {}).get("wording")
    if not cfg:
        return  # 未配置 = 未启用
    for scope in cfg["scope"]:
        p = ROOT / scope
        files = [p] if p.is_file() else sorted(p.rglob("*.rs"))
        for f in files:
            text = read(f)
            for phrase in cfg["banned"]:
                if phrase in text:
                    fail(rule, f"禁用措辞 {phrase!r} 于 {f.relative_to(ROOT).as_posix()}")


# ---------------------------------------------------------------- R5 引用完整性
def _resolve(tok: str, root_map: dict[str, str]) -> Path | None:
    for prefix in sorted(root_map, key=len, reverse=True):
        if tok.startswith(prefix):
            return ROOT / root_map[prefix] / tok[len(prefix):]
    return ROOT / tok


_HEAD_CACHE: dict[str, set] = {}


def _headings(doc: str) -> set:
    """提取文档章节号（兼容 `## 5.2 标题` 与 `## 11. 标题` 两种风格）。"""
    if doc not in _HEAD_CACHE:
        p = ROOT / doc
        _HEAD_CACHE[doc] = (
            set(re.findall(r"^#{2,4}\s+(\d+(?:\.\d+)*)\.?\s", read(p), re.M))
            if p.exists()
            else set()
        )
    return _HEAD_CACHE[doc]


def r5_doc_ghost_paths() -> None:
    rule = "R5-doc-ghost-paths(引用完整性)"
    cfg = CFG["rule"]["doc_ghost_paths"]
    root_map = cfg.get("root_map", {})
    ignores = cfg.get("ignore_prefixes", [])
    src_files = None  # 惰性：仅遇到裸 .rs 名时全量列举一次
    targets: list[str] = []
    for doc in cfg["docs"]:
        if any(ch in doc for ch in "*?["):
            # glob 零匹配 = 储层尚未沉淀（模板常态，§4.6 待积累语义），静默跳过不算告警
            matched = sorted(glob.glob(str(ROOT / doc)))
            targets.extend(Path(m).resolve().relative_to(ROOT).as_posix() for m in matched)
        else:
            targets.append(doc)
    for doc in targets:
        path = ROOT / doc
        if not path.exists():
            warn(rule, f"待检文档不存在（跳过）: {doc}")
            continue
        for lineno, line in enumerate(read(path).splitlines(), 1):
            deletion_context = any(m in line for m in ("已删", "删除", "移除", "deleted"))
            for tok in set(re.findall(r"`([^`\n]+)`", line)):
                tok = tok.strip()
                if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z]{1,5}", tok):
                    continue
                if any(tok.startswith(p) for p in ignores):
                    continue
                if "/" in tok:
                    cand = _resolve(tok, root_map)
                    if cand is not None and not cand.exists():
                        fail(rule, f"{doc}:{lineno} 断言路径不存在: {tok}")
                elif tok.endswith(".rs"):
                    if deletion_context:
                        continue  # 「已删」行内提及的历史文件名不作存在性断言
                    if src_files is None:
                        src_files = {f.name: f for f in (ROOT / "src").rglob("*.rs")}
                    if tok not in src_files:
                        fail(rule, f"{doc}:{lineno} 断言源文件不存在: {tok}")


# ---------------------------------------------------------------- R7 §2.3 探索纯净
def r7_explore_purity(plan: dict) -> None:
    rule = "R7-explore-purity(§2.3)"
    cfg = CFG.get("rule", {}).get("explore_purity")
    if not cfg:
        return
    mode = str(plan.get("mode", "infer")).strip()
    if mode not in ("explore", "infer"):
        fail(rule, f"mode 非法 {mode!r}（只允许 explore | infer，缺省 infer → 改计划）")
    items = plan.get("items") or []
    raw_track = any(
        str(f).endswith(m)
        for m in cfg["raw_track_markers"]
        for it in items
        for f in it.get("files", [])
    ) or str(plan.get("skill_evolution", "")).strip().lower() == "true"
    if raw_track and mode != "explore":
        fail(rule, "产出原始轨迹（SKILL.md）/ skill_evolution 任务必须 mode: explore（元裸跑，禁先验注入 → 改计划）")


# ---------------------------------------------------------------- R6 计划对碰
def _parse_plan_header(text: str) -> dict | None:
    m = re.search(r"^```yaml\s*\n(.*?)^```\s*$", text, re.S | re.M) or re.search(
        r"^---\s*\n(.*?)^---\s*$", text, re.S | re.M
    )
    if not m:
        return None
    plan: dict = {}
    item: dict | None = None
    block_list: list[str] | None = None  # 当前打开的多行列表（files/interfaces/accept）
    block_indent = -1  # 打开列表的键缩进；后续行缩进 ≤ 它 = 列表结束
    for raw in m.group(1).splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0:
            item = None
            block_list = None
            k, _, v = line.partition(":")
            if k.strip() == "items" and not v.strip():
                plan["items"] = []
            else:
                plan[k.strip()] = v.split(" #")[0].strip().strip('"')
            continue
        if plan.get("items") is None:
            continue
        if block_list is not None and indent <= block_indent:
            block_list = None
        if line.startswith("- "):
            if block_list is not None:  # 列表条目，不是新 item
                entry = _unquote(line[2:])
                if entry:
                    block_list.append(entry)
                continue
            item = {}
            plan["items"].append(item)
            line = line[2:].strip()
        if item is None:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.split(" #")[0].strip()
        if v == "":
            item[k] = []
            block_list = item[k]
            block_indent = indent
        elif v.startswith("["):
            item[k] = [_unquote(x) for x in v.strip("[]").split(",") if x.strip()]
            block_list = None
        else:
            item[k] = _unquote(v)
            block_list = None
    return plan or None


# accept 执行统一用 bash -c（≠ /bin/sh/dash：||、for、[[ ]] 等 bash 语义不走样）
# shell 语法错误特征（引号不配对/EOF）→ 命令自身坏了，路由「改计划」而非「改代码」（假阳性治理）
_SYNTAX_ERR = re.compile(r"(unexpected EOF|未预期的 EOF|syntax error|语法错误)", re.I)


def r8_skill_contract() -> None:
    """R8-skill-contract（README §2.4）：技能结构闸——结晶的机械面。

    技能 = 液→固相变产物（§4.2 结晶算子）：固化资产必须自带适用条件、验证凭证、溯源，
    否则不可召回（散文不可结晶）。无 deliverables/ 静默跳过（可选轨道，模板常态，同 R5 glob 语义）。
    """
    rule = "R8-skill-contract(§2.4)"
    skills_dir = ROOT / "deliverables"
    if not skills_dir.is_dir():
        return
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        rel = skill_md.relative_to(ROOT)
        text = skill_md.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
        if not m:
            fail(rule, f"{rel}: 缺 frontmatter（→ 改文档：name/description/validation 三件套）")
            continue
        fm = m.group(1)
        for field in ("name", "description", "validation"):
            if not re.search(rf"^{field}:\s*\S", fm, re.M):
                fail(rule, f"{rel}: frontmatter 缺 {field}（→ 改文档）")
        body = text[m.end():]
        if not re.search(r"^#{1,3}\s*(适用|When to [Aa]pply)", body, re.M):
            fail(rule, f"{rel}: 缺「适用条件」节（→ 改文档：何时用/不用）")
        if not re.search(r"^#{1,3}\s*(溯源|Source)", body, re.M):
            fail(rule, f"{rel}: 缺「溯源」节（→ 改文档：源自哪条失败模式/规则/任务，对应 §4.5 PROMOTED 记录）")


def r6_plan(plan_path: Path, *, run_accept: bool, collision: bool) -> None:
    rule = "R6-plan-collision"
    plan = _parse_plan_header(read(plan_path))
    if plan is None:
        fail(rule, "未找到计划 YAML 头（```yaml 围栏或 --- 块）——P 必须结构化（plan.md 协议）")
        return
    r7_explore_purity(plan)
    items = plan.get("items") or []
    if not items:
        fail(rule, "items 为空——计划无转化条目")
    for it in items:
        pid = it.get("id", "?")
        raw = str(it.get("blueprint", "")).strip()
        if not raw:
            warn(rule, f"{pid}: 未声明 blueprint 锚（建议引用章节号）")
            continue
        # 锚格式：`§x.y`（默认 Blueprint.md）或 `文件§x.y`（如 README.md§2.3）
        doc, _, sec = raw.partition("§")
        doc = doc.strip() or "Blueprint.md"
        sec = sec.strip()
        if not (ROOT / doc).exists():
            fail(rule, f"{pid}: blueprint 引用文档不存在 {doc}（→ 回写蓝图或改计划）")
        elif sec not in _headings(doc):
            fail(rule, f"{pid}: blueprint 引用悬空 {raw}（{doc} 无此章节 → 回写蓝图或改计划）")
        for f in it.get("files", []):
            if not (ROOT / f).exists():
                fail(rule, f"{pid}: 声明文件不存在 {f}（→ 改计划）")
        for iface in it.get("interfaces", []):
            code_files = list((ROOT / "src").rglob("*.rs")) + list((ROOT / "bcp").rglob("*.py"))
            if not any(iface in read(f) for f in code_files):
                fail(rule, f"{pid}: 接口签名未命中 {iface!r}（→ 改计划）")
        for cmd in it.get("accept", []):
            if not run_accept:
                continue
            try:
                r = subprocess.run(["bash", "-c", cmd], cwd=ROOT, capture_output=True, text=True, timeout=600)
            except subprocess.TimeoutExpired:
                fail(rule, f"{pid}: accept 超时(600s)（→ 改代码）: {cmd}")
                continue
            if r.returncode != 0:
                tail = (r.stderr or r.stdout).strip().splitlines()[-1:]
                detail = f" —— {tail[0][:120]}" if tail else ""
                if _SYNTAX_ERR.search(r.stderr or ""):
                    fail(rule, f"{pid}: accept 命令 shell 语法错误，未真正执行（→ 改计划：简化引号嵌套或改为脚本文件）: {cmd}{detail}")
                else:
                    fail(rule, f"{pid}: accept 失败（→ 改代码）: {cmd}{detail}")
    if collision:
        excludes = tuple(CFG.get("rule", {}).get("plan_collision", {}).get("excludes", []))
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],  # -uall：新目录折叠为目录级会漏对碰新文件
            cwd=ROOT, capture_output=True, text=True,
        ).stdout.splitlines()
        raw_changed = {ln[3:].strip().strip('"') for ln in out if len(ln) > 3}  # strip 引号：git 对含空格/特殊字符路径加 C 风格引号，不剥则声明对不上
        # 豁免语义：excludes 路径不强制声明；但声明了就必须真改动。
        changed = {c for c in raw_changed if not c.startswith(excludes)}
        declared = {f for it in items for f in it.get("files", [])}
        for f in sorted(declared - raw_changed):
            fail(rule, f"声明未改动 {f}（声明了没改 → 改实现或修正 files）")
        for f in sorted(changed - declared):
            fail(rule, f"改动未声明 {f}（改了没声明 → 更新 files 或回退改动）")


# ---------------------------------------------------------------- selfcheck
def selfcheck() -> int:
    """范式健康自检：报告各闸门依赖就绪状态（空转 = 依赖缺失，闸门形同虚设）。

    空转的 check 比没有 check 更危险（虚假安全感）。报告非裁决：退出码恒 0，不入账本
    （避免安装期频繁自检污染证据流；与 evolve.py 同为报告器但免刷屏）。
    """
    lines: list[str] = ["范式健康自检（--selfcheck，报告非裁决，不入账本）", ""]

    def item(ok: bool, tag: str, okmsg: str, badmsg: str) -> None:
        lines.append(f"  [{'OK  ' if ok else 'IDLE'}] {tag} — {okmsg if ok else badmsg}")

    def note(tag: str, msg: str) -> None:
        lines.append(f"  [NOTE] {tag} — {msg}")

    # ── 宿主适配层（pi 专属；换宿主 = 重写等价机械注入层，README 两层结构表）
    lines.append("[宿主适配层 .pi/（pi 专属，换宿主需重写等价机械注入层）]")
    item((ROOT / ".pi" / "APPEND_SYSTEM.md").exists(), "工作流内核", "在", "缺失——四步工作流不可用")
    gate = ROOT / ".pi" / "extensions" / "memory-gate.ts"
    item(gate.exists(), "memory-gate 三闸门", "在", "缺失——域注入/大文件附注/compaction 恢复不可用")
    if gate.exists():
        # 剥离 // 注释行后机械提取 ROUTES（注释里的示例不得混入）
        src = "\n".join(ln for ln in read(gate).splitlines() if not ln.lstrip().startswith("//"))
        routes = re.findall(r'\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]', src)
        if not routes:
            lines.append("  [IDLE] memory-gate ROUTES — 为空：域规则注入空转（配前缀→域映射 + .pi/rules/<域>.md）")
        for prefix, domain in routes:
            rf = ROOT / ".pi" / "rules" / f"{domain}.md"
            item(rf.exists(), f"域规则 {domain}（{prefix}）", ".pi/rules/%s.md 在" % domain, "缺失——gate fail-open 放行 = 注入空转")
    hook = ROOT / ".git" / "hooks" / "pre-commit"
    if hook.exists():
        item("check.py" in read(hook), "pre-commit 提交闸门", "已装", "存在但不调 check.py——用 kit/pre-commit")
    elif (ROOT / ".git").exists():
        item(False, "pre-commit 提交闸门", "", "未装——cp kit/pre-commit .git/hooks/ && chmod +x")
    else:
        note("pre-commit 提交闸门", "非 git 项目，无提交闸门（static check 照常可用）")

    # ── R5 引用完整性
    lines.append("[R5 引用完整性]")
    cfg5 = CFG["rule"]["doc_ghost_paths"]
    missing = [d for d in cfg5["docs"] if not any(ch in d for ch in "*?[") and not (ROOT / d).exists()]
    item(not missing, "检视文档", f"{len(cfg5['docs'])} 项配置就绪", f"缺失 {missing}——对应文档路径断言不设防")
    rules_dir = ROOT / ".pi" / "rules"
    n_rules = len(list(rules_dir.glob("*.md"))) if rules_dir.exists() else 0
    item(n_rules > 0, "规则储层 .pi/rules/", f"{n_rules} 个规则文件", "空——R5 对储层部分空转（沉淀避坑后生效）")

    # ── R6 计划对碰
    lines.append("[R6 计划对碰]")
    item((ROOT / "bcp" / "plans").exists(), "计划目录 bcp/plans/", "在", "缺失——/plan 产出无落点（首次 /plan 自动建亦可）")

    # 技能召回挂载（可选轨道，README §2.4）：pi settings 路径相对 .pi 解析——必须验证解析后指向真实储层，
    # 只 grep 字符串会漏掉「路径写错但词对了」的乌龙（实测发生：deliverables 写成相对 cwd，实际解析到 .pi/deliverables）
    skill_assets = sorted((ROOT / "deliverables").glob("*/SKILL.md")) if (ROOT / "deliverables").is_dir() else []
    if skill_assets:
        settings = ROOT / ".pi" / "settings.json"
        mounted = False
        if settings.exists():
            try:
                for s in json.loads(settings.read_text(encoding="utf-8")).get("skills") or []:
                    if (ROOT / ".pi" / s).resolve() == (ROOT / "deliverables").resolve():
                        mounted = True
                        break
            except (json.JSONDecodeError, OSError):
                pass
        item(mounted, "技能召回挂载", f"{len(skill_assets)} 个技能资产已挂载 pi 召回（解析验证通过）", "deliverables/ 有 SKILL.md 但 .pi/settings.json 未正确挂载（注意：路径相对 .pi 解析，应写 ../deliverables）——技能永不被召回（§5.5 匹配召回空转）")
    else:
        note("技能储层 deliverables/", "无技能资产（可选轨道，模板常态；首个 SKILL.md 结晶后 R8 自动接管）")
    if not (ROOT / "Blueprint.md").exists():
        note("Blueprint.md", "无——计划 blueprint 锚用 `文件§x.y` 格式（如 README.md§4）或先建蓝图（可选件，§2 B→P 接缝）")
    n_plan = 0
    if LEDGER.exists():
        for ln in LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                if str(json.loads(ln).get("mode", "")).startswith("plan"):
                    n_plan += 1
            except json.JSONDecodeError:
                pass
    item(n_plan > 0, "R6 实战记录", f"账本含 {n_plan} 条 plan 模式记录", "0 条——R6 管道未经实战（跑一次 /check --plan 验证）")

    # ── R7 探索纯净
    lines.append("[R7 探索纯净]")
    item(bool(CFG.get("rule", {}).get("explore_purity")), "explore_purity 配置", "在", "bcp.toml 缺 [rule.explore_purity]——R7 空转")

    # sleep 巡检节律（README §4.7）：活动量计数可见——腐烂从静默变可测量
    n_commit = 0
    try:
        n_commit = int(subprocess.run(["git", "rev-list", "--count", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip() or 0)
    except Exception:
        pass
    n_last = 0
    if LEDGER.exists():
        for ln in LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("mode") == "evolve":
                n_last = int(r.get("commits") or 0)
    pulse = n_commit - n_last
    item(pulse <= 30, "sleep 巡检节律", f"活动量 {pulse}/30 commit", f"活动量 {pulse} > 30 未巡检——跑 python3 bcp/evolve.py 落 REPORT 账即重置（/sleep 清单流见 README §4.7）")

    # 工作流逃逸代理（README §4.7）：commit 数 vs plan 记录数——粗代理非裁决，元看数据对账（/sleep）
    item(not (n_commit > 30 and n_plan * 5 < n_commit), "工作流逃逸代理", f"commits={n_commit} plan记录={n_plan}", "高 commit 低 plan 记录——疑有任务绕过计划流，跑 /sleep 对账清单核查")

    # 账本健康（§4.3 生命周期）：体积可见——归档时机由数据说话（append-only 无界，归档协议暂缓）
    if LEDGER.exists():
        note("账本健康", f"{sum(1 for _ in LEDGER.open(encoding='utf-8'))} 条 / {LEDGER.stat().st_size / 1024:.0f}KB（append-only 无界；>5MB 再议冷归档 §4.3）")
    else:
        note("账本健康", "空（首条记录落账后创建）")

    # ── R1-R4 项目专属
    lines.append("[R1-R4 项目专属（未配置 = 设计内跳过，非空转）]")
    for key, name in (
        ("builtin_touchpoints", "R1 六触点"),
        ("category_subset", "R2 类别子集"),
        ("dead_fields", "R3 死字段"),
        ("wording", "R4 措辞"),
    ):
        lines.append(f"  [{'启用' if CFG.get('rule', {}).get(key) else '未配置'}] {name}")

    print("\n".join(lines))
    print("\n自检完成：IDLE 项 = 闸门空转风险，按提示补齐依赖；退出码恒 0（报告非裁决）")
    return 0


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="BCP 对碰器 v0（阴·机械对碰）")
    ap.add_argument("--plan", type=Path, help="计划文件路径（启用 R6）")
    ap.add_argument("--collision", action="store_true", help="启用 git diff 双向对碰（需 --plan）")
    ap.add_argument("--no-exec", action="store_true", help="R6 不执行 accept 命令")
    ap.add_argument("--selfcheck", action="store_true", help="范式健康自检（空转报告，不入账本，退出码恒 0）")
    args = ap.parse_args()

    if args.selfcheck:
        return selfcheck()

    r1_builtin_touchpoints()
    r2_category_subset()
    r3_dead_fields()
    r4_wording()
    r5_doc_ghost_paths()
    r8_skill_contract()
    if args.plan:
        r6_plan(args.plan, run_accept=not args.no_exec, collision=args.collision)

    seam = {
        "R1-builtin-touchpoints": "改代码",
        "R2-category-subset": "改代码",
        "R3-dead-fields": "改代码",
        "R4-wording-scope": "改代码",
        "R5-doc-ghost-paths(引用完整性)": "改文档",
        "R6-plan-collision": "见各条",
        "R7-explore-purity(§2.3)": "改计划",
        "R8-skill-contract(§2.4)": "改文档",
    }
    for r, s, m in findings:
        print(f"[{s}] {r} [{seam.get(r, '')}]\n    {m}")
    n_fail = sum(1 for _, s, _ in findings if s == "FAIL")
    n_warn = sum(1 for _, s, _ in findings if s == "WARN")
    verdict = "PASS" if n_fail == 0 else "FAIL"
    print(f"\n对碰裁决: {verdict}  (FAIL={n_fail} WARN={n_warn})")

    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": "plan+collision" if args.plan and args.collision else ("plan" if args.plan else "static"),
        "verdict": verdict,
        "fail": n_fail,
        "warn": n_warn,
        # 单条体积上界（§4.3 生命周期）：findings 截断 top50、msg≤200 字符；全文在 stdout，账本只需索引
        "findings": [
            {"rule": r, "sev": s, "msg": m[:200]}
            for r, s, m in findings[:50]
        ],
        "findings_truncated": max(0, len(findings) - 50),
    }
    LEDGER.parent.mkdir(exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
