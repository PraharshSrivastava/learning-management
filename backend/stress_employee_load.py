import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def _request(method, url, payload=None, token=None, timeout=20):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    elapsed_ms = (time.perf_counter() - start) * 1000
    return response.status, json.loads(body), elapsed_ms


def _employee_flow(base_url, employee_id, update_progress):
    _, login, login_ms = _request(
        "POST",
        f"{base_url}/api/auth/demo-login",
        {"employee_id": employee_id},
    )
    token = login["token"]
    _, courses, courses_ms = _request("GET", f"{base_url}/api/me/courses", token=token)

    update_ms = None
    if update_progress and courses:
        course = courses[0]
        modules = course.get("modules", [])
        if modules:
            module_number = modules[0].get("module_number", 1)
            _, _, update_ms = _request(
                "PUT",
                f"{base_url}/api/me/courses/{course['course_id']}/modules/{module_number}",
                {"video_watched": True},
                token=token,
            )

    return {
        "employee_id": employee_id,
        "courses": len(courses),
        "login_ms": login_ms,
        "courses_ms": courses_ms,
        "update_ms": update_ms,
    }


def _active_employee_ids(base_url, limit):
    _, employees, _ = _request("GET", f"{base_url}/api/employees")
    return [employee["id"] for employee in employees[:limit]]


def main():
    parser = argparse.ArgumentParser(description="Stress test employee demo login and course APIs.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--employees", type=int, default=100)
    parser.add_argument("--workers", type=int, default=25)
    parser.add_argument("--update-progress", action="store_true")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    employee_ids = _active_employee_ids(base_url, args.employees)
    results = []
    failures = []
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_employee_flow, base_url, employee_id, args.update_progress): employee_id
            for employee_id in employee_ids
        }
        for future in as_completed(futures):
            employee_id = futures[future]
            try:
                results.append(future.result())
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, Exception) as exc:
                failures.append((employee_id, str(exc)))

    elapsed = time.perf_counter() - start
    login_times = [item["login_ms"] for item in results]
    course_times = [item["courses_ms"] for item in results]
    update_times = [item["update_ms"] for item in results if item["update_ms"] is not None]

    def summarize(values):
        if not values:
            return "n/a"
        return (
            f"avg={statistics.mean(values):.1f}ms "
            f"p50={statistics.median(values):.1f}ms "
            f"max={max(values):.1f}ms"
        )

    print(f"Completed {len(results)} employee flows with {len(failures)} failures in {elapsed:.2f}s")
    print(f"Login latency:   {summarize(login_times)}")
    print(f"Courses latency: {summarize(course_times)}")
    if args.update_progress:
        print(f"Update latency:  {summarize(update_times)}")
    if failures:
        print("Failures:")
        for employee_id, error in failures[:20]:
            print(f"  {employee_id}: {error}")


if __name__ == "__main__":
    main()
