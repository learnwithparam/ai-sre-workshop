import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * One source of truth for e2e config, fail-fast. Values come from the repo-root `.env`, with
 * `process.env` winning. With PUBLIC_DOMAIN set, every UI is `https://<name>.<domain>` (the VPS
 * layout in caddy/Caddyfile); without it, each UI is its local port.
 */
export const ROOT = resolve(__dirname, "../..");
const ENV_FILE = resolve(ROOT, ".env");

const fileEnv: Record<string, string> = {};
if (existsSync(ENV_FILE)) {
  for (const line of readFileSync(ENV_FILE, "utf8").split("\n")) {
    const eq = line.indexOf("=");
    if (eq > 0 && !line.trim().startsWith("#")) fileEnv[line.slice(0, eq).trim()] = line.slice(eq + 1).trim();
  }
}

const required = (key: string): string => {
  const value = process.env[key] ?? fileEnv[key];
  if (!value) throw new Error(`Missing '${key}'. Run \`make env\` or set it in ${ENV_FILE}.`);
  return value;
};

const domain = process.env.PUBLIC_DOMAIN ?? fileEnv.PUBLIC_DOMAIN;
const url = (name: string, port: number): string =>
  domain ? `https://${name}.${domain}` : `http://localhost:${port}`;

export const config = {
  appUrl: url("app", 8000),
  chatUrl: url("chat", 3080),
  sreUrl: url("sre", 8090),
  hyperdxUrl: url("hyperdx", 8080),
  approver: { email: required("SRE_APPROVER_EMAIL"), password: required("SRE_APPROVER_PASSWORD") },
  chatUser: { email: required("LIBRECHAT_USER_EMAIL"), password: required("LIBRECHAT_USER_PASSWORD") },
  hyperdxUser: { email: required("HYPERDX_USER_EMAIL"), password: required("HYPERDX_USER_PASSWORD") },
  reader: { user: "sre_agent", password: required("CLICKHOUSE_READER_PASSWORD") },
  openrouterKey: required("OPENROUTER_API_KEY"),
  hyperdxKey: required("HYPERDX_API_KEY"),
} as const;
