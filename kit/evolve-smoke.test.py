#!/usr/bin/env python3
"""BCP 报告器冒烟（零 LLM，沙盒账本）—— evolve.py 的机械测试面。

为什么需要：evolve.py 只在 sleep 对账时被调用，无自动入口、无测试面——任何异常分支
（空数据 / 畸形 schema / 幽灵引用）都可能长期潜伏。2026-09-11 实测：无 judged 记录时
`by_skill` 未初始化 → UnboundLocalError，退出码 1、REPORT 未落账、巡检无法醒来（潜伏
3 小时，因为该聚合代码加入后一次都没跑过）。

做法：`--ledger` 指向临时沙盒，断言四种账本形态下 evolve.py 均退出码 0、无 Traceback、
REPORT 落账；真账本永不触碰（规则域模式 3）。

用法：python3 kit/evolve-smoke.test.py      # 退出码 0 = 全绿
改 bcp/evolve.py 后必跑（规则域模式 8）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVOLVE = ROOT / "bcp" / "evolve.py"
REAL_LEDGER = ROOT / "bcp" / "ledger.jsonl"
PY = sys.executable or "python3"


def ts(offset: int = 0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + offset))


def run(records: list[dict]) -> tuple[int, str, str, list[dict]]:
    """在临时沙盒账本上跑一次 evolve.py，返回 (退出码, stdout, stderr, 沙盒落账记录)。"""
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "ledger.jsonl"
        if records:
            ledger.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        p = subprocess.run([PY, str(EVOLVE), "--ledger", str(ledger)], cwd=ROOT, capture_output=True, text=True)
        written = []
        if ledger.exists():
            for ln in ledger.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    try:
                        written.append(json.loads(ln))
                    except json.JSONDecodeError:
                        pass
        return p.returncode, p.stdout, p.stderr, written


# ── 账本形态 ──────────────────────────────────────────────────────────
def s_empty() -> list[dict]:
    """空账本（首跑 / 冷启动）——④ 节列待积累，不判死重。"""
    return []


def s_pending_only() -> list[dict]:
    """只有 pending、0 条 judged —— 本次崩溃的回归守卫（by_skill 空数据分支）。"""
    return [
        {"ts": ts(-100), "mode": "verify", "state": "pending", "id": "T-pending",
         "claim": "冒烟用", "commits": 20},
        {"ts": ts(-90), "mode": "verify", "state": "pending", "id": "T-pending2",
         "claim": "无 commits 基准的旧记录", },
    ]


def s_malformed() -> list[dict]:
    """畸形 schema + 幽灵裁决 + 同 ref 重复 judged —— 免疫族（跳过 + 呈报，永不崩）。"""
    return s_pending_only() + [
        {"ts": ts(-60), "mode": "verify", "state": "judged", "ref": "T-pending2",
         "verdicts": ["a", "b"], "evidence": "畸形：verdicts 非 dict（该 ref 唯一 judged，不被去重覆盖）"},
        {"ts": ts(-70), "mode": "verify", "state": "judged", "ref": "T-ghost",
         "verdicts": {"i1": "drift"}, "attribution": {"layer": "plan"}, "evidence": "幽灵 ref"},
        {"ts": ts(-80), "mode": "verify", "state": "judged", "ref": "T-pending",
         "verdicts": {"i1": "defect"}, "attribution": {"layer": "plan"}, "evidence": "旧（应被下条覆盖）"},
        {"ts": ts(-50), "mode": "verify", "state": "judged", "ref": "T-pending",
         "verdicts": {"i1": "verified"}, "evidence": "新——同 ref 统计取 ts 最新"},
        {"ts": ts(-45), "mode": "evolve", "verdict": "PROMOTED", "target": "fake-rule",
         "kind": "rule", "note": "裁决史交叉用", "evidence": "冒烟"},
    ]


def s_judged_low_agree() -> list[dict]:
    """正常 judged + 元技能预填确认率低于阈值 —— ⑧ 节确认率分支 + findings WARN。"""
    return s_pending_only() + [
        {"ts": ts(-40), "mode": "verify", "state": "judged", "ref": "T-pending",
         "verdicts": {"i1": "defect"}, "attribution": {"layer": "implementation"},
         "evidence": "元：实际跑不通", "prefill": {"skill": "sys-meta", "agree": False}},
    ]


CASES = [
    dict(name="空账本（冷启动）", recs=s_empty, expect=["[冷启动]"], cold=True),
    dict(name="只有 pending（0 judged，崩溃回归守卫）", recs=s_pending_only, expect=["元验证债"], cold=True),
    dict(name="畸形 + 幽灵 + 重复 judged", recs=s_malformed,
         expect=["[畸形]", "[幽灵裁决]"], cold=True),
    dict(name="正常 judged + 低确认率", recs=s_judged_low_agree,
         expect=["预填确认率", "低于阈值"], cold=True),
]


def main() -> int:
    real_before = (REAL_LEDGER.stat().st_size, REAL_LEDGER.stat().st_mtime) if REAL_LEDGER.exists() else None
    red = 0
    for c in CASES:
        code, out, err, written = run(c["recs"]())
        problems = []
        if code != 0:
            problems.append(f"退出码 {code}（期望 0）")
        if "Traceback" in err or "Traceback" in out:
            problems.append("出现 Traceback——报告器不得因数据形态崩溃（§5.5 免疫律）")
        reports = [r for r in written if r.get("mode") == "evolve" and r.get("verdict") == "REPORT"]
        if not reports:
            problems.append("REPORT 未落账——sleep 基线与醒来信号丢失")
        elif not isinstance(reports[-1].get("commits"), int):
            problems.append("REPORT 缺 commits 基准（sleep 闸消费端）")
        elif bool(reports[-1].get("cold_start")) != c["cold"]:
            problems.append(f"cold_start 标记不符（期望 {c['cold']}）")
        for marker in c["expect"]:
            if marker not in out:
                problems.append(f"stdout 缺预期标记 {marker!r}")
        status = "PASS" if not problems else "RED "
        print(f"  [{status}] {c['name']}" + (f"  ← {'；'.join(problems)}" if problems else ""))
        red += bool(problems)
    real_after = (REAL_LEDGER.stat().st_size, REAL_LEDGER.stat().st_mtime) if REAL_LEDGER.exists() else None
    if real_before != real_after:
        print("  [RED ] 真账本被写入——冒烟必须沙盒隔离（规则域模式 3）")
        red += 1
    else:
        print("  [PASS] 真账本未被触碰（沙盒隔离）")
    print(f"\n报告器冒烟：{len(CASES) + 1} 项，红 {red}")
    return 0 if red == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
