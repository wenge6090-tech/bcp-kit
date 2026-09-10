/**
 * BCP 记忆闸门（memory-gate）——模板通用版
 *
 * 三个机械注入点（全部零 LLM，宿主强制，不依赖 agent 自觉）：
 *
 * 1. 域规则注入：agent 首次触碰某代码域文件（read/edit/write）时，拦截该次调用，
 *    把 .pi/rules/<域>.md 全文作为 block reason 注入；重试即放行，会话内每域只拦一次。
 *    ROUTES 按项目填写（路径前缀 → 域名）；空表 = 不拦截。
 *
 * 2. 大文件读取附注：read 目标 > BIG_READ_KB 时拦截一次，提示先定位再定点读
 *    （offset/limit）；重试即放行，会话内每文件只拦一次。整读冷储层大文档是
 *    上下文的最大可控浪费（一次 = 数十 KB 税），此处机械化"先看大小"反射。
 *
 * 3. compaction 恢复注入：会话压缩后（摘要 = 有损），首次工具调用时拦截一次，
 *    注入"重读当前计划文件对齐进度"——执行状态 Σt 落盘在 bcp/plans/，过程可丢、
 *    状态必恢复（结构化状态投影）。
 *
 * 设计决定：README.md §5.5 / §8.3。触发信号 = 文件路径与事件（机械事实），无 LLM 判断。
 * 所有拦截 fail-open：规则缺失/异常放行 + notify，绝不死锁。注入事件入 bcp/ledger.jsonl
 * （mode=gate，写失败静默跳过）。
 */

import { appendFileSync, existsSync, readFileSync, statSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// ── 按项目配置 ────────────────────────────────────────────────
// 路径前缀 → 规则域（与 AGENTS.md「规则域映射」表同步）。示例：
// const ROUTES: [prefix: string, domain: string][] = [
//   ["src/types/", "types"], ["src/infra/", "infra"],
// ];
const ROUTES: [prefix: string, domain: string][] = [
	["bcp/", "bcp"],
	[".pi/extensions/", "bcp"],
];

/** 大文件整读拦截阈值（字节）。~20KB ≈ 5-7k tokens。0 = 关闭。 */
const BIG_READ_KB = 20;

/** sleep 闸触发阈值（commit 数，README §4.7）：自上次巡检（evolve REPORT 落账）以来的活动量。 */
const SLEEP_COMMIT_THRESHOLD = 30;
// ─────────────────────────────────────────────────────────────

const BIG_READ_BYTES = BIG_READ_KB * 1024;

// ── sleep 闸 helpers（README §4.7）：活动量 = 当前 commit 数 − 最后一条 evolve 记录的 commits 基准 ──
function lastReportCommits(root: string): number {
	try {
		const lines = readFileSync(join(root, "bcp", "ledger.jsonl"), "utf-8").trim().split("\n");
		for (let i = lines.length - 1; i >= 0; i--) {
			const r = JSON.parse(lines[i]) as { mode?: string; commits?: number };
			if (r.mode === "evolve") return typeof r.commits === "number" ? r.commits : 0;
		}
	} catch {
		/* 冷启动/账本不可读 = 0（冷启动豁免自然成立） */
	}
	return 0;
}

function commitCount(root: string): number {
	try {
		return parseInt(execSync("git rev-list --count HEAD", { cwd: root }).toString().trim(), 10) || 0;
	} catch {
		return 0; // 非 git 项目 = 0 → 差值恒 ≤ 阈值，天然 fail-open
	}
}

function localTs(): string {
	const d = new Date();
	const p = (n: number) => String(n).padStart(2, "0");
	return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

// 工具包根归一化（防乌龙）：ctx.cwd = pi 启动目录，子目录启动会把账本写到 <子目录>/bcp/（分裂）。
// 向上找范式件特征（.pi/APPEND_SYSTEM.md），找不到则返回原目录（fail-open，与非工具包项目兼容）。
function projectRoot(start: string): string {
	let dir = start;
	while (true) {
		if (existsSync(join(dir, ".pi", "APPEND_SYSTEM.md"))) return dir;
		const parent = dirname(dir);
		if (parent === dir) return start;
		dir = parent;
	}
}

function logGate(cwd: string, kind: string, target: string, verdict: string, extra?: Record<string, unknown>) {
	try {
		appendFileSync(
			join(cwd, "bcp", "ledger.jsonl"),
			// §4.3 契约：域注入事件 {domain, file}；kind/target 为兼容字段（evolve.py 兼容读两端）
			JSON.stringify({ ts: localTs(), mode: "gate", verdict, fail: 0, warn: 0, findings: [], kind, target, ...extra }) + "\n",
		);
	} catch {
		/* 证据流失败不影响注入 */
	}
}

export default function memoryGate(pi: ExtensionAPI) {
	const injectedDomains = new Set<string>(); // 每域只拦一次
	const bigReadWarned = new Set<string>(); // 每大文件只拦一次
	let compacted = false; // compaction 后首次工具调用拦截一次
	let sleepPulsed = false; // sleep 闸（§4.7）：会话只催一次巡检

	pi.on("session_start", async () => {
		injectedDomains.clear();
		bigReadWarned.clear();
		sleepPulsed = false;
		compacted = false;
	});

	pi.on("session_compact", async (_event, ctx) => {
		compacted = true;
		ctx.ui?.notify?.("memory-gate: 会话已压缩——下次工具调用将注入状态恢复指引（计划文件 = Σt）", "info");
	});

	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName !== "read" && event.toolName !== "edit" && event.toolName !== "write") {
			return;
		}
		const raw = (event.input as { path?: string }).path;
		if (!raw) return;
		const sessionCwd = ctx.cwd ?? process.cwd();
		const root = projectRoot(sessionCwd); // 账本/ROUTES 基准 = 工具包根；相对路径解析仍按会话 cwd（agent 语义不变）
		const abs = resolve(sessionCwd, raw);

		// sleep 闸（README §4.7）：活动量超阈 → 催一次巡检（正反旋转：阴对账列清单，阳执行打勾，元独占裁决）
		if (!sleepPulsed) {
			sleepPulsed = true;
			if (commitCount(root) - lastReportCommits(root) > SLEEP_COMMIT_THRESHOLD) {
				logGate(root, "sleep", "pulse", "INJECTED");
				return {
					block: true,
					reason:
						`[memory-gate] sleep 闸：自上次巡检以来活动量已超 ${SLEEP_COMMIT_THRESHOLD} 个 commit——液态经验在积压，固态储层待归一化。` +
						`执行 sleep 巡检（/sleep 命令或按 README §4.7 清单流）：机械对账（evolve.py + check.py --selfcheck）→ 列清单 → 元逐条裁决 → 打勾 → ` +
						`清单完成即重跑 evolve.py 落 REPORT 账（sleep 结束，本闸自动重置）。` +
						`本次调用已标记已催，重发即放行。`,
				};
			}
		}

		// ③ compaction 恢复（优先级最高，且与域注入不冲突——放行本次调用，只附带注入）
		if (compacted) {
			compacted = false;
			logGate(root, "compact-restore", raw, "INJECTED");
			return {
				block: true,
				reason:
					`[memory-gate] 会话已经历 compaction（早期细节被摘要，可能有损）。对齐进度：读 ` +
					`bcp/plans/ 下最新计划文件（执行状态 Σt，条目勾选即进度），按未完成项继续；` +
					`若无计划文件，按 AGENTS.md 重建当前任务上下文后继续本次调用。\n\n` +
					`(本次原调用已放行语义：重新发起即可执行)`,
			};
		}

		// ② 大文件整读附注
		// 技能召回记账（README §4.3/§9.1）：读技能正文 = 匹配召回事件，只记账不拦截（§5.5 漏斗第三层）
		if (event.toolName === "read") {
			const dm = abs.match(/deliverables[/\\][^/\\]+[/\\]SKILL\.md$/);
			if (dm) logGate(root, "skill-recall", dm[1], "READ");
		}
		if (event.toolName === "read" && BIG_READ_BYTES > 0) {
			try {
				if (statSync(abs).size > BIG_READ_BYTES && !bigReadWarned.has(abs)) {
					bigReadWarned.add(abs);
					const lines = readFileSync(abs, "utf-8").split("\n").length;
					logGate(root, "big-read", raw, "INJECTED");
					return {
						block: true,
						reason:
							`[memory-gate] ${raw} 为大文件（>${BIG_READ_KB}KB，${lines} 行）。整读是一次性大额上下文税。` +
							`若只需部分内容：先 bash grep -n 关键词定位，再带 offset/limit 定点读。` +
							`确认确需整读（如全文重构），重发同一调用即放行（本会话不再拦此文件）。`,
					};
				}
			} catch {
				/* stat 失败 = 文件不存在，放行让 read 自己报错 */
			}
		}

		// ① 域规则注入
		const hit = ROUTES.find(([prefix]) => abs.startsWith(resolve(root, prefix)));
		if (!hit) return;
		const domain = hit[1];
		if (injectedDomains.has(domain)) return;

		let rules: string;
		try {
			rules = readFileSync(join(cwd, ".pi", "rules", `${domain}.md`), "utf-8");
		} catch {
			ctx.ui?.notify?.(`memory-gate: 规则文件缺失 .pi/rules/${domain}.md（fail-open 放行）`, "warning");
			logGate(root, "domain", domain, "FAIL_OPEN");
			injectedDomains.add(domain);
			return;
		}
		injectedDomains.add(domain);
		logGate(root, "domain", domain, "INJECTED", { domain, file: abs }); // §4.3 {domain, file}
		return {
			block: true,
			reason:
				`[memory-gate] 首次触碰 ${domain} 域（${abs}），以下避坑规则已强制注入。` +
				`吸收后重新发起同一调用即可继续（本会话不再拦截）：\n\n${rules}`,
		};
	});
}
