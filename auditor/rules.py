from __future__ import annotations
from typing import Any, Dict, List, Optional

from auditor.base import AuditConfig, PdbFinding


def _labels_match(pod_labels: dict, selector: dict) -> bool:
    """Return True if pod_labels satisfy all selector key-value pairs."""
    if not selector:
        return True
    for k, v in selector.items():
        if pod_labels.get(k) != v:
            return False
    return True


def _pdb_selector(pdb) -> dict:
    sel = pdb.spec.selector
    if sel and sel.match_labels:
        return dict(sel.match_labels)
    return {}


def _pods_selected_by_pdb(pdb, pods: List[Any]) -> List[Any]:
    sel = _pdb_selector(pdb)
    return [
        p for p in pods
        if _labels_match(dict(p.metadata.labels or {}), sel)
    ]


def _pdb_covers_workload(workload, pdbs: List[Any]) -> Optional[Any]:
    """Return the first PDB whose selector overlaps workload pod template labels."""
    wl_labels = {}
    if hasattr(workload.spec, "selector") and workload.spec.selector:
        wl_labels = dict(workload.spec.selector.match_labels or {})

    for pdb in pdbs:
        pdb_sel = _pdb_selector(pdb)
        if not pdb_sel:
            # Empty selector catches everything
            return pdb
        # Overlap: every pdb key must be in wl_labels with matching value
        if all(wl_labels.get(k) == v for k, v in pdb_sel.items()):
            return pdb
    return None


def _desired_replicas(workload) -> int:
    spec = workload.spec
    if hasattr(spec, "replicas") and spec.replicas is not None:
        return spec.replicas
    return 1


def _pdb_blocks_all(pdb, replicas: int) -> bool:
    """True if the PDB prevents ANY pod from being evicted."""
    spec = pdb.spec
    # maxUnavailable == 0 blocks all evictions
    if spec.max_unavailable is not None:
        val = spec.max_unavailable
        if isinstance(val, int) and val == 0:
            return True
        if isinstance(val, str) and val in ("0", "0%"):
            return True
    # minAvailable == replicas also blocks all evictions
    if spec.min_available is not None:
        val = spec.min_available
        if isinstance(val, int) and val >= replicas:
            return True
        if isinstance(val, str) and val == "100%":
            return True
    return False


def evaluate_namespace(
    ns: str,
    deployments: List[Any],
    statefulsets: List[Any],
    daemonsets: List[Any],
    pdbs: List[Any],
    pods: List[Any],
    cfg: AuditConfig,
) -> List[PdbFinding]:
    findings: List[PdbFinding] = []

    # -- Deployments --
    for dep in deployments:
        name = dep.metadata.name
        replicas = _desired_replicas(dep)
        pdb = _pdb_covers_workload(dep, pdbs)

        if replicas == 1:
            findings.append(PdbFinding(
                namespace=ns,
                resource_type="deployment",
                resource_name=name,
                severity="MEDIUM",
                finding_type="SINGLE_REPLICA_WORKLOAD",
                description=f"Deployment '{name}' runs with 1 replica. No redundancy; any disruption causes downtime.",
                recommendation="Increase replicas to >= 2 and add a PodDisruptionBudget.",
            ))
            continue

        if pdb is None:
            findings.append(PdbFinding(
                namespace=ns,
                resource_type="deployment",
                resource_name=name,
                severity="HIGH",
                finding_type="NO_PDB",
                description=f"Deployment '{name}' has {replicas} replicas but no PodDisruptionBudget.",
                recommendation="Add a PDB with minAvailable or maxUnavailable to protect this workload during node drain.",
            ))
        else:
            if _pdb_blocks_all(pdb, replicas):
                findings.append(PdbFinding(
                    namespace=ns,
                    resource_type="deployment",
                    resource_name=name,
                    severity="CRITICAL",
                    finding_type="PDB_BLOCKS_ALL_EVICTIONS",
                    description=(
                        f"Deployment '{name}' PDB '{pdb.metadata.name}' blocks ALL evictions "
                        f"(maxUnavailable=0 or minAvailable>={replicas}). Node drain will hang indefinitely."
                    ),
                    recommendation="Set maxUnavailable >= 1 or minAvailable < replicas so at least one pod can be evicted.",
                ))

    # -- StatefulSets --
    for sts in statefulsets:
        name = sts.metadata.name
        replicas = _desired_replicas(sts)
        pdb = _pdb_covers_workload(sts, pdbs)

        if replicas == 1:
            findings.append(PdbFinding(
                namespace=ns,
                resource_type="statefulset",
                resource_name=name,
                severity="MEDIUM",
                finding_type="SINGLE_REPLICA_WORKLOAD",
                description=f"StatefulSet '{name}' runs with 1 replica. Any disruption causes full downtime.",
                recommendation="Increase replicas to >= 2 and add a PodDisruptionBudget.",
            ))
            continue

        if pdb is None:
            findings.append(PdbFinding(
                namespace=ns,
                resource_type="statefulset",
                resource_name=name,
                severity="HIGH",
                finding_type="NO_PDB",
                description=f"StatefulSet '{name}' has {replicas} replicas but no PodDisruptionBudget.",
                recommendation="Add a PDB to protect this stateful workload during voluntary disruptions.",
            ))
        else:
            if _pdb_blocks_all(pdb, replicas):
                findings.append(PdbFinding(
                    namespace=ns,
                    resource_type="statefulset",
                    resource_name=name,
                    severity="CRITICAL",
                    finding_type="PDB_BLOCKS_ALL_EVICTIONS",
                    description=(
                        f"StatefulSet '{name}' PDB '{pdb.metadata.name}' blocks ALL evictions. "
                        f"Node drain will hang indefinitely."
                    ),
                    recommendation="Set maxUnavailable >= 1 or minAvailable < replicas.",
                ))

    # -- DaemonSets --
    for ds in daemonsets:
        name = ds.metadata.name
        pdb = _pdb_covers_workload(ds, pdbs)
        if pdb is not None:
            findings.append(PdbFinding(
                namespace=ns,
                resource_type="daemonset",
                resource_name=name,
                severity="LOW",
                finding_type="PDB_ON_DAEMONSET",
                description=f"DaemonSet '{name}' has PDB '{pdb.metadata.name}'. PDBs on DaemonSets may block node drain.",
                recommendation="Remove the PDB from DaemonSets or ensure maxUnavailable >= 1 to allow drains.",
            ))

    # -- Orphaned PDBs (selector matches zero running pods) --
    for pdb in pdbs:
        selected = _pods_selected_by_pdb(pdb, pods)
        if not selected:
            findings.append(PdbFinding(
                namespace=ns,
                resource_type="pdb",
                resource_name=pdb.metadata.name,
                severity="HIGH",
                finding_type="PDB_SELECTOR_MISMATCH",
                description=f"PDB '{pdb.metadata.name}' selector matches zero running pods. It may be orphaned.",
                recommendation="Verify the PDB selector matches the intended workload labels, or delete the orphaned PDB.",
            ))

    # Apply min severity filter
    min_order = cfg.min_severity_order()
    findings = [f for f in findings if f.severity_order() >= min_order]

    return findings
