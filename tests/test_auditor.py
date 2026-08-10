"""Unit tests for k8s-pdb-auditor -- no cluster required."""
from unittest.mock import MagicMock

import pytest

from auditor.base import AuditConfig, PdbFinding, SEVERITY_ORDER
from auditor.rules import (
    evaluate_namespace,
    _labels_match,
    _pdb_blocks_all,
)


# ---------------------------------------------------------------------------
# Helpers to build fake k8s objects
# ---------------------------------------------------------------------------

def _make_dep(name: str, replicas: int, labels: dict) -> MagicMock:
    dep = MagicMock()
    dep.metadata.name = name
    dep.spec.replicas = replicas
    dep.spec.selector.match_labels = labels
    return dep


def _make_sts(name: str, replicas: int, labels: dict) -> MagicMock:
    sts = MagicMock()
    sts.metadata.name = name
    sts.spec.replicas = replicas
    sts.spec.selector.match_labels = labels
    return sts


def _make_ds(name: str, labels: dict) -> MagicMock:
    ds = MagicMock()
    ds.metadata.name = name
    ds.spec.selector.match_labels = labels
    return ds


def _make_pdb(name: str, selector: dict, max_unavailable=None, min_available=None) -> MagicMock:
    pdb = MagicMock()
    pdb.metadata.name = name
    pdb.spec.selector.match_labels = selector
    pdb.spec.max_unavailable = max_unavailable
    pdb.spec.min_available = min_available
    return pdb


def _make_pod(labels: dict) -> MagicMock:
    pod = MagicMock()
    pod.metadata.labels = labels
    pod.status.phase = "Running"
    return pod


def _cfg(**kwargs) -> AuditConfig:
    return AuditConfig(**kwargs)


# ---------------------------------------------------------------------------
# Unit tests: _labels_match
# ---------------------------------------------------------------------------

def test_labels_match_exact():
    assert _labels_match({"app": "web", "env": "prod"}, {"app": "web"}) is True


def test_labels_match_empty_selector():
    assert _labels_match({}, {}) is True


def test_labels_match_miss():
    assert _labels_match({"app": "web"}, {"app": "api"}) is False


# ---------------------------------------------------------------------------
# Unit tests: _pdb_blocks_all
# ---------------------------------------------------------------------------

def test_pdb_blocks_max_unavailable_zero():
    pdb = _make_pdb("p", {}, max_unavailable=0)
    assert _pdb_blocks_all(pdb, 3) is True


def test_pdb_blocks_max_unavailable_zero_str():
    pdb = _make_pdb("p", {}, max_unavailable="0%")
    assert _pdb_blocks_all(pdb, 3) is True


def test_pdb_blocks_min_available_equals_replicas():
    pdb = _make_pdb("p", {}, min_available=3)
    assert _pdb_blocks_all(pdb, 3) is True


def test_pdb_blocks_min_available_100pct():
    pdb = _make_pdb("p", {}, min_available="100%")
    assert _pdb_blocks_all(pdb, 5) is True


def test_pdb_does_not_block():
    pdb = _make_pdb("p", {}, max_unavailable=1)
    assert _pdb_blocks_all(pdb, 3) is False


# ---------------------------------------------------------------------------
# Integration tests: evaluate_namespace
# ---------------------------------------------------------------------------

cfg = _cfg()


def test_no_pdb_finding():
    dep = _make_dep("api", 3, {"app": "api"})
    findings = evaluate_namespace("default", [dep], [], [], [], [], cfg)
    types = [f.finding_type for f in findings]
    assert "NO_PDB" in types
    sev = next(f.severity for f in findings if f.finding_type == "NO_PDB")
    assert sev == "HIGH"


def test_single_replica_finding():
    dep = _make_dep("solo", 1, {"app": "solo"})
    findings = evaluate_namespace("default", [dep], [], [], [], [], cfg)
    types = [f.finding_type for f in findings]
    assert "SINGLE_REPLICA_WORKLOAD" in types


def test_pdb_blocks_all_critical():
    dep = _make_dep("api", 3, {"app": "api"})
    pdb = _make_pdb("api-pdb", {"app": "api"}, max_unavailable=0)
    findings = evaluate_namespace("default", [dep], [], [], [pdb], [], cfg)
    criticals = [f for f in findings if f.severity == "CRITICAL"]
    assert len(criticals) >= 1
    assert criticals[0].finding_type == "PDB_BLOCKS_ALL_EVICTIONS"


def test_orphaned_pdb():
    pdb = _make_pdb("ghost-pdb", {"app": "ghost"})
    findings = evaluate_namespace("default", [], [], [], [pdb], [], cfg)
    types = [f.finding_type for f in findings]
    assert "PDB_SELECTOR_MISMATCH" in types


def test_pdb_on_daemonset():
    ds = _make_ds("node-agent", {"app": "node-agent"})
    pdb = _make_pdb("ds-pdb", {"app": "node-agent"})
    findings = evaluate_namespace("default", [], [], [ds], [pdb], [], cfg)
    types = [f.finding_type for f in findings]
    assert "PDB_ON_DAEMONSET" in types


def test_min_severity_filter():
    dep = _make_dep("api", 1, {"app": "api"})
    cfg_high = _cfg(min_severity="HIGH")
    findings = evaluate_namespace("default", [dep], [], [], [], [], cfg_high)
    assert all(f.severity in ("HIGH", "CRITICAL") for f in findings)


def test_severity_order():
    assert SEVERITY_ORDER["CRITICAL"] > SEVERITY_ORDER["HIGH"]
    assert SEVERITY_ORDER["HIGH"] > SEVERITY_ORDER["MEDIUM"]
    assert SEVERITY_ORDER["MEDIUM"] > SEVERITY_ORDER["LOW"]


def test_finding_to_dict():
    f = PdbFinding(
        namespace="default",
        resource_type="deployment",
        resource_name="api",
        severity="HIGH",
        finding_type="NO_PDB",
        description="desc",
        recommendation="rec",
    )
    d = f.to_dict()
    assert d["namespace"] == "default"
    assert d["severity"] == "HIGH"
