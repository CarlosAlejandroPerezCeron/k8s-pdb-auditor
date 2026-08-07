from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

from kubernetes import client, config

from auditor.base import AuditConfig, SYSTEM_NAMESPACES


@dataclass
class ClusterData:
    namespaces: List[Any] = field(default_factory=list)
    deployments: Dict[str, List[Any]] = field(default_factory=dict)   # ns -> deployments
    statefulsets: Dict[str, List[Any]] = field(default_factory=dict)  # ns -> statefulsets
    daemonsets: Dict[str, List[Any]] = field(default_factory=dict)    # ns -> daemonsets
    pdbs: Dict[str, List[Any]] = field(default_factory=dict)          # ns -> PDBs
    pods: Dict[str, List[Any]] = field(default_factory=dict)          # ns -> pods


def collect(cfg: AuditConfig) -> ClusterData:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config(context=cfg.context)

    core = client.CoreV1Api()
    apps = client.AppsV1Api()
    policy = client.PolicyV1Api()

    data = ClusterData()

    if cfg.namespace:
        ns_names = [cfg.namespace]
    else:
        all_ns = core.list_namespace().items
        ns_names = [ns.metadata.name for ns in all_ns]
        if cfg.skip_system:
            ns_names = [n for n in ns_names if n not in SYSTEM_NAMESPACES]

    for ns in ns_names:
        data.namespaces.append(ns)
        data.deployments[ns] = apps.list_namespaced_deployment(ns).items
        data.statefulsets[ns] = apps.list_namespaced_stateful_set(ns).items
        data.daemonsets[ns] = apps.list_namespaced_daemon_set(ns).items
        data.pdbs[ns] = policy.list_namespaced_pod_disruption_budget(ns).items
        data.pods[ns] = [
            p for p in core.list_namespaced_pod(ns).items
            if p.status and p.status.phase == "Running"
        ]

    return data
