"""薄壳五件：签名在、调用即明确报错（不返回假结果）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework import claim, invariants, land, ledger, trace
from framework.pending import PendingError


def test_ledger_check_raises():
    with pytest.raises(PendingError):
        ledger.check("ledger.toml")


def test_invariants_check_raises():
    with pytest.raises(PendingError):
        invariants.check("invariants.toml")


def test_claim_submit_raises():
    with pytest.raises(PendingError):
        claim.submit(task="X", member="M", status="success", files=[], why="", evidence="",
                     claims_dir=".pipe/claims")


def test_claim_collect_raises():
    with pytest.raises(PendingError):
        claim.collect(task="X", claims_dir=".pipe/claims")


def test_land_raises():
    with pytest.raises(PendingError):
        land.land(task="X", repo_root=Path("."), dry_run=True)


def test_land_reset_derived_raises():
    with pytest.raises(PendingError):
        land.reset_derived(repo_root=Path("."))


def test_trace_seal_raises():
    with pytest.raises(PendingError):
        trace.seal(repo_root=Path("."), reason="why")


def test_trace_emit_event_raises():
    with pytest.raises(PendingError):
        trace.emit_event(ndjson_path="e.ndjson", event={})
