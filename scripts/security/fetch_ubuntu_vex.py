"""Fetch official Canonical VEX evidence for CVEs in a saved report.

Public CVE identifiers are the only report data sent to the service. This does
not suppress findings or decide that a missing record means a vulnerability is
fixed. All files in one batch use the same upstream Git commit.
"""

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


def request(url):
    req = urllib.request.Request(url, headers={"User-Agent": "LMS-SBOM-review/1"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory; existing evidence is preserved.")
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    ids = sorted({v["VulnerabilityID"] for r in report.get("Results") or []
                  for v in r.get("Vulnerabilities") or []})
    excluded = [cve for cve in ids if not re.fullmatch(r"CVE-\d{4}-\d+", cve)]
    ids = [cve for cve in ids if re.fullmatch(r"CVE-\d{4}-\d+", cve)]
    if not ids:
        parser.error("Report has no public CVE identifiers.")
    commit_url = "https://api.github.com/repos/canonical/ubuntu-security-notices/commits/main"
    commit = json.loads(request(commit_url))["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid upstream commit identity")
    args.output.mkdir(parents=True)

    def fetch(cve):
        url = ("https://raw.githubusercontent.com/canonical/ubuntu-security-notices/"
               f"{commit}/vex/cve/{cve.split('-')[1]}/{cve}.json")
        row = {"cve": cve, "url": url}
        try:
            raw = request(url)
            doc = json.loads(raw)
            if not doc.get("statements") or not all(
                s.get("vulnerability", {}).get("name") == cve
                for s in doc["statements"]
            ):
                raise ValueError("VEX document has missing or mismatched CVE statements")
            (args.output / f"{cve}.json").write_bytes(raw)
            row.update(state="downloaded", sha256=hashlib.sha256(raw).hexdigest())
        except urllib.error.HTTPError as error:
            row.update(state="missing" if error.code == 404 else "error",
                       error=f"HTTP {error.code}")
        except Exception as error:
            row.update(state="error", error=str(error))
        return row

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(fetch, ids))
    index = {"retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "upstream_commit": commit, "commit_url": commit_url, "rows": rows,
             "non_cve_identifiers_not_queried": excluded,
             "limitation": "Missing/error records remain unresolved. Match distro, "
                           "architecture, source and installed versions before applying VEX."}
    (args.output / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"commit": commit, "requested": len(rows),
                      **{state: sum(r["state"] == state for r in rows)
                         for state in ("downloaded", "missing", "error")}}, indent=2))
    if any(r["state"] == "error" for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
