"""Compare saved reports by ecosystem, package, and advisory; does not assert exploitability."""

import argparse
import collections
import json
from pathlib import Path


def load(path):
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = [dict(v, ecosystem=result.get("Type", ""))
            for result in report.get("Results") or []
            for v in result.get("Vulnerabilities") or []]
    keys = collections.Counter((r["ecosystem"], r["PkgName"], r["VulnerabilityID"])
                               for r in rows)
    counts = dict(collections.Counter(r.get("Severity", "UNKNOWN") for r in rows))
    return report, keys, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    before, old_keys, old_counts = load(args.before)
    after, new_keys, new_counts = load(args.after)
    old_os = (before.get("Metadata", {}).get("OS") or {}).get("Family")
    new_os = (after.get("Metadata", {}).get("OS") or {}).get("Family")
    if old_os and new_os and old_os != new_os:
        parser.error(
            "OS families differ; package keys and vendor severity/coverage are not "
            "comparable. Review inherited CVEs against the replacement versions "
            "instead of counting every missing vendor match as fixed."
        )
    removed = list((old_keys - new_keys).elements())
    added = list((new_keys - old_keys).elements())
    result = {
        "before_artifact": before.get("ArtifactName"),
        "after_artifact": after.get("ArtifactName"),
        "before_severity": old_counts, "after_severity": new_counts,
        "removed_occurrences": len(removed), "added_occurrences": len(added),
        "removed": removed, "added": added,
        "limitation": "Equivalent scanner settings/database must be verified separately. "
                      "Keys omit target paths; separate component reports should be compared.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("removed", "added")}, indent=2))


if __name__ == "__main__":
    main()
