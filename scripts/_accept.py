"""Portable acceptance policy: load + fail-closed validate `<repo>/.repo-audit/accept.json`.

The audit leaves detect everything by design; this module is consulted one layer up
(the wave's reporting stage and the MPRR engine's remediation stage) to mark findings
acceptable. A malformed policy is a hard error — never silently "accept nothing" or
"accept everything". See docs/superpowers/specs/2026-06-14-portable-acceptance-safeguard-design.md.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ACCEPT_RELPATH = Path(".repo-audit") / "accept.json"
_STAGES = frozenset({"report", "remediation"})
_KINDS = frozenset({"finding", "path", "rule"})


class AcceptError(ValueError):
    """Raised on any malformed acceptance policy (fail-closed)."""


@dataclass(frozen=True)
class AcceptEntry:
    kind: str
    fields: dict[str, str]
    reason: str
    applies: frozenset[str]
    expires: str | None

    def is_expired(self, today: date | None = None) -> bool:
        """True only for an ISO date in the past; non-date tokens never auto-expire."""
        if not self.expires:
            return False
        try:
            parsed = date.fromisoformat(self.expires)
        except ValueError:
            return False
        return parsed < (today or date.today())


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AcceptError(msg)


def _parse_entry(raw: Any, index: int) -> AcceptEntry:
    _require(isinstance(raw, dict), f"accept[{index}] must be an object")
    match = raw.get("match")
    _require(isinstance(match, dict), f"accept[{index}].match must be an object")
    kind = match.get("kind")
    _require(kind in _KINDS, f"accept[{index}].match.kind must be one of {sorted(_KINDS)}")
    reason = raw.get("reason")
    _require(isinstance(reason, str) and reason.strip(), f"accept[{index}].reason is required")

    applies_raw = raw.get("applies", ["report", "remediation"])
    _require(
        isinstance(applies_raw, list) and applies_raw,
        f"accept[{index}].applies must be a non-empty array",
    )
    _require(all(a in _STAGES for a in applies_raw),
             f"accept[{index}].applies values must be in {sorted(_STAGES)}")

    fields: dict[str, str] = {}
    for key in ("leaf", "path", "symbol", "metric", "glob"):
        if key in match:
            _require(isinstance(match[key], str), f"accept[{index}].match.{key} must be a string")
            fields[key] = match[key]

    if kind == "finding":
        missing = [k for k in ("leaf", "path", "symbol", "metric") if k not in fields]
        _require(not missing, f"accept[{index}] finding match missing {missing}")
    elif kind == "path":
        _require("glob" in fields, f"accept[{index}] path match needs 'glob'")
        _require(".." not in fields["glob"] and not fields["glob"].startswith("/"),
                 f"accept[{index}] glob must be repo-relative (no '..' or leading '/')")
    else:  # rule
        _require("leaf" in fields or "metric" in fields,
                 f"accept[{index}] rule match needs 'leaf' and/or 'metric'")

    expires = raw.get("expires")
    _require(
        expires is None or isinstance(expires, str),
        f"accept[{index}].expires must be string|null",
    )
    return AcceptEntry(kind, fields, reason, frozenset(applies_raw), expires)


def _parse_policy(payload: Any) -> list[AcceptEntry]:
    _require(isinstance(payload, dict), "accept policy must be a JSON object")
    _require(payload.get("version") == 1, "accept policy version must be 1")
    accept = payload.get("accept")
    _require(isinstance(accept, list), "accept policy 'accept' must be an array")
    return [_parse_entry(raw, i) for i, raw in enumerate(accept)]


class AcceptPolicy:
    """A validated set of acceptance entries with stage-scoped matching."""

    def __init__(self, entries: list[AcceptEntry]) -> None:
        self.entries = entries

    def merge(self, other: "AcceptPolicy") -> "AcceptPolicy":
        return AcceptPolicy(self.entries + other.entries)

    @staticmethod
    def _entry_matches(entry: AcceptEntry, finding: dict[str, Any]) -> bool:
        f = entry.fields
        if entry.kind == "finding":
            return all(str(finding.get(k, "")) == f[k]
                       for k in ("leaf", "path", "symbol", "metric"))
        if entry.kind == "path":
            glob = f["glob"]
            paths = [finding.get("path", "")] + list(finding.get("files", []) or [])
            return any(p and fnmatch.fnmatch(p, glob) for p in paths)
        # rule: every specified key must equal (AND), at least one is present
        return all(str(finding.get(k, "")) == v for k, v in f.items())

    def matches(self, finding: dict[str, Any], stage: str) -> AcceptEntry | None:
        for entry in self.entries:
            if stage in entry.applies and self._entry_matches(entry, finding):
                return entry
        return None

    def partition(
        self, findings: list[dict[str, Any]], stage: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        """→ (active, accepted, stale). Accepted carry reason + expired flag; stale =
        stage-scoped entries that matched nothing (described for the sidecar)."""
        stage_entries = [e for e in self.entries if stage in e.applies]
        matched: set[int] = set()
        active: list[dict[str, Any]] = []
        accepted: list[dict[str, Any]] = []
        for finding in findings:
            hit = None
            for i, entry in enumerate(stage_entries):
                if self._entry_matches(entry, finding):
                    hit = (i, entry)
                    break
            if hit is None:
                active.append(finding)
            else:
                i, entry = hit
                matched.add(i)
                accepted.append({**finding, "accepted": True,
                                 "accept_reason": entry.reason,
                                 "expired": entry.is_expired()})
        stale = [f"{e.kind}:{e.fields}" for i, e in enumerate(stage_entries)
                 if i not in matched]
        return active, accepted, stale


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AcceptError(f"{path} is invalid JSON: {exc}") from exc
    except OSError as exc:
        raise AcceptError(f"cannot read {path}: {exc}") from exc


def load_accept(repo: Path, extra: Path | None = None) -> AcceptPolicy:
    """Discover `<repo>/.repo-audit/accept.json` (+ optional --accept file), validated."""
    entries: list[AcceptEntry] = []
    in_repo = Path(repo) / ACCEPT_RELPATH
    if in_repo.exists():
        entries.extend(_parse_policy(_read_json(in_repo)))
    if extra is not None:
        entries.extend(_parse_policy(_read_json(Path(extra))))
    return AcceptPolicy(entries)


def from_baseline(rows: list[dict[str, str]]) -> AcceptPolicy:
    """Adapt a legacy flat --baseline array into report-stage finding acceptances."""
    entries = [
        AcceptEntry(
            "finding",
            {k: str(r.get(k, "")) for k in ("leaf", "path", "symbol", "metric")},
            "(legacy --baseline)",
            frozenset({"report"}),
            None,
        )
        for r in rows
    ]
    return AcceptPolicy(entries)
