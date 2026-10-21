"""Create the two workshop logins if they do not exist yet. Safe to run on every `make up`.

LibreChat: the AI SRE chat user, through LibreChat's own create-user command.
HyperDX: on a fresh stack the workshop user registers as the first account, which creates the
team, and the team's ingestion key is set to HYPERDX_API_KEY; otherwise it joins your existing
team through HyperDX's own invite acceptance endpoint.
Either way the password is hashed by HyperDX. Passwords are read from .env and
passed on stdin or in a request body, never as command arguments.
"""

import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_env import ENV, read  # noqa: E402


def sh(args: list[str], stdin: str | None = None) -> str:
    return subprocess.run(args, input=stdin, capture_output=True, text=True, check=True).stdout.strip()


def librechat_user(email: str, password: str) -> None:
    count = sh(["docker", "exec", "mongodb", "mongosh", "LibreChat", "--quiet", "--eval",
                f"db.users.countDocuments({{ email: {json.dumps(email)} }})"])  # fmt: skip
    if count != "0":
        print(f"LibreChat user {email} exists")
        return
    name = email.split("@")[0]
    sh(["docker", "exec", "-i", "librechat", "npm", "run", "create-user", "--", email, "AI SRE", name,
        "--email-verified=true"], stdin=f"{password}\n")  # fmt: skip
    print(f"LibreChat user {email} created")


def wait_for_ingest(api_key: str, timeout_s: int = 120) -> None:
    """The collector picks up a changed team key on its next config poll, and resets connections meanwhile."""
    deadline = time.monotonic() + timeout_s
    while True:
        request = urllib.request.Request(
            "http://localhost:4318/v1/logs", data=b'{"resourceLogs": []}', method="POST",
            headers={"authorization": api_key, "content-type": "application/json"},
        )  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 fixed http URL
                if response.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        if time.monotonic() > deadline:
            raise SystemExit(f"The collector did not accept HYPERDX_API_KEY within {timeout_s} s")
        time.sleep(2)


def hyperdx_user(email: str, password: str, api_key: str) -> None:
    mongo = ["docker", "exec", "clickstack", "mongo", "--quiet", "hyperdx", "--eval"]
    if sh([*mongo, f"db.users.count({{ email: {json.dumps(email)} }})"]) != "0":
        print(f"HyperDX user {email} exists")
        return
    if sh([*mongo, "db.teams.count()"]) == "0":
        # Posted from inside the container to the HyperDX API port, so it works where 8080 is not published.
        status = sh(
            ["docker", "exec", "-i", "clickstack", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "-H", "Content-Type: application/json", "--data-binary", "@-", "http://localhost:8000/register/password"],
            stdin=json.dumps({"email": email, "password": password, "confirmPassword": password}),
        )  # fmt: skip
        if status != "200":
            raise SystemExit(f"HyperDX refused to register the workshop user (HTTP {status})")
        # The new team gets a random ingestion key; the collector and every app already send the one in .env.
        sh(["docker", "exec", "-i", "clickstack", "mongo", "--quiet", "hyperdx"],
           stdin=f"db.teams.updateOne({{}}, {{ $set: {{ apiKey: {json.dumps(api_key)} }} }});\n")  # fmt: skip
        wait_for_ingest(api_key)
        print(f"HyperDX user {email} created with a new team that accepts HYPERDX_API_KEY")
        return
    token = secrets.token_hex(32)
    sh([*mongo, f"""var team = db.teams.findOne();
        db.teaminvites.insertOne({{ teamId: team._id, email: {json.dumps(email)}, token: '{token}',
                                   createdAt: new Date(), updatedAt: new Date() }});"""])  # fmt: skip
    location = sh(
        ["docker", "exec", "-i", "clickstack", "curl", "-s", "-o", "/dev/null", "-w", "%{redirect_url}",
         "--data-binary", "@-", f"http://localhost:8000/team/setup/{token}"],
        stdin=urllib.parse.urlencode({"password": password}),
    )  # fmt: skip
    if "err=" in location:
        raise SystemExit(f"HyperDX refused the workshop user: {location}")
    if sh([*mongo, f"db.users.count({{ email: {json.dumps(email)} }})"]) != "1":
        raise SystemExit("HyperDX did not create the workshop user")
    print(f"HyperDX user {email} created in your team")


def main() -> None:
    env = read(ENV)
    librechat_user(env["LIBRECHAT_USER_EMAIL"], env["LIBRECHAT_USER_PASSWORD"])
    hyperdx_user(env["HYPERDX_USER_EMAIL"], env["HYPERDX_USER_PASSWORD"], env["HYPERDX_API_KEY"])


if __name__ == "__main__":
    main()
