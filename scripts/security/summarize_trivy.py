"""Group a saved Trivy JSON report into remediation families without suppressions."""

import argparse
import collections
import csv
import json
from pathlib import Path


def summarize(report):
    findings = []
    groups = collections.defaultdict(list)
    for result in report.get("Results") or []:
        # OS binary packages often share one source package and remediation.
        sources = {
            p.get("Name"): p.get("SrcName") or p.get("Name")
            for p in result.get("Packages") or []
        }
        for vulnerability in result.get("Vulnerabilities") or []:
            package = vulnerability["PkgName"]
            row = {
                "target": result.get("Target", ""),
                "type": result.get("Type", ""),
                "source": sources.get(package, package),
                "package": package,
                "installed": vulnerability.get("InstalledVersion", ""),
                "advisory": vulnerability["VulnerabilityID"],
                "severity": vulnerability.get("Severity", "UNKNOWN"),
                "listed_fix": vulnerability.get("FixedVersion", ""),
                "status": vulnerability.get("Status", ""),
                "url": vulnerability.get("PrimaryURL", ""),
            }
            findings.append(row)
            groups[(row["target"], row["type"], row["source"])].append(row)
    families = []
    for (target, ecosystem, source), rows in groups.items():
        families.append({
            "target": target,
            "type": ecosystem,
            "source": source,
            "packages": sorted({r["package"] for r in rows}),
            "occurrences": len(rows),
            "distinct_advisories": len({r["advisory"] for r in rows}),
            "severity": dict(collections.Counter(r["severity"] for r in rows)),
            "with_listed_fix": sum(bool(r["listed_fix"]) for r in rows),
            "action": "validate-supported-fix" if any(r["listed_fix"] for r in rows)
            else "assess-exposure-removal-or-mitigation",
        })
    families.sort(key=lambda g: (
        g["severity"].get("CRITICAL", 0), g["severity"].get("HIGH", 0),
        g["severity"].get("MEDIUM", 0), g["occurrences"]
    ), reverse=True)
    return {
        "artifact": report.get("ArtifactName"),
        "created": report.get("CreatedAt"),
        "scanner": report.get("Trivy"),
        "total_occurrences": len(findings),
        "distinct_advisories": len({r["advisory"] for r in findings}),
        "severity": dict(collections.Counter(r["severity"] for r in findings)),
        "with_listed_fix": sum(bool(r["listed_fix"]) for r in findings),
        "families": families,
    }, findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    summary, findings = summarize(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        columns = ["target", "type", "source", "package", "installed", "advisory",
                   "severity", "listed_fix", "status", "url"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(findings)
    print(json.dumps({k: v for k, v in summary.items() if k != "families"}, indent=2))
    for group in summary["families"][:12]:
        print(group["type"], group["source"], group["occurrences"],
              group["severity"], "listed fixes:", group["with_listed_fix"])


if __name__ == "__main__":
    main()
