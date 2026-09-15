import { config } from "../lib/config";
import { inspect } from "../lib/stack";
import { expect, test } from "../lib/ui";

const SERVICES = [
  "clickstack", "postgres-db", "docs-loader", "subscription-app", "traffic",
  "mongodb", "librechat", "mcp-clickhouse", "sre-control", "otel-collector",
]; // prettier-ignore

test("every service is healthy", async ({ request }) => {
  for (const name of SERVICES) {
    expect(inspect(name, "{{.State.Health.Status}}"), name).toBe("healthy");
  }
  for (const url of [`${config.appUrl}/health`, `${config.sreUrl}/healthz`, `${config.chatUrl}/health`]) {
    expect((await request.get(url)).status(), url).toBe(200);
  }
});
