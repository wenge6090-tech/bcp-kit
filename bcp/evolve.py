#!/usr/bin/env python3
"""BCP 演化算子报告器 v0 —— 零 LLM（README.md §4.4）。

只产数据，不当裁判：晋升/降级候选是统计信号，裁决权在人（§4.5 能垒）。
规则名注册表从 check.py 的 seam 表正则机械提取（单一来源，不建副本）。
用法：python3 bcp/evolve.py [--window N] [--min-hits M] [--ledger PATH]     # 退出码恒 0
每次运行追加 mode=evolve 审计记录到 bcp/ledger.jsonl（候选以 findings WARN 入账）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import tomllib
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "bcp" / "ledger.jsonl"
CHECK = ROOT / "bcp" / "check.py"
RULES_DIR = ROOT / ".pi" / "rules"
CFG = tomllib.loads((ROOT / "bcp" / "bcp.toml").read_text(encoding="utf-8"))
# §4.5 降级豁免（配置单一来源 bcp.toml [rule.demote]）：结构性规则违反即大改、命中天然低频，不参与命中数降级
DEMOTE_EXEMPT = tuple(CFG.get("rule", {}).get("demote", {}).get("exempt_prefixes", []))


def load_records(ledger: Path) -> list[dict]:
    if not ledger.exists():
        return []
    out: list[dict] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 损坏行跳过，不中断报告
    return out


def registered_rules() -> list[str]:
    """check.py seam 表的键 = 机械守护规则名（单一来源）。"""
    m = re.search(r"seam\s*=\s*\{(.*?)\}", CHECK.read_text(encoding="utf-8"), re.S)
    return re.findall(r'"(R\d-[^"]+)"', m.group(1)) if m else []


def parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="BCP 演化算子报告器（零 LLM，§4.4）")
    ap.add_argument("--window", type=int, default=30, help="降级考察窗口（天）")
    ap.add_argument("--min-hits", type=int, default=3, help="强化证据最小命中数")
    ap.add_argument("--ledger", type=Path, default=LEDGER, help="账本路径（默认 bcp/ledger.jsonl；测试可指空文件验冷启动）")
    args = ap.parse_args()

    now = datetime.now()
    cutoff = now - timedelta(days=args.window)
    recs = load_records(args.ledger)
    rules = registered_rules()

    rule_all: Counter[str] = Counter()
    rule_win: Counter[str] = Counter()
    last_seen: dict[str, str] = {}
    gate_by_domain: Counter[str] = Counter()
    gate_domains: set[str] = set()
    gate_files: dict[str, set[str]] = {}
    fail_open = 0
    verdicts: list[tuple[str, str, str, str, str, str]] = []
    skill_recall: Counter[str] = Counter()
    verify_pending: list[dict] = []      # 元反馈协议（§9.1）：待验证声明
    verify_judged: set[str] = set()     # 已裁决的 claim id（ref 对账）
    verify_judged_recs: list[dict] = []

    for r in recs:
        mode = r.get("mode", "")
        if mode == "gate":
            kind = str(r.get("kind", "domain"))
            if kind == "skill-recall":  # §2.4 技能召回事件（不参与 §4.6 冷启动判定——冷启动只看域注入）
                skill_recall[str(r.get("target") or r.get("domain") or "?")] += 1
                continue
            # 只统计域注入（kind=domain）：big-read/compact-restore 无 domain，计入会污染
            # §4.6 冷启动判定与域统计。字段兼容：旧记录仅 target（memory-gate 曾写 kind/target）。
            if kind != "domain":
                continue
            d = str(r.get("domain") or r.get("target") or "?")
            gate_by_domain[d] += 1
            gate_domains.add(d)
            gate_files.setdefault(d, set()).add(str(r.get("file") or r.get("target") or ""))
            if r.get("verdict") == "FAIL_OPEN":
                fail_open += 1
            continue
        if mode == "evolve":
            if r.get("verdict") in ("PROMOTED", "REJECTED"):  # §4.5 晋升裁决史（skill-impact 同构；evidence=能垒保真探针，⑧ 节审计）
                verdicts.append((str(r.get("ts", "")), str(r.get("verdict", "")), str(r.get("target", "")), str(r.get("source", "")), str(r.get("note", "")), str(r.get("evidence", ""))))
            continue
        if mode == "verify":  # 元反馈协议（§9.1）：pending=claim，judged=元滞后裁决（双轨：阴 PASS=入场券，元验证=终审）
            if r.get("state") == "pending":
                verify_pending.append(r)
            elif r.get("state") == "judged":
                verify_judged.add(str(r.get("ref", "")))
                verify_judged_recs.append(r)
            continue
        ts = parse_ts(str(r.get("ts", "")))
        for f in r.get("findings", []):
            rule = str(f.get("rule", "?"))
            rule_all[rule] += 1
            if ts and ts >= cutoff:
                rule_win[rule] += 1
            if rule not in last_seen or str(r.get("ts", "")) > last_seen[rule]:
                last_seen[rule] = str(r.get("ts", ""))

    # ⑥ 裁决史交叉（防重复呈报/提案，元负荷审计）：候选已有裁决记录 → 行内标注
    adjudicated: dict[str, tuple[str, str]] = {}
    for ts_, v_, tgt_, *_ in verdicts:
        if tgt_ not in adjudicated or ts_ > adjudicated[tgt_][1]:
            adjudicated[tgt_] = (v_, ts_)

    def adj_tag(rule: str) -> str:
        if rule not in adjudicated:
            return ""
        v, t = adjudicated[rule]
        hint = "勿重复提案" if v == "REJECTED" else "确认是否已落地"
        return f"  [已裁决:{v}@{t}——{hint}]"

    n_commit_head = 0
    try:
        n_commit_head = int(subprocess.run(["git", "rev-list", "--count", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip() or 0)
    except Exception:
        pass
    n_plan_head = sum(1 for r in recs if r.get("mode") in ("plan", "plan+collision"))
    lines: list[str] = [
        f"BCP 演化算子报告  window={args.window}d  min_hits={args.min_hits}  账本记录={len(recs)}  commits={n_commit_head}  plan记录={n_plan_head}"
    ]
    cold = sum(gate_by_domain.values()) == 0  # §4.6 冷启动：无任何域注入事件，死重判定无效
    if cold:
        lines.append("  [冷启动] 尚无域注入事件——死重判定无效，④ 列为待积累（§4.6）")

    lines.append("\n① check 规则命中（注册表来源：check.py seam 表）")
    for rule in rules:
        lines.append(
            f"  {rule:42s} 全历史={rule_all.get(rule, 0):3d}  窗口内={rule_win.get(rule, 0):3d}  末次={last_seen.get(rule, '—')}"
        )
    unregistered = sorted(set(rule_all) - set(rules))
    if unregistered:
        lines.append(f"  [注意] 账本中出现注册表外规则名: {unregistered}")

    lines.append(f"\n② memory-gate 域注入计数（域注入事件 {sum(gate_by_domain.values())}，FAIL_OPEN {fail_open}）")
    for d in sorted(gate_domains) or ["（尚无域注入事件——配 ROUTES 后重启会话开始积累）"]:
        lines.append(
            f"  {d:15s} 注入={gate_by_domain.get(d, 0):3d}  触碰文件数={len(gate_files.get(d, set()))}"
        )

    lines.append("\n③ 降级候选（窗口内零命中；豁免前缀 " + (" ".join(DEMOTE_EXEMPT) or "无") + "，§4.5 人裁决）")
    demote = [
        r for r in rules
        if rule_win.get(r, 0) == 0 and not r.startswith(DEMOTE_EXEMPT)
    ]
    for rule in demote:
        lines.append(f"  {rule:42s} 全历史={rule_all.get(rule, 0)}  末次={last_seen.get(rule, '—')}{adj_tag(rule)}")
    if not demote:
        lines.append("  （无）")

    known = sorted(p.stem for p in RULES_DIR.glob("*.md")) if RULES_DIR.exists() else []
    if cold:
        lines.append("\n④ 规则文件注入状态（冷启动——待积累，§4.6）")
        for d in known:
            lines.append(f"  .pi/rules/{d}.md  待积累")
        if not known:
            lines.append("  （无规则文件）")
        dead: list[str] = []  # 冷启动不产死重候选（§4.6），审计零 WARN
    else:
        lines.append("\n④ 死重候选（从未被注入的规则文件）")
        dead = [d for d in known if d not in gate_domains]
        for d in dead:
            lines.append(f"  .pi/rules/{d}.md")
        if not dead:
            lines.append("  （无）")

    lines.append(f"\n⑤ 强化证据（窗口内命中 ≥ {args.min_hits}）")
    strong = [(r, c) for r, c in rule_win.most_common() if c >= args.min_hits]
    for rule, c in strong:
        lines.append(f"  {rule:42s} 窗口内={c}{adj_tag(rule)}")
    if not strong:
        lines.append("  （无）")

    lines.append("\n⑥ 晋升裁决史（PROMOTED/REJECTED，防重复提案；§4.5）")
    for ts, v, tgt, src, note, ev in verdicts:
        entry = f"  {ts}  {v:9s} {tgt}"
        if src:
            entry += f"  源自失败模式「{src}」"
        if note:
            entry += f"  [{note}]"
        if not ev:
            entry += "  [无证据指针]"
        lines.append(entry.rstrip())
    if not verdicts:
        lines.append("  （无——晋升候选经人批准/拒绝后按协议追加裁决记录，见 §9.1）")

    lines.append("\n⑦ 技能资产（deliverables/*/SKILL.md，召回=skill-recall 事件，§2.4）")
    skills = sorted(p.parent.name for p in (ROOT / "deliverables").glob("*/SKILL.md")) if (ROOT / "deliverables").is_dir() else []
    # 注册对碰（声明↔实现，R6 同构）：技能的注册凭证 = ledger PROMOTED 记录（结晶经能垒，§4.5）。
    # 协议：技能裁决记录 target=技能名且 kind="skill"（与规则晋升的 PROMOTED 区分）。
    skill_promoted = {str(r.get("target")) for r in recs if r.get("mode") == "evolve" and r.get("verdict") == "PROMOTED" and str(r.get("kind")) == "skill"}
    for s in skills:
        reg = "已注册" if s in skill_promoted else "未注册（无 PROMOTED 记录——绕能垒结晶，补裁决或删除）"
        lines.append(f"  deliverables/{s}/SKILL.md  召回={skill_recall.get(s, 0)}  {reg}")
    ghost = skill_promoted - set(skills)
    if ghost:
        lines.append(f"  [幽灵注册] kind=skill 的 PROMOTED 无对应技能目录: {sorted(ghost)}——补资产或修正记录")
    if not skills:
        lines.append("  （无技能资产——可选轨道，模板常态）")

    # ⑧ 假设检验（范式→机械层过渡假设的机械传感器）：失败典藏 repro 回放 + 裁决证据指针审计。
    # 缺 repro / 缺 evidence 只计债呈报不入 findings：存量记录 append-only 不可回填，永久 WARN 是噪音；
    # 回放仍失败是可处置信号（规避未生效或回归），入 findings 呈元。
    lines.append("\n⑧ 假设检验（失败典藏回放 + 裁决证据指针 + 元验证债）")
    failures = [r for r in recs if r.get("mode") == "failure"]
    no_repro = [r for r in failures if not str(r.get("repro", "")).strip()]
    replay_fail: list[str] = []
    replayed = 0
    for r in failures:
        repro = str(r.get("repro", "")).strip()
        if not repro:
            continue
        replayed += 1
        try:
            p = subprocess.run(["bash", "-c", repro], capture_output=True, text=True, timeout=30, cwd=str(ROOT))
        except Exception:
            replay_fail.append(repro)
            continue
        if p.returncode != 0:
            replay_fail.append(repro)
    lines.append(
        f"  失败典藏 {len(failures)} 条：带 repro {len(failures) - len(no_repro)}，回放 {replayed}，仍失败 {len(replay_fail)}"
        "（仍失败 = 规避未生效或回归，呈元裁决）"
    )
    if no_repro:
        lines.append(f"  [债] {len(no_repro)} 条缺 repro 不可回放（新典藏起强制带 repro；存量 append-only 不可回填）")
    if verdicts:
        no_ev = sum(1 for v in verdicts if not v[5])
        lines.append(f"  裁决记录 {len(verdicts)} 条：缺证据指针 {no_ev}（evidence = 批准所据 diff 概览/决策 ID，防橡皮图章）")
    for c in replay_fail:
        lines.append(f"  [回归嫌疑] repro 仍失败: {c[:100]}")
    # 元验证债：pending=待办标记非阻塞标记，可永久存在，不自动 verified；只呈报不入 findings（待办非违规）。
    # 活动量分桶：n_commit_head − claim.commits（落账快照基准，同 REPORT commits 模式）<10 新鲜 / 10–30 应验证 / >30 可判长期。
    open_pending = [r for r in verify_pending if str(r.get("id", "")) not in verify_judged]
    buckets = {"新鲜": 0, "应验证": 0, "可判长期": 0}
    aged: list[tuple[int, str]] = []
    for r in open_pending:
        base = r.get("commits")
        if isinstance(base, int):
            d = n_commit_head - base
            buckets["新鲜" if d < 10 else "应验证" if d <= 30 else "可判长期"] += 1
            aged.append((d, str(r.get("id", "?"))))
        else:
            buckets["应验证"] += 1  # 无基准（旧记录/非 git）按应验证呈报
    lines.append(
        f"  元验证债：pending {len(open_pending)} 条（新鲜 {buckets['新鲜']} / 应验证 {buckets['应验证']} / 可判长期 {buckets['可判长期']}，活动量分桶 commits 距离）"
    )
    for d, cid in sorted(aged, reverse=True)[:3]:
        lines.append(f"    最老 pending: {cid}（距 {d} commits）——元可跳过，跳过即保持 pending（待办标记非阻塞标记）")
    if verify_judged_recs:
        # 幽灵裁决（⑦ 幽灵注册同构）：ref 无对应 claim = 打错了账；同 ref 多条 judged = 取 ts 最新（append-only 不改历史，统计去重）
        pending_ids = {str(r.get("id", "")) for r in verify_pending}
        phantom_judged = sorted({str(r.get("ref", "")) for r in verify_judged_recs} - pending_ids)
        latest: dict[str, dict] = {}
        for r in sorted(verify_judged_recs, key=lambda x: str(x.get("ts", ""))):
            latest[str(r.get("ref", ""))] = r
        stats_recs = list(latest.values())
        cnt = {"verified": 0, "drift": 0, "defect": 0}
        no_ev2 = 0
        malformed = 0
        for r in stats_recs:
            vd = r.get("verdicts")
            if not isinstance(vd, dict):  # 畸形记录免疫：报告器永不因坏 schema 死（load_records 已免 JSON 坏行，此处免 schema 坏行）
                malformed += 1
                continue
            vs = {str(v) for v in vd.values()}
            if "defect" in vs:
                cnt["defect"] += 1
            elif "drift" in vs:
                cnt["drift"] += 1
            else:
                cnt["verified"] += 1
            if not str(r.get("evidence", "")).strip():
                no_ev2 += 1
        total = len(stats_recs) - malformed
        rate = f"，DEFECT 率 {cnt['defect'] * 100 // total}%" if total else ""
        lines.append(
            f"  元裁决 {total} 条：verified {cnt['verified']} / drift {cnt['drift']} / defect {cnt['defect']}{rate}（evidence 必填，缺 {no_ev2} 条）"
        )
        # 预填确认率（元技能双螺旋，README §2.4）：prefill={skill,agree} 缺省不计（向后兼容）；
        # 阈值 60% 先常量（§4.2 攒证据后配置化）。低于阈值 = 降级候选（findings WARN 呈元）。
        pre_total = pre_agree = 0
        by_skill: dict[str, list[int]] = {}
        for r in stats_recs:
            pf = r.get("prefill")
            if isinstance(pf, dict) and pf:
                agree = 1 if pf.get("agree") else 0
                pre_total += 1
                pre_agree += agree
                sk = str(pf.get("skill", "")).strip()
                if sk:
                    by_skill.setdefault(sk, []).append(agree)
        if pre_total:
            lines.append(f"  预填确认率：{pre_agree}/{pre_total}（{pre_agree * 100 // pre_total}%）")
            for sk, ags in sorted(by_skill.items()):
                srate = sum(ags) * 100 // len(ags)
                flag = "  [低于阈值 60%——降级候选，呈元]" if srate < 60 else ""
                lines.append(f"    元技能 {sk}: {sum(ags)}/{len(ags)}（{srate}%）{flag}")
        if malformed:
            lines.append(f"  [畸形] verdicts 非 dict 跳过 {malformed} 条——修记录或补 claim")
        if phantom_judged:
            lines.append(f"  [幽灵裁决] ref 无对应 claim: {phantom_judged}——修正 ref 或补 claim")

    print("\n".join(lines))

    # 审计痕迹（§4.3：候选以 findings WARN 入账）
    findings = [
        {"rule": "evolve-report", "sev": "WARN", "msg": msg}
        for msg in (
            [f"降级候选: {r}{adj_tag(r)}" for r in demote]
            + [f"死重文件: .pi/rules/{d}.md" for d in dead]
            + [f"强化证据: {r} 窗口内{c}{adj_tag(r)}" for r, c in strong]
            + [f"回归嫌疑(repro 仍失败): {c[:80]}" for c in replay_fail]
            + [f"元技能确认率低于阈值: {sk} {sum(ags)}/{len(ags)}——降级候选呈元" for sk, ags in by_skill.items() if sum(ags) * 100 // len(ags) < 60]
        )
    ]
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": "evolve",
        "verdict": "REPORT",
        # sleep 触发对账基准（README §4.7）：gate 比较「当前 commit 数 − 此值 > 阈值」→ 催巡检
        "commits": (lambda p: int(p.stdout.strip() or 0) if p.returncode == 0 else None)(
            subprocess.run(["git", "rev-list", "--count", "HEAD"], capture_output=True, text=True, cwd=ROOT)
        ),
        "fail": 0,
        "warn": len(findings),
        "findings": findings,
        "window": args.window,
        "min_hits": args.min_hits,
        "cold_start": cold,
    }
    args.ledger.parent.mkdir(exist_ok=True)
    with args.ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
