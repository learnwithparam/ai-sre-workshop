"""Create the two workshop logins if they do not exist yet. Safe to run on every `make up`.

LibreChat: the AI SRE chat user, through LibreChat's own create-user command.
HyperDX: a workshop member of your existing HyperDX team, through HyperDX's own invite
acceptance endpoint, so the password is hashed by HyperDX. Passwords are read from .env and
passed on stdin or in a request body, never as command arguments.
"""

import json
import secrets
import subprocess
import sys
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


def hyperdx_user(email: str, password: str) -> None:
    mongo = ["docker", "exec", "clickstack", "mongo", "--quiet", "hyperdx", "--eval"]
    if sh([*mongo, f"db.users.count({{ email: {json.dumps(email)} }})"]) != "0":
        print(f"HyperDX user {email} exists")
        return
    token = secrets.token_hex(32)
    sh([*mongo, f"""var team = db.teams.findOne();
        if (!team) {{ throw new Error('Sign up in HyperDX at http://localhost:8080 first'); }}
        db.teaminvites.insertOne({{ teamId: team._id, email: {json.dumps(email)}, token: '{token}',
                                   createdAt: new Date(), updatedAt: new Date() }});"""])  # fmt: skip
    # Posted from inside the container to the HyperDX API port, so it works where 8080 is not published.
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
    hyperdx_user(env["HYPERDX_USER_EMAIL"], env["HYPERDX_USER_PASSWORD"])


if __name__ == "__main__":
    main()
