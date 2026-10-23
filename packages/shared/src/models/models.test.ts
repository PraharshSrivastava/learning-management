import { describe, expect, it } from 'vitest'
import {
  assignmentGroupToJson,
  assignmentRuleToJson,
  defaultAssignmentRule,
  emptyAssignmentGroup,
  formattedDate,
  formattedSize,
  hasMixedSelection,
  indexedMap,
  isDocx,
  isDueSoon,
  isGenerationComplete,
  isGroupEmpty,
  isNewAssignment,
  isPptx,
  learningMetrics,
  orderedAssigned,
  orderedAttempted,
  parseAssignmentDetailReport,
  parseAssignmentGroup,
  parseAssignmentListReport,
  parseAssignmentOptions,
  parseAssignmentReportRow,
  parseAssignmentRule,
  parseCourse,
  parseCourseDetailReport,
  parseCourseListReport,
  parseEmployee,
  parseEmployeeCourse,
  parseEmployeeDetailReport,
  parseEmployeeListReport,
  parseEmployeeModuleProgress,
  parseEmployeeProfile,
  parseGenerationJob,
  parsePdfFile,
  parsePerformanceOverview,
  parsePerformanceReportOptions,
  parsePublishedCourseModule,
  parseQuizQuestion,
  parseQuizSubmissionResult,
  parseSavedAssignmentGroup,
  parseTrainer,
  formatPercent,
  formatScore,
  progressFor,
  quizSubmitToJson,
  ruleForEditor,
  savedGroupPayload,
  statusFor,
  watchedModulesFor,
} from './index'

describe('files', () => {
  const sample = {
    document_id: 'd1',
    file_name: 'Deck.PPTX',
    display_name: 'Safety deck',
    size: 2048,
    created_at: '2026-03-04T10:05:00',
  }
  it('maps snake_case and infers the type from the extension', () => {
    expect(parsePdfFile(sample)).toEqual({
      documentId: 'd1',
      fileName: 'Deck.PPTX',
      displayName: 'Safety deck',
      fileType: 'pptx',
      size: 2048,
      createdAt: '2026-03-04T10:05:00',
    })
    expect(parsePdfFile({ ...sample, file_name: 'a.docx' }).fileType).toBe('docx')
    expect(parsePdfFile({ ...sample, file_name: 'a.txt' }).fileType).toBe('pdf')
  })
  it('defaults display name and keeps an explicit file type', () => {
    const file = parsePdfFile({ ...sample, display_name: null, file_type: 'DOCX' })
    expect(file.displayName).toBe('Deck.PPTX')
    expect(isDocx(file)).toBe(true)
    expect(isPptx(file)).toBe(false)
  })
  it('falls back for a wrong-typed optional field and throws for a required one', () => {
    expect(parsePdfFile({ ...sample, display_name: 7 }).displayName).toBe('7')
    expect(() => parsePdfFile({ ...sample, size: '5' })).toThrow()
    expect(() => parsePdfFile({ ...sample, document_id: null })).toThrow()
  })
  it('formats size and date', () => {
    const size = (n: number) => formattedSize({ ...parsePdfFile(sample), size: n })
    expect(size(512)).toBe('512 B')
    expect(size(1536)).toBe('1.5 KB')
    expect(size(5 * 1024 * 1024)).toBe('5.0 MB')
    expect(formattedDate(parsePdfFile(sample))).toBe('4/3/2026 10:05')
  })
})

describe('people', () => {
  it('parses a trainer', () => {
    expect(parseTrainer({ trainer_id: 't1', name: 'Ann', status: 'active' })).toEqual({
      trainerId: 't1',
      name: 'Ann',
      status: 'active',
    })
    expect(parseTrainer({})).toEqual({ trainerId: '', name: '', status: '' })
    expect(parseTrainer({ name: 5 }).name).toBe('5')
  })
  it('parses a trainer app employee', () => {
    const payload = {
      employee_id: 'E1',
      name: 'Bo',
      department: 'Ops',
      mailing_lists: ['all', 3],
      job_title: 'Lead',
      join_date: '2025-01-02',
      status: 'active',
    }
    expect(parseEmployee(payload)).toEqual({
      employeeId: 'E1',
      name: 'Bo',
      department: 'Ops',
      mailingLists: ['all', '3'],
      jobTitle: 'Lead',
      joinDate: '2025-01-02',
      status: 'active',
    })
    expect(parseEmployee({})).toMatchObject({ status: '', mailingLists: [] })
    expect(parseEmployee({ mailing_lists: 'x' }).mailingLists).toEqual([])
  })
  it('uses the active status default for the employee app profile', () => {
    expect(parseEmployeeProfile({ employee_id: 'E1' })).toEqual({
      employeeId: 'E1',
      name: '',
      department: '',
      jobTitle: '',
      joinDate: '',
      status: 'active',
    })
  })
})

describe('generation', () => {
  it('parses a job', () => {
    const job = parseGenerationJob({ id: 'j1', course_id: 'c1', status: 'failed', error: 'boom' })
    expect(job).toEqual({ id: 'j1', courseId: 'c1', status: 'failed', error: 'boom' })
    expect(isGenerationComplete(job)).toBe(true)
    expect(isGenerationComplete({ ...job, status: 'running' })).toBe(false)
  })
  it('defaults missing fields', () => {
    expect(parseGenerationJob({})).toEqual({ id: '', courseId: '', status: '', error: null })
    expect(parseGenerationJob({ id: 12 }).id).toBe('12')
  })
})

describe('quiz', () => {
  const sample = {
    question_text: 'Q?',
    options: [
      { key: 'A', text: 'one' },
      { key: 'B', text: 'two' },
    ],
    correct_option: 'A',
    explanation: 'Because',
  }
  it('maps a question', () => {
    expect(parseQuizQuestion(sample)).toEqual({
      questionText: 'Q?',
      options: [
        { key: 'A', text: 'one' },
        { key: 'B', text: 'two' },
      ],
      correctOption: 'A',
      explanation: 'Because',
    })
  })
  it('defaults and wrong-type fallback', () => {
    expect(parseQuizQuestion({})).toEqual({
      questionText: '',
      options: [],
      correctOption: '',
      explanation: '',
    })
    expect(parseQuizQuestion({ options: 'nope' }).options).toEqual([])
    expect(parseQuizQuestion({ options: [{ key: 1 }] }).options).toEqual([{ key: '1', text: '' }])
  })
  it('parses a submit result', () => {
    const result = parseQuizSubmissionResult({
      quiz_passed: true,
      quiz_score: 0.75,
      correct_count: 3,
      total_questions: 4,
      pass_mark: 0.6667,
      answer_results: { '0': true, '1': false, '2': 'true', x: true },
    })
    expect(result).toEqual({
      passed: true,
      score: 0.75,
      correctCount: 3,
      totalQuestions: 4,
      passMark: 0.6667,
      answerResults: { 0: true, 1: false },
    })
  })
  it('falls back for optional maps and throws for required numbers', () => {
    const base = { quiz_score: 1, correct_count: 1, total_questions: 1, pass_mark: 0.5 }
    const result = parseQuizSubmissionResult({ ...base, quiz_passed: 'yes', answer_results: [1] })
    expect(result.passed).toBe(false)
    expect(result.answerResults).toEqual({})
    expect(() => parseQuizSubmissionResult({ ...base, quiz_score: null })).toThrow()
  })
  it('builds the submit body', () => {
    expect(quizSubmitToJson({ 0: 'A', 2: 'C' })).toEqual({
      selected_answers: { '0': 'A', '2': 'C' },
    })
  })
  it('indexedMap keeps only integer keys', () => {
    expect(indexedMap({ '1': 2, a: 3 }, true)).toEqual({ 1: '2' })
    expect(indexedMap('x', true)).toEqual({})
  })
})

describe('course (trainer)', () => {
  const module = {
    module_number: 1,
    title: 'Intro',
    source_text: 'text',
    start_line: '1',
    end_line: '9',
    num_questions: 2,
    quiz: { questions: [{ question_text: 'Q' }] },
    slides: [{ a: 1 }],
    images: [{ image_id: 'i1', caption: 'cap', file_path: '/x.png' }],
    video_path: '/v.mp4',
    notes: 'n',
    captions: [{ t: 1 }],
  }
  const sample = {
    lifecycle_state: 'published',
    lifecycle_revision: 4,
    can_delete: true,
    course_id: 'c1',
    trainer_id: 't1',
    can_manage: true,
    creator_name: 'Ann',
    course_name: 'Safety',
    course_description: 'desc',
    course_objective: 'obj',
    course_difficulty: 'easy',
    language: 'en',
    target_audience: 'all',
    modules: [module],
    images: [],
    thumbnail_path: '/t.png',
    status: 'ready',
    created_at: '2026-01-01T00:00:00Z',
    generation: { status: 'done', failed_checkpoint: 'f', current_checkpoint: 'c', error: 'e' },
    module_count: 1,
    is_assignable: false,
  }
  it('maps snake_case to camelCase', () => {
    const course = parseCourse(sample)
    expect(course).toMatchObject({
      lifecycleState: 'published',
      lifecycleRevision: 4,
      canDelete: true,
      courseId: 'c1',
      trainerId: 't1',
      canManage: true,
      creatorName: 'Ann',
      courseName: 'Safety',
      thumbnailPath: '/t.png',
      generationStatus: 'done',
      failedCheckpoint: 'f',
      currentCheckpoint: 'c',
      generationError: 'e',
      moduleCount: 1,
      isAssignable: true,
    })
    expect(course.modules[0]).toEqual({
      moduleNumber: 1,
      title: 'Intro',
      sourceText: 'text',
      startLine: '1',
      endLine: '9',
      numQuestions: 2,
      quiz: { questions: [{ question_text: 'Q' }] },
      slides: [{ a: 1 }],
      images: [{ imageId: 'i1', caption: 'cap', filePath: '/x.png' }],
      videoPath: '/v.mp4',
      notes: 'n',
      captions: [{ t: 1 }],
    })
  })
  it('defaults every missing field', () => {
    expect(parseCourse({})).toEqual({
      lifecycleState: '',
      lifecycleRevision: 0,
      canDelete: false,
      courseId: '',
      trainerId: '',
      documentId: null,
      canManage: false,
      creatorName: null,
      courseName: '',
      courseDescription: '',
      courseObjective: '',
      courseDifficulty: '',
      language: '',
      targetAudience: '',
      modules: [],
      images: [],
      thumbnailPath: '',
      status: '',
      createdAt: '',
      generationStatus: '',
      failedCheckpoint: '',
      currentCheckpoint: '',
      generationError: '',
      moduleCount: 0,
      isAssignable: false,
    })
    expect(parseCourse({ modules: [{}] }).modules[0]).toMatchObject({
      numQuestions: 3,
      notes: '',
      quiz: null,
    })
  })
  it('falls back for wrong types', () => {
    const course = parseCourse({
      ...sample,
      lifecycle_revision: 'x',
      can_delete: 'true',
      modules: 'bad',
      generation: 'bad',
      module_count: 'x',
      is_assignable: 1,
      course_name: 42,
    })
    expect(course).toMatchObject({
      lifecycleRevision: 0,
      canDelete: false,
      modules: [],
      generationStatus: '',
      moduleCount: 0,
      isAssignable: false,
      courseName: '42',
    })
  })
  it('turns a non-map module item into a title-only module', () => {
    const course = parseCourse({ modules: ['Plain title'] })
    expect(course.modules[0]).toMatchObject({
      moduleNumber: 0,
      title: 'Plain title',
      numQuestions: 3,
    })
    expect(course.moduleCount).toBe(1)
  })
  it('infers assignable only when every module is complete', () => {
    const base = { ...sample, is_assignable: false }
    expect(parseCourse({ ...base, status: 'draft' }).isAssignable).toBe(false)
    expect(parseCourse({ ...base, thumbnail_path: '' }).isAssignable).toBe(false)
    expect(parseCourse({ ...base, modules: [{ ...module, video_path: '' }] }).isAssignable).toBe(
      false,
    )
    expect(
      parseCourse({ ...base, modules: [{ ...module, quiz: { questions: [] } }] }).isAssignable,
    ).toBe(false)
    expect(
      parseCourse({ ...base, modules: [{ ...module, num_questions: 0, quiz: null }] }).isAssignable,
    ).toBe(true)
    expect(parseCourse({ ...base, status: 'published' }).isAssignable).toBe(true)
    expect(parseCourse({ is_assignable: true }).isAssignable).toBe(true)
  })
  it('keeps an explicit module_count', () => {
    expect(parseCourse({ ...sample, module_count: 9 }).moduleCount).toBe(9)
  })
})

describe('assignment', () => {
  const group = {
    saved_group_id: 'g1',
    name: ' North ',
    employee_ids: ['E1'],
    departments: ['Ops'],
    mailing_lists: [],
    job_titles: ['Lead'],
    joined_less_than_days_ago: 30,
  }
  it('maps a group and round-trips toJson', () => {
    const parsed = parseAssignmentGroup(group)
    expect(parsed).toEqual({
      savedGroupId: 'g1',
      name: ' North ',
      employeeIds: ['E1'],
      departments: ['Ops'],
      mailingLists: [],
      jobTitles: ['Lead'],
      joinedLessThanDaysAgo: 30,
    })
    expect(assignmentGroupToJson(parsed)).toEqual({ ...group, name: 'North' })
    expect(parseAssignmentGroup(assignmentGroupToJson(parsed))).toEqual({
      ...parsed,
      name: 'North',
    })
  })
  it('omits saved_group_id and blank name in toJson', () => {
    expect(assignmentGroupToJson(emptyAssignmentGroup({ name: '  ' }))).toEqual({
      employee_ids: [],
      departments: [],
      mailing_lists: [],
      job_titles: [],
      joined_less_than_days_ago: null,
    })
  })
  it('defaults and wrong types for a group', () => {
    expect(parseAssignmentGroup({})).toEqual(emptyAssignmentGroup())
    expect(parseAssignmentGroup({ employee_ids: 'x', joined_less_than_days_ago: '3' })).toEqual(
      emptyAssignmentGroup(),
    )
    expect(parseAssignmentGroup({ joined_less_than_days_ago: 2.9 }).joinedLessThanDaysAgo).toBe(2)
  })
  it('computes group predicates', () => {
    expect(isGroupEmpty(emptyAssignmentGroup())).toBe(true)
    expect(isGroupEmpty(emptyAssignmentGroup({ joinedLessThanDaysAgo: 0 }))).toBe(false)
    expect(
      hasMixedSelection(emptyAssignmentGroup({ employeeIds: ['a'], departments: ['d'] })),
    ).toBe(true)
    expect(hasMixedSelection(emptyAssignmentGroup({ employeeIds: ['a'] }))).toBe(false)
  })
  it('parses a rule with groups', () => {
    const rule = parseAssignmentRule({
      include_all: false,
      include_groups: [group],
      exclude_groups: [],
      deadline_days: 14,
      deadline_mode: 'fixed',
      deadline_date: '2026-12-01',
      is_active: false,
    })
    expect(rule).toMatchObject({
      includeAll: false,
      deadlineDays: 14,
      deadlineMode: 'fixed',
      deadlineDate: '2026-12-01',
      isActive: false,
    })
    expect(rule.includeGroups).toHaveLength(1)
    expect(rule.excludeGroups).toEqual([])
  })
  it('falls back to legacy flat fields', () => {
    const rule = parseAssignmentRule({
      include_employee_ids: ['E1'],
      include_departments: ['Ops'],
      joined_less_than_days_ago: 10,
      exclude_job_titles: ['Intern'],
    })
    expect(rule.includeGroups).toEqual([
      emptyAssignmentGroup({
        employeeIds: ['E1'],
        departments: ['Ops'],
        joinedLessThanDaysAgo: 10,
      }),
    ])
    expect(rule.excludeGroups).toEqual([emptyAssignmentGroup({ jobTitles: ['Intern'] })])
  })
  it('ignores the legacy joined days for the exclude group', () => {
    expect(parseAssignmentRule({ joined_less_than_days_ago: 5 }).excludeGroups).toEqual([])
  })
  it('defaults a rule', () => {
    expect(parseAssignmentRule({})).toEqual({
      includeAll: true,
      includeGroups: [],
      excludeGroups: [],
      deadlineDays: 7,
      deadlineMode: 'relative',
      deadlineDate: null,
      isActive: true,
    })
    expect(parseAssignmentRule({ include_all: null, is_active: 0 })).toMatchObject({
      includeAll: true,
      isActive: true,
    })
    expect(parseAssignmentRule({ deadline_days: 'x' }).deadlineDays).toBe(7)
  })
  it('keeps the constructor default of fixed mode', () => {
    expect(defaultAssignmentRule().deadlineMode).toBe('fixed')
  })
  it('serializes a rule without is_active and gates deadline_date on mode', () => {
    const rule = parseAssignmentRule({
      include_groups: [group],
      deadline_mode: 'fixed',
      deadline_date: '2026-12-01',
    })
    const json = assignmentRuleToJson(rule)
    expect(json).toEqual({
      include_all: true,
      include_groups: [{ ...group, name: 'North' }],
      exclude_groups: [],
      deadline_days: 7,
      deadline_mode: 'fixed',
      deadline_date: '2026-12-01',
    })
    expect(assignmentRuleToJson({ ...rule, deadlineMode: 'relative' }).deadline_date).toBeNull()
    expect(parseAssignmentRule(json)).toMatchObject({
      includeGroups: rule.includeGroups.map((g) => ({ ...g, name: 'North' })),
    })
  })
  it('forces fixed mode for a rule that was never saved', () => {
    expect(ruleForEditor({}).deadlineMode).toBe('fixed')
    expect(ruleForEditor({ updated_at: '2026-01-01' }).deadlineMode).toBe('relative')
    expect(ruleForEditor({ published_at: '2026-01-01' }).deadlineMode).toBe('relative')
    expect(() => ruleForEditor(null)).toThrow()
  })
  it('builds the saved group payload', () => {
    const g = emptyAssignmentGroup({ employeeIds: ['E1'] })
    expect(savedGroupPayload(g, 'include', 0)).toEqual({
      name: 'Employee selection group 1',
      group_type: 'include',
      employee_ids: ['E1'],
      departments: [],
      mailing_lists: [],
      job_titles: [],
      joined_less_than_days_ago: null,
    })
    expect(savedGroupPayload({ ...g, name: ' Mine ' }, 'exclude', 2).name).toBe('Mine')
    expect(savedGroupPayload(g, 'exclude', 2).name).toBe('Employee exclusion group 3')
  })
  it('parses a saved group', () => {
    const saved = parseSavedAssignmentGroup({
      saved_group_id: 's1',
      trainer_id: 't1',
      name: 'Team',
      group_type: 'exclude',
      employee_ids: ['E1'],
    })
    expect(saved).toMatchObject({
      savedGroupId: 's1',
      trainerId: 't1',
      name: 'Team',
      groupType: 'exclude',
    })
    expect(saved.group).toMatchObject({ savedGroupId: 's1', name: 'Team', employeeIds: ['E1'] })
    expect(parseSavedAssignmentGroup({})).toMatchObject({ savedGroupId: '', groupType: 'include' })
  })
  it('parses options', () => {
    const options = parseAssignmentOptions({
      employees: [{ employee_id: 'E1', name: 'Bo' }],
      departments: ['Ops'],
      mailing_lists: ['all'],
      job_titles: ['Lead'],
    })
    expect(options.employees[0]).toMatchObject({ employeeId: 'E1', name: 'Bo' })
    expect(options).toMatchObject({
      departments: ['Ops'],
      mailingLists: ['all'],
      jobTitles: ['Lead'],
    })
    expect(parseAssignmentOptions({})).toEqual({
      employees: [],
      departments: [],
      mailingLists: [],
      jobTitles: [],
    })
    expect(parseAssignmentOptions({ departments: 'x' }).departments).toEqual([])
  })
})

describe('performance reports', () => {
  const row = {
    assignment_id: 'a1',
    employee_id: 'E1',
    employee_name: 'Bo',
    employee_status: 'active',
    department: 'Ops',
    mailing_lists: ['all'],
    course_id: 'c1',
    course_name: 'Safety',
    status: 'started',
    due_soon: true,
    inactive: false,
    repeated_failures: false,
    failed_attempts: 1,
    assigned_at: '2026-01-01',
    started_at: null,
    completed_at: null,
    deadline: '2026-02-01',
    last_learner_activity_at: null,
    total_modules: 4,
    completed_modules: 2,
    completion_percent: 50,
    total_attempts: 3,
    average_score: 72.5,
    scored_modules: 2,
    course_status: 'active',
    access_available: false,
    access_reason: 'disabled',
    on_time: true,
  }
  const summary = {
    current_assignments: 5,
    historical_assignments: 1,
    assigned: 6,
    unique_learners: 4,
    pending: 1,
    started: 2,
    completed: 3,
    overdue: 0,
    due_soon: 1,
    inactive: 0,
    repeated_failures: 0,
    completion_rate: 50,
    on_time_compliance: null,
    on_time_denominator: 0,
    average_score: 80,
    scored_modules: 7,
  }
  it('maps an assignment row', () => {
    expect(parseAssignmentReportRow(row)).toMatchObject({
      assignmentId: 'a1',
      employeeName: 'Bo',
      dueSoon: true,
      mailingLists: ['all'],
      completionPercent: 50,
      averageScore: 72.5,
      accessAvailable: false,
      accessReason: 'disabled',
      onTime: true,
      lastLearnerActivityAt: null,
    })
  })
  it('defaults an assignment row and falls back on wrong types', () => {
    expect(parseAssignmentReportRow({})).toMatchObject({
      courseStatus: 'active',
      accessAvailable: true,
      mailingLists: [],
      totalModules: 0,
      averageScore: null,
      dueSoon: false,
    })
    expect(
      parseAssignmentReportRow({ total_modules: '7', average_score: 'x', due_soon: 'true' }),
    ).toMatchObject({
      totalModules: 7,
      averageScore: null,
      dueSoon: false,
    })
  })
  it('maps the overview', () => {
    const overview = parsePerformanceOverview({
      summary,
      breakdowns: {
        courses: [
          {
            label: 'Safety',
            course_id: 'c1',
            assigned: 6,
            completed: 3,
            overdue: 0,
            completion_rate: 50,
          },
        ],
        departments: [],
        mailing_lists: [],
      },
      completion_trend: [{ date: '2026-01-01', completed: 2 }],
      watchlist: [row],
      generated_at: '2026-01-02T00:00:00Z',
      due_soon_days: 7,
      inactive_days: 14,
    })
    expect(overview.summary).toMatchObject({
      currentAssignments: 5,
      uniqueLearners: 4,
      dueSoon: 1,
      onTimeCompliance: null,
    })
    expect(overview.breakdowns.courses[0]).toEqual({
      label: 'Safety',
      courseId: 'c1',
      assigned: 6,
      completed: 3,
      overdue: 0,
      completionRate: 50,
    })
    expect(overview).toMatchObject({
      dueSoonDays: 7,
      inactiveDays: 14,
      generatedAt: '2026-01-02T00:00:00Z',
    })
    expect(overview.watchlist).toHaveLength(1)
    expect(overview.completionTrend).toEqual([{ date: '2026-01-01', completed: 2 }])
  })
  it('defaults an empty overview', () => {
    const overview = parsePerformanceOverview({})
    expect(overview.summary.assigned).toBe(0)
    expect(overview.breakdowns).toEqual({ courses: [], departments: [], mailingLists: [] })
    expect(parsePerformanceOverview({ summary: 'x', watchlist: 'y' }).watchlist).toEqual([])
  })
  it('maps options', () => {
    expect(
      parsePerformanceReportOptions({
        courses: [{ course_id: 'c1', course_name: 'Safety' }],
        departments: ['Ops'],
        mailing_lists: ['all'],
      }),
    ).toEqual({
      courses: [{ courseId: 'c1', courseName: 'Safety' }],
      departments: ['Ops'],
      mailingLists: ['all'],
    })
    expect(parsePerformanceReportOptions({})).toEqual({
      courses: [],
      departments: [],
      mailingLists: [],
    })
  })
  it('maps course list and detail', () => {
    const course = { ...summary, course_id: 'c1', course_name: 'Safety' }
    expect(
      parseCourseListReport({ courses: [course], generated_at: 'g' }).courses[0],
    ).toMatchObject({
      courseId: 'c1',
      completionRate: 50,
    })
    const detail = parseCourseDetailReport({
      course,
      modules: [
        {
          module_id: 'm1',
          module_number: 1,
          title: 'Intro',
          num_questions: 3,
          assigned: 6,
          watched: 5,
          passed: 4,
          attempts: 9,
          average_score: null,
        },
      ],
      generated_at: 'g',
    })
    expect(detail.modules[0]).toEqual({
      moduleId: 'm1',
      moduleNumber: 1,
      title: 'Intro',
      numQuestions: 3,
      assigned: 6,
      watched: 5,
      passed: 4,
      attempts: 9,
      averageScore: null,
    })
    expect(parseCourseDetailReport({}).course.courseId).toBe('')
  })
  it('maps assignment list and detail', () => {
    expect(
      parseAssignmentListReport({
        rows: [row],
        total: 40,
        page: 2,
        page_size: 25,
        generated_at: 'g',
      }),
    ).toMatchObject({
      total: 40,
      page: 2,
      pageSize: 25,
    })
    expect(parseAssignmentListReport({}).page).toBe(1)
    const detail = parseAssignmentDetailReport({
      assignment: row,
      modules: [
        {
          module_id: 'm1',
          module_number: 2,
          title: 'T',
          num_questions: 3,
          video_watched: true,
          quiz_passed: false,
          latest_score: 66.5,
          attempt_count: 2,
          last_attempt_at: '2026-01-05',
        },
      ],
      attempts: [
        { module_id: null, occurred_at: '2026-01-05', score: 66.5, passed: false },
        { occurred_at: 'x', passed: 'maybe' },
      ],
      generated_at: 'g',
    })
    expect(detail.modules[0]).toMatchObject({
      videoWatched: true,
      quizPassed: false,
      latestScore: 66.5,
      attemptCount: 2,
    })
    expect(detail.attempts[0]).toEqual({
      moduleId: null,
      occurredAt: '2026-01-05',
      score: 66.5,
      passed: false,
    })
    expect(detail.attempts[1]).toEqual({
      moduleId: null,
      occurredAt: 'x',
      score: null,
      passed: null,
    })
  })
  it('maps employee list and detail', () => {
    const employee = {
      employee_id: 'E1',
      employee_name: 'Bo',
      employee_status: 'active',
      department: null,
      assigned: 3,
      completed: 1,
      in_progress: 1,
      not_started: 1,
      completion_rate: 33.3,
      overdue: 0,
      due_soon: 1,
      inactive: 0,
      repeated_failures: 2,
      average_score: null,
      scored_modules: 0,
      last_learner_activity_at: null,
      needs_attention: true,
    }
    const list = parseEmployeeListReport({
      rows: [employee],
      total: 1,
      page: 1,
      page_size: 25,
      summary: { employees: 1, overdue: 'x' },
      generated_at: 'g',
    })
    expect(list.rows[0]).toMatchObject({
      employeeName: 'Bo',
      completionRate: 33.3,
      needsAttention: true,
      department: null,
    })
    expect(list.summary).toEqual({ employees: 1, overdue: 0 })
    const detail = parseEmployeeDetailReport({ employee, assignments: [row], generated_at: 'g' })
    expect(detail.employee.inProgress).toBe(1)
    expect(detail.assignments).toHaveLength(1)
    expect(parseEmployeeListReport({}).summary).toEqual({})
  })
  it('formats scores like the Dart helpers', () => {
    expect(formatScore(72.456)).toBe('72.5%')
    expect(formatScore(null)).toBe('-')
    expect(formatPercent(50)).toBe('50%')
    expect(formatPercent(33.33)).toBe('33.3%')
    expect(formatPercent('x')).toBe('-')
  })
})

describe('employee course', () => {
  const published = {
    course_id: 'c1',
    course_name: 'Safety',
    course_description: 'desc',
    images: [{ image_id: 'i', caption: 'c', file_path: '/a.png' }],
    thumbnail_path: '/t.png',
    created_at: '2026-01-01',
    assignment_status: 'pending',
    assigned_at: '2026-01-02T00:00:00Z',
    deadline: '2026-02-01T00:00:00Z',
    started_at: null,
    completed_at: null,
    modules: [
      {
        module_number: 1,
        title: 'Intro',
        notes: 'n',
        video_path: '/v1.mp4',
        quiz: [
          {
            question_id: 'q1',
            question: 'Q?',
            options: ['a', 'b'],
            correct: 'a',
            explanation: 'e',
          },
        ],
        pass_mark: 0.7,
        captions: [],
      },
      { module_number: 2, title: 'Two', video_path: '/v2.mp4', quiz: [] },
    ],
    module_progress: {
      '1': {
        video_watched: true,
        quiz_passed: true,
        quiz_score: 1,
        selected_answers: { '0': 'a', z: 'b' },
      },
      '2': { video_watched: true },
      '3': 'ignored',
    },
    quiz_attempts: { '1': { count: 2 } },
  }
  it('parses a published module', () => {
    expect(parsePublishedCourseModule(published.modules[0])).toEqual({
      moduleNumber: 1,
      title: 'Intro',
      notes: 'n',
      videoPath: '/v1.mp4',
      quiz: [
        { questionId: 'q1', question: 'Q?', options: ['a', 'b'], correct: 'a', explanation: 'e' },
      ],
      passMark: 0.7,
      captions: [],
    })
    expect(parsePublishedCourseModule({})).toEqual({
      moduleNumber: 0,
      title: '',
      notes: '',
      videoPath: '',
      quiz: [],
      passMark: 2 / 3,
      captions: [],
    })
    expect(parsePublishedCourseModule({ pass_mark: 'x', quiz: 'y' })).toMatchObject({
      passMark: 2 / 3,
      quiz: [],
    })
  })
  it('parses module progress', () => {
    expect(parseEmployeeModuleProgress({})).toEqual({
      videoWatched: false,
      quizPassed: false,
      quizScore: null,
      selectedAnswers: null,
      attemptCount: 0,
    })
    expect(
      parseEmployeeModuleProgress({
        quiz_passed: true,
        quiz_score: 0.5,
        selected_answers: { '1': 'B', x: 'C' },
        attempt_count: 3,
      }),
    ).toEqual({
      videoWatched: false,
      quizPassed: true,
      quizScore: 0.5,
      selectedAnswers: { 1: 'B' },
      attemptCount: 3,
    })
    // Failed quiz ignores saved answers.
    expect(
      parseEmployeeModuleProgress({ quiz_passed: false, selected_answers: { '1': 'B' } })
        .selectedAnswers,
    ).toBeNull()
    expect(parseEmployeeModuleProgress({ quiz_score: 'x', video_watched: 'yes' })).toMatchObject({
      quizScore: null,
      videoWatched: false,
    })
  })
  it('parses a published course and merges attempt counts', () => {
    const course = parseEmployeeCourse(published)
    expect(course).toMatchObject({
      courseId: 'c1',
      courseName: 'Safety',
      thumbnailPath: '/t.png',
      assignmentStatus: 'pending',
      assignedAt: '2026-01-02T00:00:00Z',
      startedAt: null,
      images: [{ imageId: 'i', caption: 'c', filePath: '/a.png' }],
    })
    expect(course.publishedModules).toHaveLength(2)
    expect(Object.keys(course.moduleProgress)).toEqual(['1', '2'])
    expect(course.moduleProgress['1']).toMatchObject({
      attemptCount: 2,
      selectedAnswers: { 0: 'a' },
    })
    expect(course.moduleProgress['2']).toMatchObject({ videoWatched: true, attemptCount: 0 })
  })
  it('defaults an empty course and handles wrong types', () => {
    expect(parseEmployeeCourse({})).toEqual({
      courseId: '',
      courseName: '',
      courseDescription: '',
      images: [],
      thumbnailPath: '',
      createdAt: '',
      assignmentStatus: null,
      assignedAt: null,
      deadline: null,
      startedAt: null,
      completedAt: null,
      publishedModules: [],
      moduleProgress: {},
    })
    expect(
      parseEmployeeCourse({ module_progress: 'x', quiz_attempts: 5, deadline: 12 }).deadline,
    ).toBeNull()
  })

  const NOW = new Date('2026-01-10T12:00:00Z')
  const make = (extra: Record<string, unknown>) => parseEmployeeCourse({ ...published, ...extra })
  const passedProgress = { '1': { quiz_passed: true }, '2': { video_watched: true } }
  it('computes status', () => {
    expect(statusFor(make({ module_progress: passedProgress }), NOW)).toBe('passed')
    expect(statusFor(make({ module_progress: { '1': { video_watched: true } } }), NOW)).toBe(
      'inProgress',
    )
    expect(statusFor(make({ module_progress: {} }), NOW)).toBe('pending')
    expect(statusFor(make({ module_progress: {}, deadline: '2026-01-01T00:00:00Z' }), NOW)).toBe(
      'overdue',
    )
    expect(
      statusFor(make({ module_progress: passedProgress, deadline: '2026-01-01T00:00:00Z' }), NOW),
    ).toBe('passed')
    expect(statusFor(make({ modules: [], module_progress: {} }), NOW)).toBe('pending')
  })
  it('computes progress and watched modules', () => {
    expect(progressFor(make({ module_progress: { '1': { quiz_passed: true } } }))).toBe(0.5)
    expect(progressFor(make({ modules: [] }))).toBe(0)
    expect(watchedModulesFor(make({ module_progress: passedProgress }))).toBe(1)
  })
  it('flags due soon and new assignments', () => {
    expect(isDueSoon(make({ deadline: '2026-01-15T00:00:00Z' }), NOW)).toBe(true)
    expect(isDueSoon(make({ deadline: '2026-01-20T00:00:00Z' }), NOW)).toBe(false)
    expect(isDueSoon(make({ deadline: '2026-01-05T00:00:00Z' }), NOW)).toBe(false)
    expect(isDueSoon(make({ deadline: null }), NOW)).toBe(false)
    expect(
      isNewAssignment(
        make({ module_progress: {}, assigned_at: '2026-01-08T00:00:00Z', deadline: null }),
        NOW,
      ),
    ).toBe(true)
    expect(
      isNewAssignment(make({ module_progress: {}, assigned_at: '2025-12-01T00:00:00Z' }), NOW),
    ).toBe(false)
    expect(
      isNewAssignment(
        make({
          module_progress: { '1': { video_watched: true } },
          assigned_at: '2026-01-08T00:00:00Z',
        }),
        NOW,
      ),
    ).toBe(false)
  })
  it('orders assigned and attempted courses', () => {
    const overdue = make({ course_id: 'o', module_progress: {}, deadline: '2026-01-01T00:00:00Z' })
    const pendingLate = make({
      course_id: 'p2',
      module_progress: {},
      deadline: '2026-03-01T00:00:00Z',
    })
    const pendingEarly = make({
      course_id: 'p1',
      module_progress: {},
      deadline: '2026-02-01T00:00:00Z',
    })
    const pendingNone = make({ course_id: 'p3', module_progress: {}, deadline: null })
    const progress = make({
      course_id: 'i',
      module_progress: { '1': { video_watched: true } },
      assigned_at: '2026-01-05T00:00:00Z',
    })
    const done = make({
      course_id: 'd',
      module_progress: passedProgress,
      assigned_at: '2026-01-07T00:00:00Z',
    })
    const all = [done, pendingLate, progress, pendingNone, overdue, pendingEarly]
    expect(orderedAssigned(all, NOW).map((c) => c.courseId)).toEqual(['o', 'p1', 'p2', 'p3', 'i'])
    expect(orderedAttempted(all, NOW).map((c) => c.courseId)).toEqual(['d', 'i'])
    expect(learningMetrics(all, NOW)).toEqual({
      assigned: 5,
      attempted: 2,
      passed: 1,
      pending: 4,
      inProgress: 1,
    })
  })
})
