"""Query OSV for exact hosted Pub versions; SDK/git/path packages remain coverage gaps.

Requires PyYAML (available in the backend development environment).
Only public hosted package names and versions are sent to the OSV API.
"""

import argparse
import datetime
import json
import urllib.request
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locks", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inventory = []
    gaps = []
    for lock in args.locks:
        for name, package in yaml.safe_load(lock.read_text(encoding="utf-8"))["packages"].items():
            row = {"lock": str(lock), "name": name, "version": package["version"],
                   "source": package["source"]}
            description = package.get("description")
            url = description.get("url", "") if isinstance(description, dict) else ""
            if package["source"] == "hosted" and url in (
                "https://pub.dev", "https://pub.dartlang.org"
            ):
                inventory.append(row)
            else:
                gaps.append(row)
    versions = sorted({(row["name"], row["version"]) for row in inventory})
    queries = [{"package": {"ecosystem": "Pub", "name": name}, "version": version}
               for name, version in versions]
    request = urllib.request.Request(
        "https://api.osv.dev/v1/querybatch",
        data=json.dumps({"queries": queries}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = json.load(response)
    results = raw["results"]
    if len(results) != len(versions):
        raise RuntimeError("OSV response does not match the query count")
    # Fail rather than treat incomplete/paginated data as a clean result.
    if any(result.get("next_page_token") for result in results):
        raise RuntimeError("OSV pagination requires further queries")
    findings = [dict(name=name, version=version, advisories=result["vulns"])
                for (name, version), result in zip(versions, results) if result.get("vulns")]
    summary = {"queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "endpoint": "https://api.osv.dev/v1/querybatch", "ecosystem": "Pub",
               "unique_hosted_versions_queried": len(versions),
               "inventory": inventory, "coverage_gaps": gaps, "findings": findings,
               "queries": queries, "response": raw}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "queried_at", "unique_hosted_versions_queried", "findings", "coverage_gaps"
    )}, indent=2))


if __name__ == "__main__":
    main()
