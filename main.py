#!/usr/bin/env python3
"""k8s-pdb-auditor: Kubernetes PodDisruptionBudget auditor."""
import argparse
import sys

from auditor.base import AuditConfig
from auditor.collector import collect
from auditor.rules import evaluate_namespace
from report import print_terminal, print_json, write_csv


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="k8s-pdb-auditor",
        description="Audit PodDisruptionBudgets in a Kubernetes cluster.",
    )
    p.add_argument("-n", "--namespace", help="Audit a single namespace (default: all)")
    p.add_argument("--skip-system", action="store_true", help="Skip kube-system and related namespaces")
    p.add_argument("--min-severity", default="LOW", choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                   help="Minimum severity to report (default: LOW)")
    p.add_argument("--context", help="kubeconfig context to use")
    p.add_argument("--output", default="terminal", choices=["terminal", "json", "csv"],
                   help="Output format (default: terminal)")
    p.add_argument("--csv-path", default="pdb-audit.csv", help="CSV output path (default: pdb-audit.csv)")
    p.add_argument("--fail-on-critical", action="store_true",
                   help="Exit with code 1 if any CRITICAL findings are found")
    return p


def main() -> None:
    args = build_parser().parse_args()
    cfg = AuditConfig(
        namespace=args.namespace,
        skip_system=args.skip_system,
        min_severity=args.min_severity,
        context=args.context,
    )

    print("Collecting cluster data...", file=sys.stderr)
    data = collect(cfg)

    all_findings = []
    for ns in data.namespaces:
        ns_findings = evaluate_namespace(
            ns=ns,
            deployments=data.deployments.get(ns, []),
            statefulsets=data.statefulsets.get(ns, []),
            daemonsets=data.daemonsets.get(ns, []),
            pdbs=data.pdbs.get(ns, []),
            pods=data.pods.get(ns, []),
            cfg=cfg,
        )
        all_findings.extend(ns_findings)

    all_findings.sort(key=lambda f: f.severity_order(), reverse=True)

    if args.output == "json":
        print_json(all_findings)
    elif args.output == "csv":
        write_csv(all_findings, args.csv_path)
    else:
        print_terminal(all_findings, cfg)

    if args.fail_on_critical:
        has_critical = any(f.severity == "CRITICAL" for f in all_findings)
        if has_critical:
            sys.exit(1)


if __name__ == "__main__":
    main()
