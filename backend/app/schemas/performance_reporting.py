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
    on_time: bool


class ReportSummary(ApiSchema):
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
