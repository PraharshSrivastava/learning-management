class PDFFile {
  final String documentId;
  final String fileName;
  final String displayName;
  final int size;
  final String createdAt;

  PDFFile({
    required this.documentId,
    required this.fileName,
    required this.displayName,
    required this.size,
    required this.createdAt,
  });

  factory PDFFile.fromJson(Map<String, dynamic> json) {
    return PDFFile(
      documentId: json['document_id'] as String,
      fileName: json['file_name'] as String,
      displayName:
          json['display_name']?.toString() ?? json['file_name'] as String,
      size: json['size'] as int,
      createdAt: json['created_at'] as String,
    );
  }

  String get formattedSize {
    if (size < 1024) return '$size B';
    if (size < 1024 * 1024) return '${(size / 1024).toStringAsFixed(1)} KB';
    return '${(size / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  String get formattedDate {
    final dateTime = DateTime.parse(createdAt).toLocal();
    return '${dateTime.day}/${dateTime.month}/${dateTime.year} ${dateTime.hour.toString().padLeft(2, '0')}:${dateTime.minute.toString().padLeft(2, '0')}';
  }
}

// ---------- Course Image Data Model ----------

class CourseImage {
  final String imageId;
  final String caption;
  final String filePath;

  CourseImage({
    required this.imageId,
    required this.caption,
    required this.filePath,
  });

  factory CourseImage.fromJson(Map<String, dynamic> json) {
    return CourseImage(
      imageId: json['image_id']?.toString() ?? '',
      caption: json['caption']?.toString() ?? '',
      filePath: json['file_path']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'image_id': imageId,
        'caption': caption,
        'file_path': filePath,
      };
}

// ---------- Module Model ----------

class CourseModule {
  final int moduleNumber;
  final String title;
  final String sourceText;
  final String startLine;
  final String endLine;
  final int numQuestions;
  final Map<String, dynamic>? quiz;
  final List<dynamic> slides;
  final List<CourseImage> images;
  final String? videoPath;
  final String notes;
  final List<dynamic> captions;

  CourseModule({
    required this.moduleNumber,
    required this.title,
    required this.sourceText,
    required this.startLine,
    required this.endLine,
    this.numQuestions = 3,
    this.quiz,
    this.slides = const [],
    this.images = const [],
    this.videoPath,
    this.notes = '',
    this.captions = const [],
  });

  factory CourseModule.fromJson(Map<String, dynamic> json) {
    final slideList = json['slides'] as List? ?? [];
    return CourseModule(
      moduleNumber: (json['module_number'] as num?)?.toInt() ?? 0,
      title: json['title']?.toString() ?? '',
      sourceText: json['source_text']?.toString() ?? '',
      startLine: json['start_line']?.toString() ?? '',
      endLine: json['end_line']?.toString() ?? '',
      numQuestions: (json['num_questions'] as num?)?.toInt() ?? 3,
      quiz: json['quiz'] as Map<String, dynamic>?,
      slides: slideList,
      images: (json['images'] as List? ?? [])
          .map((img) => CourseImage.fromJson(img as Map<String, dynamic>))
          .toList(),
      videoPath: json['video_path']?.toString(),
      notes: json['notes']?.toString() ?? '',
      captions: json['captions'] as List? ?? [],
    );
  }

  Map<String, dynamic> toJson() => {
        'module_number': moduleNumber,
        'title': title,
        'source_text': sourceText,
        'start_line': startLine,
        'end_line': endLine,
        'num_questions': numQuestions,
        'quiz': quiz,
        'slides': slides,
        'images': images.map((img) => img.toJson()).toList(),
        'video_path': videoPath,
        'notes': notes,
        'captions': captions,
      };
}

class Trainer {
  final String trainerId;
  final String name;
  final String status;

  const Trainer({
    required this.trainerId,
    required this.name,
    required this.status,
  });

  factory Trainer.fromJson(Map<String, dynamic> json) {
    return Trainer(
      trainerId: json['trainer_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      status: json['status']?.toString() ?? '',
    );
  }
}

class Employee {
  final String employeeId;
  final String name;
  final String department;
  final String jobTitle;
  final String joinDate;
  final String status;

  Employee({
    required this.employeeId,
    required this.name,
    required this.department,
    required this.jobTitle,
    required this.joinDate,
    required this.status,
  });

  factory Employee.fromJson(Map<String, dynamic> json) {
    return Employee(
      employeeId: json['employee_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      department: json['department']?.toString() ?? '',
      jobTitle: json['job_title']?.toString() ?? '',
      joinDate: json['join_date']?.toString() ?? '',
      status: json['status']?.toString() ?? '',
    );
  }
}

class AssignmentRule {
  final bool includeAll;
  final List<AssignmentGroup> includeGroups;
  final List<AssignmentGroup> excludeGroups;
  final int deadlineDays;
  final bool isActive;

  const AssignmentRule({
    this.includeAll = true,
    this.includeGroups = const [],
    this.excludeGroups = const [],
    this.deadlineDays = 7,
    this.isActive = true,
  });

  factory AssignmentRule.fromJson(Map<String, dynamic> json) {
    List<String> strings(String key) =>
        (json[key] as List? ?? []).map((item) => item.toString()).toList();
    List<AssignmentGroup> groups(String key) => (json[key] as List? ?? [])
        .map((item) => AssignmentGroup.fromJson(item as Map<String, dynamic>))
        .toList();
    final includeGroups = groups('include_groups');
    final excludeGroups = groups('exclude_groups');
    return AssignmentRule(
      includeAll: json['include_all'] != false,
      includeGroups: includeGroups.isNotEmpty
          ? includeGroups
          : [
              AssignmentGroup(
                employeeIds: strings('include_employee_ids'),
                departments: strings('include_departments'),
                jobTitles: strings('include_job_titles'),
                joinedLessThanDaysAgo:
                    (json['joined_less_than_days_ago'] as num?)?.toInt(),
              )
            ].where((group) => !group.isEmpty).toList(),
      excludeGroups: excludeGroups.isNotEmpty
          ? excludeGroups
          : [
              AssignmentGroup(
                employeeIds: strings('exclude_employee_ids'),
                departments: strings('exclude_departments'),
                jobTitles: strings('exclude_job_titles'),
              )
            ].where((group) => !group.isEmpty).toList(),
      deadlineDays: (json['deadline_days'] as num?)?.toInt() ?? 7,
      isActive: json['is_active'] != false,
    );
  }

  AssignmentRule copyWith({
    bool? includeAll,
    List<AssignmentGroup>? includeGroups,
    List<AssignmentGroup>? excludeGroups,
    int? deadlineDays,
    bool? isActive,
  }) {
    return AssignmentRule(
      includeAll: includeAll ?? this.includeAll,
      includeGroups: includeGroups ?? this.includeGroups,
      excludeGroups: excludeGroups ?? this.excludeGroups,
      deadlineDays: deadlineDays ?? this.deadlineDays,
      isActive: isActive ?? this.isActive,
    );
  }

  Map<String, dynamic> toJson() => {
        'include_all': includeAll,
        'include_groups': includeGroups.map((group) => group.toJson()).toList(),
        'exclude_groups': excludeGroups.map((group) => group.toJson()).toList(),
        'deadline_days': deadlineDays,
      };
}

class AssignmentGroup {
  final List<String> employeeIds;
  final List<String> departments;
  final List<String> jobTitles;
  final int? joinedLessThanDaysAgo;

  const AssignmentGroup({
    this.employeeIds = const [],
    this.departments = const [],
    this.jobTitles = const [],
    this.joinedLessThanDaysAgo,
  });

  bool get isEmpty =>
      employeeIds.isEmpty &&
      departments.isEmpty &&
      jobTitles.isEmpty &&
      joinedLessThanDaysAgo == null;

  factory AssignmentGroup.fromJson(Map<String, dynamic> json) {
    List<String> strings(String key) =>
        (json[key] as List? ?? []).map((item) => item.toString()).toList();
    return AssignmentGroup(
      employeeIds: strings('employee_ids'),
      departments: strings('departments'),
      jobTitles: strings('job_titles'),
      joinedLessThanDaysAgo:
          (json['joined_less_than_days_ago'] as num?)?.toInt(),
    );
  }

  AssignmentGroup copyWith({
    List<String>? employeeIds,
    List<String>? departments,
    List<String>? jobTitles,
    int? joinedLessThanDaysAgo,
    bool clearJoinedLessThanDaysAgo = false,
  }) {
    return AssignmentGroup(
      employeeIds: employeeIds ?? this.employeeIds,
      departments: departments ?? this.departments,
      jobTitles: jobTitles ?? this.jobTitles,
      joinedLessThanDaysAgo: clearJoinedLessThanDaysAgo
          ? null
          : (joinedLessThanDaysAgo ?? this.joinedLessThanDaysAgo),
    );
  }

  Map<String, dynamic> toJson() => {
        'employee_ids': employeeIds,
        'departments': departments,
        'job_titles': jobTitles,
        'joined_less_than_days_ago': joinedLessThanDaysAgo,
      };
}

class AssignmentOptions {
  final List<Employee> employees;
  final List<String> departments;
  final List<String> jobTitles;

  const AssignmentOptions({
    this.employees = const [],
    this.departments = const [],
    this.jobTitles = const [],
  });

  factory AssignmentOptions.fromJson(Map<String, dynamic> json) {
    return AssignmentOptions(
      employees: (json['employees'] as List? ?? [])
          .map((item) => Employee.fromJson(item as Map<String, dynamic>))
          .toList(),
      departments: (json['departments'] as List? ?? [])
          .map((item) => item.toString())
          .toList(),
      jobTitles: (json['job_titles'] as List? ?? [])
          .map((item) => item.toString())
          .toList(),
    );
  }
}

class PerformanceCourseOption {
  final String courseId;
  final String courseName;

  const PerformanceCourseOption({required this.courseId, required this.courseName});

  factory PerformanceCourseOption.fromJson(Map<String, dynamic> json) {
    return PerformanceCourseOption(
      courseId: json['course_id']?.toString() ?? '',
      courseName: json['course_name']?.toString() ?? '',
    );
  }
}

class PerformanceStatusOption {
  final String key;
  final String label;

  const PerformanceStatusOption({required this.key, required this.label});

  factory PerformanceStatusOption.fromJson(Map<String, dynamic> json) {
    return PerformanceStatusOption(
      key: json['key']?.toString() ?? '',
      label: json['label']?.toString() ?? '',
    );
  }
}

class PerformanceOptions {
  final List<Employee> employees;
  final List<String> departments;
  final List<String> jobTitles;
  final List<PerformanceCourseOption> courses;
  final List<PerformanceStatusOption> statuses;

  const PerformanceOptions({
    this.employees = const [],
    this.departments = const [],
    this.jobTitles = const [],
    this.courses = const [],
    this.statuses = const [],
  });

  factory PerformanceOptions.fromJson(Map<String, dynamic> json) {
    return PerformanceOptions(
      employees: (json['employees'] as List? ?? [])
          .map((item) => Employee.fromJson(item as Map<String, dynamic>))
          .toList(),
      departments: (json['departments'] as List? ?? [])
          .map((item) => item.toString())
          .toList(),
      jobTitles: (json['job_titles'] as List? ?? [])
          .map((item) => item.toString())
          .toList(),
      courses: (json['courses'] as List? ?? [])
          .map((item) =>
              PerformanceCourseOption.fromJson(item as Map<String, dynamic>))
          .toList(),
      statuses: (json['statuses'] as List? ?? [])
          .map((item) =>
              PerformanceStatusOption.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}

class PerformanceSummary {
  final int assigned;
  final int pending;
  final int started;
  final int completed;
  final int overdue;
  final int completionRate;
  final double averageAttempts;
  final double? averageScore;

  const PerformanceSummary({
    this.assigned = 0,
    this.pending = 0,
    this.started = 0,
    this.completed = 0,
    this.overdue = 0,
    this.completionRate = 0,
    this.averageAttempts = 0,
    this.averageScore,
  });

  factory PerformanceSummary.fromJson(Map<String, dynamic> json) {
    return PerformanceSummary(
      assigned: (json['assigned'] as num?)?.toInt() ?? 0,
      pending: (json['pending'] as num?)?.toInt() ?? 0,
      started: (json['started'] as num?)?.toInt() ?? 0,
      completed: (json['completed'] as num?)?.toInt() ?? 0,
      overdue: (json['overdue'] as num?)?.toInt() ?? 0,
      completionRate: (json['completion_rate'] as num?)?.toInt() ?? 0,
      averageAttempts: (json['average_attempts'] as num?)?.toDouble() ?? 0,
      averageScore: (json['average_score'] as num?)?.toDouble(),
    );
  }
}

class PerformanceBreakdown {
  final String label;
  final int assigned;
  final int pending;
  final int started;
  final int completed;
  final int overdue;
  final int completionRate;

  const PerformanceBreakdown({
    required this.label,
    required this.assigned,
    required this.pending,
    required this.started,
    required this.completed,
    required this.overdue,
    required this.completionRate,
  });

  factory PerformanceBreakdown.fromJson(Map<String, dynamic> json) {
    return PerformanceBreakdown(
      label: json['label']?.toString() ?? '',
      assigned: (json['assigned'] as num?)?.toInt() ?? 0,
      pending: (json['pending'] as num?)?.toInt() ?? 0,
      started: (json['started'] as num?)?.toInt() ?? 0,
      completed: (json['completed'] as num?)?.toInt() ?? 0,
      overdue: (json['overdue'] as num?)?.toInt() ?? 0,
      completionRate: (json['completion_rate'] as num?)?.toInt() ?? 0,
    );
  }
}

class PerformanceModule {
  final int moduleNumber;
  final String title;
  final bool videoWatched;
  final bool quizPassed;
  final double? quizScore;
  final int attemptCount;
  final double? lastScore;
  final bool? lastPassed;
  final String? lastAttemptAt;

  const PerformanceModule({
    required this.moduleNumber,
    required this.title,
    required this.videoWatched,
    required this.quizPassed,
    this.quizScore,
    required this.attemptCount,
    this.lastScore,
    this.lastPassed,
    this.lastAttemptAt,
  });

  factory PerformanceModule.fromJson(Map<String, dynamic> json) {
    return PerformanceModule(
      moduleNumber: (json['module_number'] as num?)?.toInt() ?? 0,
      title: json['title']?.toString() ?? '',
      videoWatched: json['video_watched'] == true,
      quizPassed: json['quiz_passed'] == true,
      quizScore: (json['quiz_score'] as num?)?.toDouble(),
      attemptCount: (json['attempt_count'] as num?)?.toInt() ?? 0,
      lastScore: (json['last_score'] as num?)?.toDouble(),
      lastPassed: json['last_passed'] as bool?,
      lastAttemptAt: json['last_attempt_at']?.toString(),
    );
  }
}

class PerformanceRow {
  final Employee employee;
  final String courseId;
  final String courseTitle;
  final String statusKey;
  final String statusLabel;
  final String? assignedAt;
  final String? deadline;
  final String? lastActivityAt;
  final int totalModules;
  final int completedModules;
  final int completionPercent;
  final int totalAttempts;
  final double? latestScore;
  final double? bestScore;
  final double? averageScore;
  final List<PerformanceModule> modules;

  const PerformanceRow({
    required this.employee,
    required this.courseId,
    required this.courseTitle,
    required this.statusKey,
    required this.statusLabel,
    this.assignedAt,
    this.deadline,
    this.lastActivityAt,
    required this.totalModules,
    required this.completedModules,
    required this.completionPercent,
    required this.totalAttempts,
    this.latestScore,
    this.bestScore,
    this.averageScore,
    required this.modules,
  });

  factory PerformanceRow.fromJson(Map<String, dynamic> json) {
    final course = json['course'] as Map<String, dynamic>? ?? {};
    final status = json['status'] as Map<String, dynamic>? ?? {};
    return PerformanceRow(
      employee: Employee.fromJson(json['employee'] as Map<String, dynamic>),
      courseId: course['course_id']?.toString() ?? '',
      courseTitle: course['course_name']?.toString() ?? '',
      statusKey: status['key']?.toString() ?? 'pending',
      statusLabel: status['label']?.toString() ?? 'Pending',
      assignedAt: json['assigned_at']?.toString(),
      deadline: json['deadline']?.toString(),
      lastActivityAt: json['last_activity_at']?.toString(),
      totalModules: (json['total_modules'] as num?)?.toInt() ?? 0,
      completedModules: (json['completed_modules'] as num?)?.toInt() ?? 0,
      completionPercent: (json['completion_percent'] as num?)?.toInt() ?? 0,
      totalAttempts: (json['total_attempts'] as num?)?.toInt() ?? 0,
      latestScore: (json['latest_score'] as num?)?.toDouble(),
      bestScore: (json['best_score'] as num?)?.toDouble(),
      averageScore: (json['average_score'] as num?)?.toDouble(),
      modules: (json['modules'] as List? ?? [])
          .map((item) =>
              PerformanceModule.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}

class PerformanceDashboard {
  final PerformanceSummary summary;
  final List<PerformanceBreakdown> courseBreakdowns;
  final List<PerformanceBreakdown> departmentBreakdowns;
  final List<PerformanceBreakdown> jobTitleBreakdowns;
  final List<PerformanceRow> rows;
  final PerformanceOptions options;
  final String generatedAt;

  const PerformanceDashboard({
    this.summary = const PerformanceSummary(),
    this.courseBreakdowns = const [],
    this.departmentBreakdowns = const [],
    this.jobTitleBreakdowns = const [],
    this.rows = const [],
    this.options = const PerformanceOptions(),
    this.generatedAt = '',
  });

  factory PerformanceDashboard.fromJson(Map<String, dynamic> json) {
    final breakdowns = json['breakdowns'] as Map<String, dynamic>? ?? {};
    List<PerformanceBreakdown> breakdownList(String key) =>
        (breakdowns[key] as List? ?? [])
            .map((item) =>
                PerformanceBreakdown.fromJson(item as Map<String, dynamic>))
            .toList();
    return PerformanceDashboard(
      summary: PerformanceSummary.fromJson(
        json['summary'] as Map<String, dynamic>? ?? {},
      ),
      courseBreakdowns: breakdownList('courses'),
      departmentBreakdowns: breakdownList('departments'),
      jobTitleBreakdowns: breakdownList('job_titles'),
      rows: (json['rows'] as List? ?? [])
          .map((item) => PerformanceRow.fromJson(item as Map<String, dynamic>))
          .toList(),
      options: PerformanceOptions.fromJson(
        json['options'] as Map<String, dynamic>? ?? {},
      ),
      generatedAt: json['generated_at']?.toString() ?? '',
    );
  }
}

// Model for Generated Course Outline
class Course {
  final String courseId;
  final String courseName;
  final String courseDescription;
  final String courseObjective;
  final String courseDifficulty;
  final String language;
  final String targetAudience;
  final List<CourseModule> modules;
  final List<CourseImage> images;
  final String thumbnailPath;
  final String createdAt;
  final String generationStatus;
  final String failedCheckpoint;
  final String currentCheckpoint;
  final String generationError;

  Course({
    required this.courseId,
    required this.courseName,
    required this.courseDescription,
    required this.courseObjective,
    required this.courseDifficulty,
    required this.language,
    required this.targetAudience,
    required this.modules,
    required this.images,
    this.thumbnailPath = '',
    required this.createdAt,
    this.generationStatus = '',
    this.failedCheckpoint = '',
    this.currentCheckpoint = '',
    this.generationError = '',
  });

  factory Course.fromJson(Map<String, dynamic> json) {
    return Course(
      courseId: json['course_id']?.toString() ?? '',
      courseName: json['course_name']?.toString() ?? '',
      courseDescription: json['course_description']?.toString() ?? '',
      courseObjective: json['course_objective']?.toString() ?? '',
      courseDifficulty: json['course_difficulty']?.toString() ?? '',
      language: json['language']?.toString() ?? '',
      targetAudience: json['target_audience']?.toString() ?? '',
      modules: (json['modules'] as List? ?? []).map((item) {
        if (item is Map<String, dynamic>) {
          return CourseModule.fromJson(item);
        }
        return CourseModule(
          moduleNumber: 0,
          title: item.toString(),
          sourceText: '',
          startLine: '',
          endLine: '',
        );
      }).toList(),
      images: (json['images'] as List? ?? [])
          .map((img) => CourseImage.fromJson(img as Map<String, dynamic>))
          .toList(),
      thumbnailPath: json['thumbnail_path']?.toString() ?? '',
      createdAt: json['created_at']?.toString() ?? '',
      generationStatus:
          (json['generation'] as Map?)?['status']?.toString() ?? '',
      failedCheckpoint:
          (json['generation'] as Map?)?['failed_checkpoint']?.toString() ?? '',
      currentCheckpoint:
          (json['generation'] as Map?)?['current_checkpoint']?.toString() ?? '',
      generationError: (json['generation'] as Map?)?['error']?.toString() ?? '',
    );
  }
}

// ---------- DATA MODELS FOR QUIZ ----------

class QuizQuestion {
  final String questionText;
  final List<QuizOption> options;
  final String correctOption;
  final String explanation;

  QuizQuestion({
    required this.questionText,
    required this.options,
    required this.correctOption,
    required this.explanation,
  });

  factory QuizQuestion.fromJson(Map<String, dynamic> json) {
    return QuizQuestion(
      questionText: json['question_text']?.toString() ?? '',
      options: (json['options'] as List? ?? [])
          .map((o) => QuizOption.fromJson(o as Map<String, dynamic>))
          .toList(),
      correctOption: json['correct_option']?.toString() ?? '',
      explanation: json['explanation']?.toString() ?? '',
    );
  }
}

class QuizOption {
  final String key;
  final String text;

  QuizOption({required this.key, required this.text});

  factory QuizOption.fromJson(Map<String, dynamic> json) {
    return QuizOption(
      key: json['key']?.toString() ?? '',
      text: json['text']?.toString() ?? '',
    );
  }
}
