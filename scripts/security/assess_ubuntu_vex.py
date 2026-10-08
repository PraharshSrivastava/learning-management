"""Keep inherited risks visible across an OS migration using official VEX.

Run on a machine with dpkg. This is an assessment register, not a scanner ignore
file. Unknown, missing, deferred and ignored issues remain open. Custom builds
need a separate upstream/code-presence assessment and are not closed by VEX.
"""

import argparse
import collections
import csv
import hashlib
import json
import subprocess
import urllib.parse
from pathlib import Path

from summarize_trivy import summarize


def parse_product(value):
    if not value.startswith("pkg:deb/ubuntu/"):
        return None
    path, _, query = value.partition("?")
    name_version = path.removeprefix("pkg:deb/ubuntu/")
    name, sep, version = name_version.partition("@")
    qualifiers = urllib.parse.parse_qs(query)
    if qualifiers.get("distro") != ["resolute"] or qualifiers.get("arch") != ["source"]:
        return None
    return urllib.parse.unquote(name), urllib.parse.unquote(version) if sep else ""


def ge(installed, fixed):
    if not fixed:
        return False
    result = subprocess.run(["dpkg", "--compare-versions", installed, "ge", fixed], check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError("Debian version comparison failed")
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("native_inventory", type=Path)
    parser.add_argument("vex_directory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    old_report = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    new_report = json.loads(args.candidate.read_text(encoding="utf-8-sig"))
    if new_report.get("Metadata", {}).get("OS") != {"Family": "ubuntu", "Name": "26.04"}:
        parser.error("This assessment requires detected Ubuntu 26.04 packages.")
    _, old_rows = summarize(old_report)
    _, new_rows = summarize(new_report)
    new_keys = {(r["source"], r["advisory"]): r for r in new_rows}
    inventory = json.loads(args.native_inventory.read_text())
    sources = collections.defaultdict(set)
    for package in inventory["packages"]:
        if package["source"] and package["source_version"]:
            sources[package["source"]].add(package["source_version"])
    index = json.loads((args.vex_directory / "index.json").read_text())
    files = {r["cve"]: r for r in index["rows"]}
    rows = []
    for original in old_rows:
        family, cve = original["source"], original["advisory"]
        record = files.get(cve)
        row = {**original, "candidate_source_versions": ";".join(sorted(sources[family])),
               "candidate_reported_severity": new_keys.get((family, cve), {}).get("severity", ""),
               "assessment": "OPEN_MISSING_VENDOR_EVIDENCE", "vendor_status": "",
               "evidence_url": record["url"] if record else "", "vendor_product": "",
               "notes": "No applicable vendor statement; missing matches are not fixes."}
        if record and record["state"] == "downloaded":
            path = args.vex_directory / f"{cve}.json"
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != record["sha256"]:
                raise ValueError(f"VEX evidence hash mismatch: {cve}")
            document = json.loads(raw)
            matches = [(statement, product["@id"], parsed[1])
                       for statement in document["statements"]
                       for product in statement.get("products") or []
                       if (parsed := parse_product(product["@id"])) and parsed[0] == family]
            # A conflict or duplicate is kept open for human review.
            if len(matches) == 1:
                statement, product, fixed = matches[0]
                status = statement["status"]
                row.update(vendor_status=status, vendor_product=product,
                           notes=statement.get("status_notes") or statement.get("impact_statement")
                           or statement.get("action_statement") or "")
                versions = sources[family]
                if not versions:
                    row.update(assessment="OPEN_SOURCE_ABSENT_BUNDLE_REVIEW",
                               notes="Source package absent; separately check bundled/native components.")
                elif status == "fixed" and all(ge(v, fixed) for v in versions):
                    row["assessment"] = "VENDOR_FIXED_VERSION_CONFIRMED"
                elif status == "not_affected" and versions == {fixed} and statement.get("justification") == "vulnerable_code_not_present":
                    row["assessment"] = "VENDOR_NOT_AFFECTED_EXACT_VERSION"
                else:
                    row["assessment"] = "OPEN_" + status.upper()
            elif len(matches) > 1:
                row.update(assessment="OPEN_CONFLICTING_VENDOR_STATEMENTS",
                           notes="Multiple source statements need manual assessment.")
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {"candidate_image": new_report["Metadata"]["ImageID"],
               "vex_commit": index["upstream_commit"], "inherited_occurrences": len(rows),
               "assessments": dict(collections.Counter(r["assessment"] for r in rows)),
               "open_original_severity": dict(collections.Counter(r["severity"] for r in rows
                                                                    if r["assessment"].startswith("OPEN_"))),
               "limitation": "Custom libraries require separate upstream evidence. Vendor-fixed/not-affected "
                             "are assessment outcomes, not comparable raw scanner reductions."}
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
