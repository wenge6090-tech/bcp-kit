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

    for r in recs:
        mode = r.get("mode", "")
        if mode == "gate":
            # 只统计域注入（kind=domain）：big-read/compact-restore 无 domain，计入会污染
            # §4.6 冷启动判定与域统计。字段兼容：旧记录仅 target（memory-gate 曾写 kind/target）。
            if str(r.get("kind", "domain")) != "domain":
                continue
            d = str(r.get("domain") or r.get("target") or "?")
            gate_by_domain[d] += 1
            gate_domains.add(d)
            gate_files.setdefault(d, set()).add(str(r.get("file") or r.get("target") or ""))
            if r.get("verdict") == "FAIL_OPEN":
                fail_open += 1
            continue
        if mode == "evolve":
            continue
        ts = parse_ts(str(r.get("ts", "")))
        for f in r.get("findings", []):
            rule = str(f.get("rule", "?"))
            rule_all[rule] += 1
            if ts and ts >= cutoff:
                rule_win[rule] += 1
            if rule not in last_seen or str(r.get("ts", "")) > last_seen[rule]:
                last_seen[rule] = str(r.get("ts", ""))

    lines: list[str] = [
        f"BCP 演化算子报告  window={args.window}d  min_hits={args.min_hits}  账本记录={len(recs)}"
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
        lines.append(f"  {rule:42s} 全历史={rule_all.get(rule, 0)}  末次={last_seen.get(rule, '—')}")
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
        lines.append(f"  {rule:42s} 窗口内={c}")
    if not strong:
        lines.append("  （无）")

    print("\n".join(lines))

    # 审计痕迹（§4.3：候选以 findings WARN 入账）
    findings = [
        {"rule": "evolve-report", "sev": "WARN", "msg": msg}
        for msg in (
            [f"降级候选: {r}" for r in demote]
            + [f"死重文件: .pi/rules/{d}.md" for d in dead]
            + [f"强化证据: {r} 窗口内{c}" for r, c in strong]
        )
    ]
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": "evolve",
        "verdict": "REPORT",
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
