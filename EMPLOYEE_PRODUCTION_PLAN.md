# Employee Productionization Plan

## Employee-Only Plan Of Action

1. Add an `employees` table with fields such as `id`, `employee_code`, `name`, `email`, `department`, `role`, `level`, `manager_id`, `join_date`, `location`, `status`, `created_at`, and `updated_at`.

2. Replace the current global `employee_progress(course_id)` model with per-employee progress, keyed by `(employee_id, course_id)`.

3. Create an `employee_course_progress` table with `employee_id`, `course_id`, `status`, `assigned_at`, `deadline`, `completed_at`, `modules_json`, `attempts_json`, and `last_activity_at`.

4. Seed realistic dummy employees for testing, covering multiple departments, roles, levels, managers/directors, new joiners, old joiners, active employees, and inactive employees.

5. Add login-shaped demo auth endpoints:
   - `GET /api/employees`
   - `POST /api/auth/demo-login`
   - `GET /api/me`

6. Use demo login to select a dummy employee now, while keeping the API shape ready for real SSO or HR-backed login later.

7. Add employee-scoped course endpoints:
   - `GET /api/me/courses`
   - `PUT /api/me/courses/{course_id}/status`
   - `PUT /api/me/courses/{course_id}/modules/{module_number}`

8. Ensure all employee course/progress endpoints use the current logged-in employee identity instead of trusting a global progress record.

9. Add a reusable backend function such as `ensure_assignments_for_employee(employee_id)`.

10. For now, make `ensure_assignments_for_employee(employee_id)` assign all published courses to that employee, preserving the current behavior while making it per-employee.

11. Later, reuse the same `ensure_assignments_for_employee(employee_id)` function to evaluate assignment rules when trainer-side assignment logic is added.

12. Update `employee_frontend` to show a simple demo employee selection/login screen before the dashboard.

13. Store the selected employee session/token in the employee frontend and use it for all `/api/me/...` requests.

14. Update the employee dashboard to fetch courses from `/api/me/courses` instead of the current global employee courses endpoint.

15. Update course playback and quiz progress writes so video watched, quiz passed, quiz score, selected answers, and status changes are saved against the current employee.

16. Replace the global employee WebSocket with employee-scoped WebSockets.

17. Track active WebSocket connections by employee, so updates for one employee are only broadcast to that employee's open tabs/devices.

18. Preserve the current employee dashboard UX as much as possible while changing the underlying data ownership from global progress to per-employee progress.

19. Improve progress tracking to include attempt count, selected answers, quiz score, started timestamp, completed timestamp, and last activity timestamp.

20. Add safety tests to prove that Employee A's progress does not affect Employee B.

21. Add tests for new dummy employees receiving currently published courses.

22. Add tests for multiple employees starting and completing the same course independently.

23. Add tests proving WebSocket updates for one employee are not broadcast to another employee.

24. Add a stress test script to simulate 100-500 employees fetching courses, updating progress, and holding WebSocket connections.

25. Keep employee lookup and identity behind internal functions such as `list_employees()`, `get_employee()`, `authenticate_employee()`, `sync_employees()`, and `ensure_assignments_for_employee()`.

26. Ensure those internal functions use dummy DB data now, but can later be switched to HR sync and real auth without rewriting course progress logic.

## Production Readiness Checklist

1. Replace demo login with real company authentication, such as SSO, OIDC, SAML, or the company's chosen auth mechanism.

2. Validate sessions or tokens securely on every protected backend request.

3. Add logout, session expiry, unauthorized handling, and re-login flow.

4. Add role-based authorization so employees can only access their own learning data.

5. Add trainer/admin authorization separately from employee authorization.

6. Ensure backend APIs never trust arbitrary `employee_id` values sent from the frontend for employee-owned routes.

7. Add database migrations instead of relying only on `CREATE TABLE IF NOT EXISTS`.

8. Use a versioned migration tool or equivalent process so schema changes can be safely applied in production.

9. Add database constraints and indexes:
   - unique employee code
   - unique employee email where applicable
   - unique `(employee_id, course_id)` progress rows
   - foreign keys between employees, courses, and progress
   - indexes for employee, course, status, department, and role lookups

10. Move environment-specific configuration out of code and into environment variables or deployment configuration.

11. Externalize database URL/path, CORS origins, auth secrets, HR credentials, frontend API URL, and asset storage configuration.

12. Replace local SQLite with a production database such as PostgreSQL or the company-approved database, with connection pooling and environment-based configuration.

13. Add structured backend logging with request IDs.

14. Add error tracking and clear error responses for auth failures, progress update failures, and WebSocket failures.

15. Add basic operational metrics, including request latency, error rate, active WebSocket count, and progress update volume.

16. Improve employee frontend session handling for expired sessions, unauthorized responses, reconnect attempts, offline state, and missing employee profiles.

17. Stress test realistic employee usage with hundreds of concurrent course fetches, quiz submissions, progress updates, and WebSocket connections.

18. Validate video and static asset performance under load.

19. Consider moving course videos/slides/images from local backend static files to object storage or CDN for production scale.

20. Ensure video delivery supports efficient playback behavior, caching, and range requests if needed.

21. Add HR sync robustness:
   - handle department changes
   - handle role changes
   - handle manager changes
   - handle employee deactivation
   - preserve learning history for inactive or exited employees
   - audit sync results
   - retry failed syncs safely

22. Keep HR as the source of employee profile truth, while LMS remains the source of course assignment, progress, quiz attempts, completion status, and deadlines.

23. Add backend tests for auth/session behavior.

24. Add backend tests for per-employee data isolation.

25. Add backend tests for progress updates, module completion, quiz attempts, and course completion.

26. Add backend tests for assignment catch-up behavior.

27. Add WebSocket tests for employee-scoped broadcasting.

28. Add HR sync mapping tests once the HR database/schema is known.

29. Add deployment checks for environment configuration, database connectivity, static asset access, and health endpoint readiness.

30. Add backup and recovery expectations for LMS-owned progress data.

31. Run a final production-readiness pass across security, performance, observability, migrations, and operational recovery before launch.
