from __future__ import annotations
import csv
import io
import json
from typing import List

from auditor.base import AuditConfig, PdbFinding

SEVERITY_COLOR = {
    "CRITICAL": "\033[91m",
    "HIGH": "\033[93m",
    "MEDIUM": "\033[94m",
    "LOW": "\033[92m",
}
RESET = "\033[0m"


def _plain_terminal(findings: List[PdbFinding], cfg: AuditConfig) -> None:
    if not findings:
        print("No findings above severity threshold. Cluster PDB posture looks good.")
        return
    sorted_findings = sorted(findings, key=lambda f: f.severity_order(), reverse=True)
    print(f"\n{'='*72}")
    print(f"  k8s-pdb-auditor  --  {len(findings)} finding(s)")
    print(f"{'='*72}\n")
    for i, f in enumerate(sorted_findings, 1):
        color = SEVERITY_COLOR.get(f.severity, "")
        print(f"[{i}] {color}{f.severity}{RESET}  {f.finding_type}")
        print(f"    Namespace : {f.namespace}")
        print(f"    Resource  : {f.resource_type}/{f.resource_name}")
        print(f"    Detail    : {f.description}")
        print(f"    Fix       : {f.recommendation}")
        print()


def _rich_terminal(findings: List[PdbFinding], cfg: AuditConfig) -> None:
    from rich.console import Console
    from rich.table import Table
    console = Console()
    if not findings:
        console.print("[bold green]No findings.[/] Cluster PDB posture looks good.")
        return
    table = Table(title=f"k8s-pdb-auditor -- {len(findings)} finding(s)", show_lines=True)
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Type", width=28)
    table.add_column("Namespace", width=18)
    table.add_column("Resource", width=22)
    table.add_column("Description")
    sev_style = {"CRITICAL": "red", "HIGH": "yellow", "MEDIUM": "blue", "LOW": "green"}
    for f in sorted(findings, key=lambda x: x.severity_order(), reverse=True):
        style = sev_style.get(f.severity, "")
        table.add_row(
            f"[{style}]{f.severity}[/{style}]",
            f.finding_type,
            f.namespace,
            f"{f.resource_type}/{f.resource_name}",
            f.description,
        )
    console.print(table)


def print_terminal(findings: List[PdbFinding], cfg: AuditConfig) -> None:
    try:
        import rich  # noqa: F401
        _rich_terminal(findings, cfg)
    except ImportError:
        _plain_terminal(findings, cfg)


def print_json(findings: List[PdbFinding]) -> None:
    print(json.dumps([f.to_dict() for f in findings], indent=2))


def write_csv(findings: List[PdbFinding], path: str) -> None:
    if not findings:
        return
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(findings[0].to_dict().keys()))
        writer.writeheader()
        for f in findings:
            writer.writerow(f.to_dict())
    print(f"CSV report written to {path}")
