/**
 * BCP 机械检查命令（/check）
 *
 * 键入 /check → 运行 bcp/check.py（零 LLM）。
 * FAIL：把裁决注入会话，按每条标注的修复方向处理（改代码/改文档/改计划）；
 * PASS：注入收尾清单（避坑→AGENTS.md，定论→Blueprint.md 需批准，删除计划文件）。
 *
 * 检查是机械闸门，不依赖 LLM「记得跑检查」。
 */

import { existsSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function bcpCheckExtension(pi: ExtensionAPI) {
	const findLatestPlan = (): string | undefined => {
		const plansDir = join(process.cwd(), "bcp", "plans");
		if (!existsSync(plansDir)) return undefined;
		const plans = readdirSync(plansDir)
			.filter((f) => f.endsWith(".plan.md"))
			.map((f) => join(plansDir, f))
			.filter((p) => statSync(p).isFile())
			.sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs);
		return plans[0];
	};

	pi.registerCommand("check", {
		description: "机械检查：对计划跑 bcp/check.py（--plan <file> 可指定，默认 bcp/plans/ 最新）",
		getArgumentCompletions: (prefix: string) => {
			const plansDir = join(process.cwd(), "bcp", "plans");
			if (!existsSync(plansDir)) return null;
			const items = readdirSync(plansDir)
				.filter((f) => f.endsWith(".plan.md"))
				.map((f) => join("bcp", "plans", f));
			const filtered = items.filter((p) => p.includes(prefix));
			return filtered.length > 0 ? filtered.map((p) => ({ value: p, label: p })) : null;
		},
		handler: async (args: string, ctx) => {
			// 1. 定位计划文件：显式参数 > bcp/plans/ 最新
			let plan = args.trim();
			if (!plan) {
				const latest = findLatestPlan();
				if (!latest) {
					ctx.ui.notify("没有计划文件：/check <path>，或先 /plan 产出 bcp/plans/<slug>.plan.md", "warning");
					return;
				}
				// 计划文件唯一合法位置：bcp/plans/（根 plan.md 只放 schema）
				plan = latest;
			}
			if (!existsSync(resolve(ctx.cwd, plan))) {
				ctx.ui.notify(`计划文件不存在：${plan}`, "error");
				return;
			}

			// 2. 机械执行对碰器（零 LLM；cwd = 项目根）
			const r = await pi.exec("python3", ["bcp/check.py", "--plan", plan, "--collision"], {
				cwd: ctx.cwd,
				timeout: 600_000,
			});
			const output = `${r.stdout}${r.stderr}`.trim();

			// 3. 裁决注入会话（sendUserMessage 触发下一轮）
			if (r.code === 0) {
				ctx.ui.notify(`检查 PASS：${plan}`, "info");
				pi.appendEntry("bcp-check", { plan, verdict: "PASS", output });
				pi.sendUserMessage(
					`[bcp-check] 检查 PASS（${plan}）。收尾：\n` +
						`1. ≤3 条避坑写入对应 .pi/rules/<域>.md（无对应文件则新建并在 AGENTS.md 域映射表登记）；\n` +
						`2. 0–1 条设计定论回写 Blueprint.md（范式层则回写 BCP.md，先征得用户确认）；\n` +
						`3. 删除计划文件 ${plan}（成功即删，失败才留档）。`,
				);
			} else {
				ctx.ui.notify("检查 FAIL，裁决已注入会话", "warning");
				pi.appendEntry("bcp-check", { plan, verdict: "FAIL", output });
				pi.sendUserMessage(
					`[bcp-check] 检查 FAIL（${plan}）。机械裁决：\n\n${output}\n\n` +
						`按每条标注的修复方向处理（改代码 / 改文档 / 改计划），改完再次 /check。` +
						`若本任务最终以 FAIL 收尾（不再重试）：强制失败典藏（BCP §1）——压缩一条失败模式` +
						`（标题+规避句 ≤200 字符）追加 bcp/ledger.jsonl（mode=failure，字段 title/avoidance/domain，§4.3）` +
						`+ 对应 .pi/rules/<域>.md。`,
				);
			}
		},
	});
}
