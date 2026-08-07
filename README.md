# k8s-pdb-auditor

Kubernetes PodDisruptionBudget auditor by Carlos Alejandro Perez Ceron.

PDB misconfiguration is the #1 cause of stalled node drains and cluster upgrade failures.
Most teams discover this the hard way -- during a production upgrade when kubectl drain hangs
indefinitely waiting for pods that can never be evicted.

k8s-pdb-auditor scans every namespace in your cluster, checks every Deployment and StatefulSet,
and surfaces PDB gaps before they block your next upgrade or on-call rotation.

## How it works

1. Connects to your cluster via kubeconfig context or in-cluster service account
2. Enumerates all Deployments, StatefulSets, DaemonSets, and PodDisruptionBudgets
3. Evaluates each workload against the PDB ruleset
4. Ranks findings by severity (CRITICAL -> HIGH -> MEDIUM -> LOW)
5. Outputs a rich terminal table, JSON, or CSV

## Quickstart

```bash
pip install -r requirements.txt

# Audit all namespaces
python main.py

# Audit specific namespace
python main.py --namespace production

# Skip system namespaces
python main.py --skip-system

# Only CRITICAL and HIGH
python main.py --min-severity HIGH

# JSON output
python main.py --output json --out-file pdb-findings.json
```

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Python      | 3.11+  |
| kubeconfig  | Valid context with get on pods, deployments, statefulsets, daemonsets, poddisruptionbudgets |
| RBAC        | ClusterRole with read access to pods, deployments, statefulsets, daemonsets, poddisruptionbudgets |

## CLI reference

| Flag                  | Default  | Description                               |
|-----------------------|----------|-------------------------------------------|
| --namespace TEXT      | all      | Audit a single namespace                  |
| --skip-system         | off      | Skip kube-system, kube-public, kube-node-lease |
| --min-severity TEXT   | LOW      | Minimum severity: LOW, MEDIUM, HIGH, CRITICAL |
| --output TEXT         | terminal | terminal, json, or csv                    |
| --out-file TEXT       | -        | Write output to file instead of stdout    |
| --context TEXT        | current  | kubeconfig context to use                 |

## Finding types

| Finding                  | Severity | Description                                                     |
|--------------------------|----------|-----------------------------------------------------------------|
| NO_PDB                   | HIGH     | Workload has replicas > 1 but no PDB covering it               |
| PDB_BLOCKS_ALL_EVICTIONS | CRITICAL | PDB prevents all pod evictions -- node drain will hang forever  |
| PDB_SELECTOR_MISMATCH    | HIGH     | PDB selector matches zero running pods -- budget is inactive    |
| SINGLE_REPLICA_WORKLOAD  | MEDIUM   | Workload runs with 1 replica -- any disruption means downtime   |
| PDB_ON_DAEMONSET         | LOW      | PDB targets a DaemonSet -- may block drain on single-pod nodes  |

## Sample output

```
k8s-pdb-auditor
Namespace     | Type        | Resource     | Severity | Finding
--------------------------------------------------------------------------------------------
production    | deployment  | payments-api | CRITICAL | PDB_BLOCKS_ALL_EVICTIONS
production    | statefulset | postgres     | HIGH     | NO_PDB
staging       | pdb         | old-pdb      | HIGH     | PDB_SELECTOR_MISMATCH
staging       | deployment  | worker       | MEDIUM   | SINGLE_REPLICA_WORKLOAD

Total: 4 findings  CRITICAL: 1  HIGH: 2  MEDIUM: 1
```

## Project structure

```
k8s-pdb-auditor/
|-- auditor/
|   |-- __init__.py
|   |-- base.py       # PdbFinding, AuditConfig dataclasses
|   |-- collector.py  # Fetches workloads and PDBs from cluster
|   `-- rules.py      # All finding rules
|-- tests/
|   |-- __init__.py
|   `-- test_auditor.py
|-- main.py           # CLI entrypoint
|-- report.py         # Terminal / JSON / CSV formatters
|-- requirements.txt
`-- .github/workflows/ci.yml
```

## License

MIT (c) Carlos Alejandro Perez Ceron
