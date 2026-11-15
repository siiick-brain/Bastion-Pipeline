"""Triggers the bastion-pipeline job on the local Jenkins and prints each stage result.

Usage: python infra/jenkins/run_job.py [--url http://127.0.0.1:8080] [--timeout 1200]
Reads the admin password from infra/jenkins/secrets/admin_password. Exit 0 when the build
result is SUCCESS, 1 otherwise. Never prints the password.
"""

from __future__ import annotations

import argparse
import base64
import http.cookiejar
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--job", default="bastion-pipeline")
    ap.add_argument("--timeout", type=int, default=1200)
    args = ap.parse_args(argv)
    if not args.url.startswith("http://127.0.0.1"):
        print("refusing a non-local Jenkins URL", file=sys.stderr)
        return 2

    password = (HERE / "secrets/admin_password").read_text().strip()
    auth = "Basic " + base64.b64encode(f"admin:{password}".encode()).decode()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def call(path: str, method: str = "GET", headers: dict[str, str] | None = None) -> bytes:
        req = urllib.request.Request(  # noqa: S310 - local URL checked above
            args.url + path, method=method, headers={"Authorization": auth, **(headers or {})}
        )
        with opener.open(req, timeout=30) as resp:
            body: bytes = resp.read()
            return body

    crumb = json.loads(call("/crumbIssuer/api/json"))
    last = json.loads(call(f"/job/{args.job}/api/json?tree=lastBuild[number]"))["lastBuild"]
    previous = last["number"] if last else 0
    call(f"/job/{args.job}/build", "POST", {crumb["crumbRequestField"]: crumb["crumb"]})

    deadline = time.monotonic() + args.timeout
    build = None
    while time.monotonic() < deadline:
        time.sleep(5)
        info = json.loads(call(f"/job/{args.job}/api/json?tree=lastBuild[number,building,result]"))
        b = info.get("lastBuild")
        if b and b["number"] > previous and not b["building"]:
            build = b
            break
    if build is None:
        print("timed out waiting for the build")
        return 1

    n = build["number"]
    log = call(f"/job/{args.job}/{n}/consoleText").decode(errors="replace")
    print(f"Build #{n}: {build['result']}")
    for line in log.splitlines():
        if line.startswith("[Pipeline] { (") or 'Stage "' in line:
            print("  stage:", line.split("(", 1)[-1].rstrip(")").strip())
    if build["result"] != "SUCCESS":
        print("--- last 40 log lines ---")
        print("\n".join(log.splitlines()[-40:]))
    return 0 if build["result"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
