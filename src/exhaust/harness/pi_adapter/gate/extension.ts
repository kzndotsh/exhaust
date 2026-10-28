/**
 * exhaust's gate extension (ADR 0025). One job: relay, never decide.
 *
 * Registers exactly seven tools — the six `AgentAction` variants plus a
 * zero-argument handshake tool — and forwards every call made through them
 * to exhaust's own Harness process over a Unix domain socket, one
 * connection per call. The socket path comes from `EXHAUST_RELAY_SOCKET`,
 * set by `PiAgentSession.launch()` before spawning this process.
 *
 * Deliberately NOT built on `ctx.ui`: Pi's extension-UI subprotocol
 * (`select`/`confirm`/`input`/`editor`) is narrow, human-dialog-shaped,
 * and auto-resolves with a default value on timeout — exactly the
 * silently-default-to-allow failure mode exhaust's own approvals model
 * (ADR 0023) exists to rule out. A dedicated socket carries the actual
 * `{tool, input}` -> `{ok, output}` round trip instead, with no implicit
 * timeout-driven default.
 *
 * The field tables below (`PARAMETERS`) are the TypeScript half of the
 * wire contract; `exhaust.harness.pi_adapter.schema.RELAY_TOOL_FIELDS` is
 * the Python half. There is no generated pipeline between them — six
 * fixed, rarely-changing action types don't earn one — so a human keeps
 * the two in sync, and `tests/test_pi_adapter_translate.py` pins the
 * Python side's actual field requirements as the anchor to check against.
 */

import * as net from "node:net";
import type { ExtensionAPI, ToolCallEvent, ToolCallEventResult } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const RELAY_TOOL_NAMES = [
	"sandbox_call",
	"real_target_call",
	"record_finding",
	"propose_verdict",
	"self_report",
	"set_vertical_state",
	"exhaust_handshake",
] as const;

type RelayToolName = (typeof RELAY_TOOL_NAMES)[number];

const PARAMETERS: Record<RelayToolName, ReturnType<typeof Type.Object>> = {
	sandbox_call: Type.Object({
		tool: Type.String(),
		method: Type.String(),
		params: Type.Record(Type.String(), Type.Unknown()),
	}),
	real_target_call: Type.Object({
		tool: Type.String(),
		method: Type.String(),
		params: Type.Record(Type.String(), Type.Unknown()),
		target: Type.String(),
	}),
	record_finding: Type.Object({
		claim: Type.String(),
		severity: Type.String(),
		scope: Type.String(),
		evidence_scratch_path: Type.String(),
	}),
	propose_verdict: Type.Object({
		finding_id: Type.String(),
		verdict_type: Type.String(),
		note: Type.Optional(Type.String()),
		requirements: Type.Optional(Type.String()),
		supporting_evidence: Type.Optional(Type.Array(Type.String())),
		contradicting_evidence: Type.Optional(Type.Array(Type.String())),
	}),
	self_report: Type.Object({
		tools_exercised: Type.Array(Type.String()),
		findings_dispositioned: Type.Array(Type.String()),
		no_further_avenues: Type.Boolean(),
	}),
	set_vertical_state: Type.Object({
		reason: Type.String(),
	}),
	exhaust_handshake: Type.Object({}),
};

interface RelayReply {
	ok: boolean;
	output: string;
}

function relaySocketPath(): string {
	const path = process.env.EXHAUST_RELAY_SOCKET;
	if (!path) {
		throw new Error("EXHAUST_RELAY_SOCKET is not set; the exhaust gate extension cannot relay calls");
	}
	return path;
}

/** One connection, one JSON request line out, one JSON response line in. */
function relay(toolName: RelayToolName, input: Record<string, unknown>): Promise<RelayReply> {
	return new Promise((resolve, reject) => {
		const socket = net.createConnection(relaySocketPath());
		let buffer = "";

		socket.on("connect", () => {
			socket.end(`${JSON.stringify({ tool: toolName, input })}\n`);
		});
		socket.on("data", (chunk: Buffer) => {
			buffer += chunk.toString("utf8");
		});
		socket.on("error", reject);
		socket.on("close", () => {
			const line = buffer.split("\n", 1)[0];
			if (!line) {
				reject(new Error(`exhaust relay closed with no reply for ${toolName}`));
				return;
			}
			try {
				resolve(JSON.parse(line) as RelayReply);
			} catch (err) {
				reject(err);
			}
		});
	});
}

export default function exhaustGate(pi: ExtensionAPI): void {
	for (const name of RELAY_TOOL_NAMES) {
		pi.registerTool({
			name,
			label: name,
			description:
				`exhaust relay tool, forwarded to the Harness's own ${name} handling. ` +
				"Never executed locally; see exhaust.harness.pi_adapter.translate for what it becomes.",
			parameters: PARAMETERS[name],
			execute: async (_toolCallId, params) => {
				const { ok, output } = await relay(name, params as Record<string, unknown>);
				return { content: [{ type: "text", text: output }], details: {}, isError: !ok };
			},
		});
	}

	// Defense in depth: nothing other than our own seven relay tools may ever execute,
	// even if a built-in tool or a future upgrade somehow becomes reachable. Checked before
	// any execute() above runs, so an unexpected tool never reaches the relay at all.
	pi.on("tool_call", (event: ToolCallEvent): ToolCallEventResult | undefined => {
		if (!(RELAY_TOOL_NAMES as readonly string[]).includes(event.toolName)) {
			return { block: true, reason: "exhaust: only relayed AgentActions may execute" };
		}
		return undefined;
	});
}
