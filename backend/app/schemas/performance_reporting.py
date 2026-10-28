"""Response contracts for trainer performance reporting."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiSchema


class AssignmentReportRow(ApiSchema):
    assignment_id: str
    employee_id: str
    employee_name: str
    employee_status: str
    department: str | None = None
    mailing_lists: list[str] = Field(default_factory=list)
    course_id: str
    course_name: str
    status: str
    due_soon: bool
    inactive: bool
    repeated_failures: bool
    failed_attempts: int
    assigned_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    deadline: str | None = None
    last_learner_activity_at: str | None = None
    total_modules: int
    completed_modules: int
    completion_percent: int
    total_attempts: int
    average_score: float | None = None
    scored_modules: int
    course_status: str = "active"
    access_available: bool = True
    access_reason: str | None = None
    on_time: bool


class ReportSummary(ApiSchema):
    current_assignments: int = 0
    historical_assignments: int = 0
    assigned: int
    unique_learners: int
    pending: int
    started: int
    completed: int
    overdue: int
    due_soon: int
    inactive: int
    repeated_failures: int
    completion_rate: int
    on_time_compliance: int | None = None
    on_time_denominator: int
    average_score: float | None = None
    scored_modules: int


class ReportBreakdown(ApiSchema):
    label: str
    course_id: str | None = None
    assigned: int
    completed: int
    overdue: int
    completion_rate: int


class ReportBreakdowns(ApiSchema):
    courses: list[ReportBreakdown]
    departments: list[ReportBreakdown]
    mailing_lists: list[ReportBreakdown]


class CompletionTrendPoint(ApiSchema):
    date: str
    completed: int


class PerformanceOverview(ApiSchema):
    summary: ReportSummary
    breakdowns: ReportBreakdowns
    completion_trend: list[CompletionTrendPoint]
    watchlist: list[AssignmentReportRow]
    generated_at: str
    due_soon_days: int
    inactive_days: int


class CourseReport(ReportSummary):
    course_id: str
    course_name: str


class CourseListReport(ApiSchema):
    courses: list[CourseReport]
    generated_at: str


class CourseModuleReport(ApiSchema):
    module_id: str
    module_number: int
    title: str
    num_questions: int
    assigned: int
    watched: int
    passed: int
    attempts: int
    average_score: float | None = None


class CourseDetailReport(ApiSchema):
    course: CourseReport
    modules: list[CourseModuleReport]
    generated_at: str


class AssignmentListReport(ApiSchema):
    rows: list[AssignmentReportRow]
    total: int
    page: int
    page_size: int
    generated_at: str


class AssignmentModuleReport(ApiSchema):
    module_id: str
    module_number: int
    title: str
    num_questions: int
    video_watched: bool
    quiz_passed: bool
    latest_score: float | None = None
    attempt_count: int
    last_attempt_at: str | None = None


class QuizAttemptReport(ApiSchema):
    module_id: str | None = None
    occurred_at: str
    score: float | None = None
    passed: bool | None = None


class AssignmentDetailReport(ApiSchema):
    assignment: AssignmentReportRow
    modules: list[AssignmentModuleReport]
    attempts: list[QuizAttemptReport]
    generated_at: str


class ReportCourseOption(ApiSchema):
    course_id: str
    course_name: str


class PerformanceReportOptions(ApiSchema):
    courses: list[ReportCourseOption]
    departments: list[str]
    mailing_lists: list[str]
    # True when Learning Journeys are switched on, so the report shows its Journeys tab.
    journeys_enabled: bool = False


class EmployeeReportRow(ApiSchema):
    employee_id: str
    employee_name: str
    employee_status: str
    department: str | None = None
    assigned: int
    completed: int
    in_progress: int
    not_started: int
    completion_rate: float
    overdue: int
    due_soon: int
    inactive: int
    repeated_failures: int
    average_score: float | None = None
    scored_modules: int
    last_learner_activity_at: str | None = None
    needs_attention: bool


class EmployeeListReport(ApiSchema):
    rows: list[EmployeeReportRow]
    total: int
    page: int
    page_size: int
    summary: dict[str, int]
    generated_at: str


class EmployeeDetailReport(ApiSchema):
    employee: EmployeeReportRow
    assignments: list[AssignmentReportRow]
    generated_at: str


class JourneyReport(ApiSchema):
    journey_id: str
    title: str
    journey_status: str
    step_count: int
    required_count: int
    certificate_enabled: bool
    assigned: int
    unique_learners: int
    completed: int
    started: int
    pending: int
    waiting: int
    overdue: int
    removed: int
    due_soon: int
    inactive: int
    completion_rate: int
    average_progress: int
    certificates: int


class JourneyListReport(ApiSchema):
    enabled: bool
    journeys: list[JourneyReport]
    generated_at: str


class JourneyStepReport(ApiSchema):
    course_id: str
    course_name: str
    step_number: int
    stage_title: str | None = None
    is_required: bool
    unlock_rule: str
    learners: int
    passed: int
    in_progress: int
    available: int
    locked: int
    unavailable: int


class JourneyLearnerReport(ApiSchema):
    journey_id: str
    employee_id: str
    employee_name: str
    employee_status: str
    department: str | None = None
    status: str
    assigned_at: str | None = None
    available_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    deadline: str | None = None
    last_learner_activity_at: str | None = None
    passed_count: int
    required_count: int
    completion_percent: int
    current_step: int | None = None
    current_course_id: str | None = None
    current_course_name: str | None = None
    certificate_number: str | None = None
    due_soon: bool
    inactive: bool


class JourneyDetailReport(ApiSchema):
    journey: JourneyReport
    steps: list[JourneyStepReport]
    learners: list[JourneyLearnerReport]
    generated_at: str
