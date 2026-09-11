#!/usr/bin/env python3
"""BCP 宿主行为契约一致性向量集（零 LLM，Blueprint §8.2 / kit/host-contract.md §4）。

参考实现 GateCore = 契约语义的可执行形式（从 pi 适配层 memory-gate.ts 行为抽取）。
移植者：在目标宿主实现等价闸门后，写薄适配器把宿主事件喂给同一 VECTORS——全绿才算
等价机械层。用法：python3 kit/host-contract.test.py（退出码 0=全绿，1=有红）。
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass

# ---------------------------------------------------------------- 参考实现
@dataclass
class Action:
    block: bool
    reason: str = ""


class GateCore:
    """契约 §2/§3 的纯函数化参考：依赖全部注入（rules_reader/size_of/commit_delta）。"""

    def __init__(self, *, routes, big_read_bytes, sleep_threshold, rules_reader, size_of, commit_delta,
                 has_baseline=True):
        self.routes = routes                    # [(绝对前缀, 域)]
        self.big_read_bytes = big_read_bytes
        self.sleep_threshold = sleep_threshold
        self.rules_reader = rules_reader        # domain -> str | None（None=缺失→fail-open）
        self.size_of = size_of                  # path -> int | None（None=stat 失败→放行）
        self.commit_delta = commit_delta        # () -> int
        self.has_baseline = has_baseline        # 账本有无基线记录（§5.6）；False = 冷启动 → 文案分支
        self.events: list[dict] = []            # 账本事件（mode=gate）
        self.injected_domains: set[str] = set()
        self.big_read_warned: set[str] = set()
        self.compacted = False
        self.sleep_pulsed = False

    def on_session_compact(self) -> None:
        self.compacted = True

    def _log(self, kind: str, target: str, verdict: str, **extra) -> None:
        self.events.append({"mode": "gate", "verdict": verdict, "kind": kind, "target": target, **extra})

    def on_tool_call(self, tool: str, abs_path: str) -> Action | None:
        if tool not in ("read", "edit", "write"):  # 契约 §3.3：bash 是已知缺口
            return None
        # ① sleep（每会话至多一次脉冲；首个调用即消耗资格）
        if not self.sleep_pulsed:
            self.sleep_pulsed = True
            if self.commit_delta() > self.sleep_threshold:
                self._log("sleep", "pulse", "INJECTED")
                # 无基线记录 = 冷启动：文案为「基线引导」而非「经验积压」（Blueprint §5.6）
                return Action(True, "sleep pulse：基线引导（账本尚无巡检记录）" if not self.has_baseline
                              else "sleep pulse：催巡检")
        # ② compact-restore（每次压缩后一次）
        if self.compacted:
            self.compacted = False
            self._log("compact-restore", abs_path, "INJECTED")
            return Action(True, "compaction 恢复：重读计划文件对齐 Σt")
        # ③ skill-recall（只记账不拦截，read only）
        m = re.search(r"deliverables[/\\]([^/\\]+)[/\\]SKILL\.md$", abs_path)
        if tool == "read" and m:
            self._log("skill-recall", m.group(1), "READ")
        # ④ big-read（read only；stat 失败放行）
        if tool == "read" and self.big_read_bytes > 0:
            size = self.size_of(abs_path)
            if size is not None and size > self.big_read_bytes and abs_path not in self.big_read_warned:
                self.big_read_warned.add(abs_path)
                self._log("big-read", abs_path, "INJECTED")
                return Action(True, "大文件整读：先定位再定点读")
        # ⑤ domain（每域每会话一次；规则缺失 fail-open 且域仍标记已处理）
        for prefix, domain in self.routes:
            if abs_path.startswith(prefix):
                if domain in self.injected_domains:
                    return None
                rules = self.rules_reader(domain)
                self.injected_domains.add(domain)
                if rules is None:
                    self._log("domain", domain, "FAIL_OPEN")
                    return None
                self._log("domain", domain, "INJECTED", domain=domain, file=abs_path)
                return Action(True, rules)
        return None


# ---------------------------------------------------------------- 向量集
ROUTES = [("/repo/bcp/", "bcp"), ("/repo/.pi/extensions/", "bcp")]
RULES = {"bcp": "RULES-BCP-TEXT"}


def harness(rules=RULES, sizes=None, delta=0, has_baseline=True):
    sizes = sizes or {}
    return GateCore(
        routes=ROUTES, big_read_bytes=20 * 1024, sleep_threshold=30,
        rules_reader=lambda d: rules.get(d), size_of=sizes.get,
        commit_delta=lambda: delta, has_baseline=has_baseline,
    )


# 每条：name, steps=[(setup_fn | None, tool, path, expect)], expect=(block?, reason_sub | None, last_event | None)
VECTORS: list[dict] = [
    dict(name="v_domain_first_touch", h=lambda: harness(), steps=[
        (None, "read", "/repo/bcp/check.py", (True, "RULES-BCP-TEXT", ("domain", "INJECTED"))),
    ]),
    dict(name="v_domain_once_per_session", h=lambda: harness(), steps=[
        (None, "read", "/repo/bcp/check.py", (True, "RULES-BCP-TEXT", ("domain", "INJECTED"))),
        (None, "read", "/repo/bcp/evolve.py", (False, None, None)),  # 同域第二文件：放行且无新事件
    ]),
    dict(name="v_unrouted_passthrough", h=lambda: harness(), steps=[
        (None, "read", "/repo/src/main.rs", (False, None, None)),
    ]),
    dict(name="v_rules_missing_failopen", h=lambda: harness(rules={}), steps=[
        (None, "read", "/repo/bcp/check.py", (False, None, ("domain", "FAIL_OPEN"))),
        (None, "read", "/repo/bcp/evolve.py", (False, None, None)),  # 域已标记，不再重试
    ]),
    dict(name="v_big_read_once_and_read_only", h=lambda: harness(sizes={"/repo/big.txt": 21 * 1024}), steps=[
        (None, "read", "/repo/big.txt", (True, "大文件", ("big-read", "INJECTED"))),
        (None, "read", "/repo/big.txt", (False, None, None)),   # 重试放行（一次性）
        (None, "edit", "/repo/big.txt", (False, None, None)),   # edit 不触发 big-read（read only 语义）
    ]),
    dict(name="v_compact_restore_once", h=lambda: harness(), steps=[
        (lambda g: g.on_session_compact(), "read", "/repo/src/a.rs", (True, "Σt", ("compact-restore", "INJECTED"))),
        (None, "read", "/repo/src/b.rs", (False, None, None)),  # 只恢复一次
    ]),
    dict(name="v_skill_recall_log_only", h=lambda: harness(), steps=[
        (None, "read", "/repo/deliverables/foo/SKILL.md", (False, None, ("skill-recall", "READ"))),
        (None, "read", "/repo/deliverables/foo/SKILL.md", (False, None, ("skill-recall", "READ"))),  # 每次都记，永不拦
    ]),
    dict(name="v_sleep_pulse_once", h=lambda: harness(delta=31), steps=[
        (None, "read", "/repo/src/a.rs", (True, "sleep", ("sleep", "INJECTED"))),
        (None, "read", "/repo/src/b.rs", (False, None, None)),  # 脉冲已消耗
    ]),
    dict(name="v_sleep_threshold_boundary", h=lambda: harness(delta=30), steps=[
        (None, "read", "/repo/src/a.rs", (False, None, None)),  # = 阈值不触发（严格大于）
    ]),
    dict(name="v_sleep_coldstart_bootstrap_text", h=lambda: harness(delta=31, has_baseline=False), steps=[
        # 冷启动（账本无基线记录）：仍拦截，但文案 = 基线引导，不得宣称经验积压（Blueprint §5.6）
        (None, "read", "/repo/src/a.rs", (True, "基线引导", ("sleep", "INJECTED"))),
    ]),
    dict(name="v_priority_sleep_over_compact", h=lambda: harness(delta=31), steps=[
        (lambda g: g.on_session_compact(), "read", "/repo/src/a.rs", (True, "sleep", ("sleep", "INJECTED"))),
        (None, "read", "/repo/src/b.rs", (True, "Σt", ("compact-restore", "INJECTED"))),  # 压缩恢复顺延
    ]),
    dict(name="v_priority_compact_over_domain", h=lambda: harness(), steps=[
        (lambda g: g.on_session_compact(), "read", "/repo/bcp/check.py", (True, "Σt", ("compact-restore", "INJECTED"))),
        (None, "read", "/repo/bcp/check.py", (True, "RULES-BCP-TEXT", ("domain", "INJECTED"))),
    ]),
    dict(name="v_bash_known_gap", h=lambda: harness(), steps=[
        (None, "bash", "/repo/bcp/check.py", (False, None, None)),  # 契约 §3.3：非三工具不拦
    ]),
    dict(name="v_edit_routed_first_touch", h=lambda: harness(), steps=[
        (None, "edit", "/repo/.pi/extensions/memory-gate.ts", (True, "RULES-BCP-TEXT", ("domain", "INJECTED"))),
    ]),
    dict(name="v_write_new_file_routed", h=lambda: harness(), steps=[
        (None, "write", "/repo/bcp/plans/x.plan.md", (True, "RULES-BCP-TEXT", ("domain", "INJECTED"))),
    ]),
]


def main() -> int:
    bad = 0
    for v in VECTORS:
        g = v["h"]()
        n_ev0 = len(g.events)
        for i, (setup, tool, path, expect) in enumerate(v["steps"]):
            if setup:
                setup(g)
            act = g.on_tool_call(tool, path)
            want_block, want_sub, want_ev = expect
            got_block = bool(act and act.block)
            errs = []
            if got_block != want_block:
                errs.append(f"block={got_block} 期望 {want_block}")
            if want_sub and (not act or want_sub not in act.reason):
                errs.append(f"reason 缺 {want_sub!r}: {act.reason if act else '—'}")
            # last_event 断言：expect 给 (kind, verdict) 时，本步后事件数应 +1 且末条匹配；None = 无新事件
            if want_ev is None:
                if len(g.events) != n_ev0:
                    errs.append(f"意外新事件: {g.events[n_ev0:]}")
            else:
                if len(g.events) != n_ev0 + 1:
                    errs.append(f"期望恰好 1 条新事件，实得 {g.events[n_ev0:]}")
                else:
                    e = g.events[-1]
                    if (e["kind"], e["verdict"]) != want_ev:
                        errs.append(f"事件 {(e['kind'], e['verdict'])} 期望 {want_ev}")
            n_ev0 = len(g.events)
            if errs:
                bad += 1
                print(f"[FAIL] {v['name']} 步{i}（{tool} {path}）: {'; '.join(errs)}")
                break
        else:
            print(f"[ok]   {v['name']}")
    print(f"\n一致性向量：{len(VECTORS)} 条，红 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
