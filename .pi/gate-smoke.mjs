#!/usr/bin/env node
/**
 * memory-gate sleep 闸真件冒烟（pi 适配层专属，需 node ≥ 22 原生 TS 剥离；不属 Blueprint §8.2 最小契约）。
 *
 * 为什么要有它：kit/host-contract.test.py 测的是「行为契约的参考实现」——宿主无关、供移植者对齐，
 * 但它把基线抽象成注入的 commit_delta()，测不到真件对账本的真实解析（裁决记录跳过 / 账本缺失）。
 * §5.5「无物对碰 README 承诺↔机械层行为」的缺口由本脚本补：真件导入 + 沙盒仓库，
 * 满足规则模式 8「改 gate 必真触发一次并验 INJECTED 落账」。
 *
 * 纪律：只在 mkdtemp 沙盒里跑，真账本 bcp/ledger.jsonl 永不被触碰（规则模式 3）。
 * 用法：node .pi/gate-smoke.mjs   —— 退出码 = 失败场景数（0 = 全绿）
 */
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const GATE = join(dirname(fileURLToPath(import.meta.url)), "extensions", "memory-gate.ts");
const { default: memoryGate } = await import(GATE); // 真件（非参考实现）
const T = 30; // SLEEP_COMMIT_THRESHOLD

const git = (root, args) => execFileSync("git", args, { cwd: root, stdio: "ignore" });

/** 造沙盒：git 仓库 + commits 个空提交 + 指定账本行 */
function sandbox(tag, ledger, commits) {
	const root = mkdtempSync(join(tmpdir(), `bcp-gate-smoke-${tag}-`));
	mkdirSync(join(root, ".pi"), { recursive: true });
	mkdirSync(join(root, "bcp"), { recursive: true });
	writeFileSync(join(root, ".pi", "APPEND_SYSTEM.md"), ""); // projectRoot 特征文件
	writeFileSync(
		join(root, "bcp", "ledger.jsonl"),
		ledger.map((r) => JSON.stringify(r)).join("\n") + (ledger.length ? "\n" : ""),
	);
	git(root, ["init", "-q"]);
	git(root, ["config", "user.email", "smoke@bcp.local"]);
	git(root, ["config", "user.name", "smoke"]);
	for (let i = 0; i < commits; i++) git(root, ["commit", "-q", "--allow-empty", "-m", `c${i}`]);
	return root;
}

/** 跑真件：注册处理器 → session_start → 首次工具调用（sleep 闸消费脉冲资格） */
async function firstCall(root) {
	const handlers = {};
	memoryGate({ on: (n, f) => { handlers[n] = f; } });
	await handlers.session_start({}, { cwd: root });
	return handlers.tool_call({ toolName: "read", input: { path: "src/a.txt" } }, { cwd: root });
}

const REPORT = (commits) => ({ ts: "2026-09-01T00:00:00", mode: "evolve", verdict: "REPORT", commits, findings: [] });
const promoted = { ts: "2026-09-02T00:00:00", mode: "evolve", verdict: "PROMOTED", kind: "skill", target: "x" };
const pulsed = (events) => events.some((e) => e.kind === "sleep" && e.verdict === "INJECTED");

const SCENARIOS = [
	{
		name: "冷启动：无基线记录 → 文案 = 基线引导（Blueprint §5.6）",
		ledger: [],
		commits: T + 1,
		expect: (r, ev) => r?.block === true && /基线引导/.test(r.reason) && !/液态经验在积压/.test(r.reason) && pulsed(ev),
	},
	{
		name: "裁决记录不重置基线：REPORT(29) 后追加 PROMOTED → 活动量 2，放行",
		ledger: [REPORT(T - 1), promoted],
		commits: T + 1,
		expect: (r) => r == null,
	},
	{
		name: "真超阈：有基线且差值 > 阈值 → 文案 = 经验积压",
		ledger: [REPORT(0)],
		commits: T + 1,
		expect: (r, ev) => r?.block === true && /液态经验在积压/.test(r.reason) && !/基线引导/.test(r.reason) && pulsed(ev),
	},
];

let bad = 0;
for (const [i, s] of SCENARIOS.entries()) {
	const root = sandbox(String(i), s.ledger, s.commits);
	try {
		const r = await firstCall(root);
		const events = readFileSync(join(root, "bcp", "ledger.jsonl"), "utf-8")
			.trim().split("\n").filter(Boolean).map((l) => JSON.parse(l)).filter((e) => e.mode === "gate");
		const ok = s.expect(r, events);
		console.log(`  [${ok ? "PASS" : "FAIL"}] ${s.name}`);
		if (!ok) {
			bad++;
			console.log(`         reason = ${(r?.reason ?? "（放行）").replace(/\n/g, " ").slice(0, 110)}`);
		}
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
}
console.log(`\n${bad === 0 ? "PASS" : "FAIL"}：${SCENARIOS.length - bad}/${SCENARIOS.length} 场景通过（真件 + 沙盒，真账本未触碰）`);
process.exit(bad);
