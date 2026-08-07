from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
SYSTEM_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease"}


@dataclass
class PdbFinding:
    namespace: str
    resource_type: str   # deployment | statefulset | daemonset | pdb
    resource_name: str
    severity: str
    finding_type: str
    description: str
    recommendation: str

    def severity_order(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 0)

    def to_dict(self) -> dict:
        return {
            "namespace": self.namespace,
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "severity": self.severity,
            "finding_type": self.finding_type,
            "description": self.description,
            "recommendation": self.recommendation,
        }


@dataclass
class AuditConfig:
    namespace: Optional[str] = None
    skip_system: bool = False
    min_severity: str = "LOW"
    context: Optional[str] = None

    def min_severity_order(self) -> int:
        return SEVERITY_ORDER.get(self.min_severity, 0)

    def to_dict(self) -> dict:
        return {
            "namespace": self.namespace,
            "skip_system": self.skip_system,
            "min_severity": self.min_severity,
            "context": self.context,
        }
