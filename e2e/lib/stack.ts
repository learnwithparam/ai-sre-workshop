import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { config, ROOT } from "./config";

/**
 * Ground truth for assertions comes from the stack itself, never from what a page claims:
 * ClickHouse (telemetry and the sre.incident_events audit log), Docker, and Postgres. Every call
 * goes through `docker exec`, so the same suite runs on a laptop or on the VPS box.
 */

const run = (cmd: string, args: string[], env: Record<string, string> = {}): string =>
  execFileSync(cmd, args, { cwd: ROOT, env: { ...process.env, ...env }, encoding: "utf8", timeout: 120_000 });

// The password travels as an environment variable, never as an argument in a process list.
export const clickhouse = <T = Record<string, unknown>>(sql: string, asUser = config.reader): T[] => {
  const out = run(
    "docker",
    ["exec", "-e", "CLICKHOUSE_PASSWORD", "clickstack", "clickhouse-client", "--user", asUser.user,
     "--query", `${sql} FORMAT JSONEachRow`], // prettier-ignore
    { CLICKHOUSE_PASSWORD: asUser.password },
  );
  return out.split("\n").filter(Boolean).map((line) => JSON.parse(line) as T);
};

/** Runs a statement expecting ClickHouse to refuse it; returns the error text. */
export const clickhouseError = (sql: string): string => {
  try {
    clickhouse(sql);
  } catch (err) {
    return String((err as { stderr?: string }).stderr ?? err);
  }
  throw new Error(`ClickHouse accepted: ${sql}`);
};

export const postgres = (sql: string): string =>
  run("docker", ["exec", "postgres-db", "psql", "-U", "postgres", "-tAc", sql]).trim();

/** Every tool call LibreChat stored for one conversation, in order. */
export const chatToolCalls = (conversationId: string): string[] =>
  JSON.parse(
    run("docker", [
      "exec", "mongodb", "mongosh", "LibreChat", "--quiet", "--eval",
      `JSON.stringify(db.messages.find({ conversationId: ${JSON.stringify(conversationId)} })
        .sort({ createdAt: 1 }).toArray()
        .flatMap(m => (m.content || []).filter(p => p.type === "tool_call").map(p => p.tool_call.name)))`,
    ]), // prettier-ignore
  ) as string[];

const mongo = (js: string): string =>
  run("docker", ["exec", "mongodb", "mongosh", "LibreChat", "--quiet", "--eval", js]).trim();

/**
 * Empties the AI SRE's chat history. Runs before the suite so the workspace on screen holds this
 * run's conversations and nothing else: the sidebar is part of what the workshop teaches from.
 */
export const clearChatHistory = (): void => {
  mongo("db.messages.deleteMany({}); db.conversations.deleteMany({});");
};

/**
 * Names a conversation after the incident it belongs to. LibreChat titles threads with the model,
 * which produces a different phrase every run, and the sidebar is in every screenshot.
 */
export const nameConversation = (conversationId: string, title: string): void => {
  mongo(
    `db.conversations.updateOne({ conversationId: ${JSON.stringify(conversationId)} },
      { $set: { title: ${JSON.stringify(title)} } })`,
  );
};

/** Prompt and completion tokens LibreChat recorded for one conversation. */
export const chatTokens = (conversationId: string): number =>
  Number(
    run("docker", [
      "exec", "mongodb", "mongosh", "LibreChat", "--quiet", "--eval",
      `db.transactions.aggregate([{ $match: { conversationId: ${JSON.stringify(conversationId)} } },
        { $group: { _id: null, t: { $sum: { $abs: "$rawAmount" } } } }]).toArray()[0]?.t ?? 0`,
    ]), // prettier-ignore
  );

export const inspect =(container: string, format: string): string =>
  run("docker", ["inspect", "-f", format, container]).trim();

export const containerEnv = (container: string, key: string): string | undefined =>
  inspect(container, "{{json .Config.Env}}")
    .replace(/^"|"$/g, "")
    .match(new RegExp(`"${key}=([^"]*)"`))?.[1];

/** `python -m sre_control.probe <args>` inside sre-control, which sits on the stack network. */
export const probe = <T>(...args: string[]): T =>
  JSON.parse(run("docker", ["exec", "sre-control", "python", "-m", "sre_control.probe", ...args])) as T;

export const chaos = (scenario: string): void => {
  run("uv", ["run", "--quiet", "python", "scripts/chaos.py", scenario]);
};

export type AuditEvent = {
  ms: number;
  incident_id: string;
  action_id: string;
  kind: string;
  actor: string;
  payload: Record<string, any>;
};

/** Audit events after `sinceMs`, oldest first, filtered by an extra SQL condition. */
export const auditEvents = (sinceMs: number, where = "1"): AuditEvent[] =>
  clickhouse<Omit<AuditEvent, "payload"> & { payload: string }>(
    `SELECT toUnixTimestamp64Milli(ts) AS ms, incident_id, action_id, kind, actor, payload
     FROM sre.incident_events
     WHERE ts >= fromUnixTimestamp64Milli(${Math.floor(sinceMs)}) AND ${where}
     ORDER BY ts LIMIT 1000`,
  ).map((e) => ({ ...e, ms: Number(e.ms), payload: JSON.parse(e.payload) }));

export const waitFor = async <T>(
  what: string,
  fn: () => T | undefined | false,
  timeoutMs: number,
  intervalMs = 3_000,
): Promise<T> => {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const value = fn();
    if (value) return value;
    if (Date.now() > deadline) throw new Error(`Timed out after ${timeoutMs / 1000}s waiting for ${what}`);
    await new Promise((r) => setTimeout(r, intervalMs));
  }
};

/** Facts one spec hands to a later one (incident ids, timings), kept under artifacts/. */
const STATE = resolve(ROOT, "artifacts/run-state.json");

export const state = {
  read: (): Record<string, any> => (existsSync(STATE) ? JSON.parse(readFileSync(STATE, "utf8")) : {}),
  merge: (patch: Record<string, unknown>): void => {
    mkdirSync(resolve(ROOT, "artifacts"), { recursive: true });
    writeFileSync(STATE, JSON.stringify({ ...state.read(), ...patch }, null, 2));
  },
};
