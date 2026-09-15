"""Settings validated at boot. A missing value stops the process and names every gap at once."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REQUIRED = (
    "CLICKHOUSE_HOST",
    "CLICKHOUSE_READER_USER",
    "CLICKHOUSE_READER_PASSWORD",
    "CLICKHOUSE_WRITER_USER",
    "CLICKHOUSE_WRITER_PASSWORD",
    "SRE_MCP_TOKEN",
    "SRE_APPROVER_EMAIL",
    "SRE_APPROVER_PASSWORD",
    "SRE_SESSION_SECRET",
    "SRE_PUBLIC_URL",
    "CHAT_PUBLIC_URL",
    "WORKSHOP_DIR",
)


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    clickhouse_host: str
    reader_user: str
    reader_password: str
    writer_user: str
    writer_password: str
    mcp_token: str
    approver_email: str
    approver_password: str
    session_secret: str
    public_url: str
    chat_url: str
    workshop_dir: Path
    workshop_sql: Path = Path("/app/workshop")
    detector_interval_s: int = 10
    verify_timeout_s: int = 300


def load_settings(env: Mapping[str, str]) -> Settings:
    missing = [name for name in REQUIRED if not env.get(name)]
    if missing:
        raise ConfigError(f"sre-control cannot start, missing: {', '.join(missing)}")
    return Settings(
        clickhouse_host=env["CLICKHOUSE_HOST"],
        reader_user=env["CLICKHOUSE_READER_USER"],
        reader_password=env["CLICKHOUSE_READER_PASSWORD"],
        writer_user=env["CLICKHOUSE_WRITER_USER"],
        writer_password=env["CLICKHOUSE_WRITER_PASSWORD"],
        mcp_token=env["SRE_MCP_TOKEN"],
        approver_email=env["SRE_APPROVER_EMAIL"],
        approver_password=env["SRE_APPROVER_PASSWORD"],
        session_secret=env["SRE_SESSION_SECRET"],
        public_url=env["SRE_PUBLIC_URL"].rstrip("/"),
        chat_url=env["CHAT_PUBLIC_URL"].rstrip("/"),
        workshop_dir=Path(env["WORKSHOP_DIR"]),
        workshop_sql=Path(env.get("WORKSHOP_SQL", "/app/workshop")),
    )
