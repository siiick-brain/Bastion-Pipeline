"""Loads and validates security/exceptions.toml. Expired or incomplete entries are errors."""

from __future__ import annotations

import datetime as dt
import tomllib
from dataclasses import dataclass
from pathlib import Path

REQUIRED = ("id", "finding", "scope", "reason", "risk", "owner", "expires")


class ExceptionRegisterError(ValueError):
    """The register is malformed, incomplete or contains an expired entry."""


@dataclass(frozen=True)
class Exception_:
    id: str
    finding: str
    scope: str
    reason: str
    risk: str
    owner: str
    expires: dt.date
    compensating: str = ""

    def covers(self, finding_id: str) -> bool:
        return self.finding.split(" ")[0] == finding_id


def load(path: Path, today: dt.date | None = None) -> list[Exception_]:
    today = today or dt.datetime.now(dt.UTC).date()
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    entries = data.get("exception", [])
    if not isinstance(entries, list):
        raise ExceptionRegisterError("'exception' must be an array of tables")
    result: list[Exception_] = []
    seen: set[str] = set()
    for raw in entries:
        missing = [k for k in REQUIRED if not str(raw.get(k, "")).strip()]
        if missing:
            raise ExceptionRegisterError(f"{raw.get('id', '?')}: missing {', '.join(missing)}")
        if raw["id"] in seen:
            raise ExceptionRegisterError(f"duplicate id {raw['id']}")
        seen.add(raw["id"])
        try:
            expires = dt.date.fromisoformat(str(raw["expires"]))
        except ValueError as exc:
            raise ExceptionRegisterError(f"{raw['id']}: invalid expires date") from exc
        if expires < today:
            raise ExceptionRegisterError(f"{raw['id']}: expired on {expires.isoformat()}")
        if (expires - today).days > 366:
            raise ExceptionRegisterError(f"{raw['id']}: expiry more than one year ahead")
        result.append(
            Exception_(
                id=raw["id"],
                finding=raw["finding"],
                scope=raw["scope"],
                reason=raw["reason"],
                risk=raw["risk"],
                owner=raw["owner"],
                expires=expires,
                compensating=raw.get("compensating", ""),
            )
        )
    return result
