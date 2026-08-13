class PDFFile {
  final String documentId;
  final String fileName;
  final String fileType;
  final int size;
  final String createdAt;

  PDFFile({
    required this.documentId,
    required this.fileName,
    this.fileType = 'pdf',
    required this.size,
    required this.createdAt,
  });

  factory PDFFile.fromJson(Map<String, dynamic> json) {
    final fileName = json['file_name'] as String;
    final lowerName = fileName.toLowerCase();
    return PDFFile(
      documentId: json['document_id'] as String,
      fileName: fileName,
      fileType: json['file_type']?.toString() ??
          (lowerName.endsWith('.pptx')
              ? 'pptx'
              : lowerName.endsWith('.docx')
                  ? 'docx'
                  : 'pdf'),
      size: json['size'] as int,
      createdAt: json['created_at'] as String,
    );
  }

  bool get isPptx => fileType.toLowerCase() == 'pptx';
  bool get isDocx => fileType.toLowerCase() == 'docx';

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
      status: json['status']?.toString() ?? 'active',
    );
  }
}

// ---------- Lessons Data Models ----------

class BulletPoint {
  final String text;
  BulletPoint({required this.text});

  factory BulletPoint.fromJson(Map<String, dynamic> json) =>
      BulletPoint(text: json['text']?.toString() ?? '');

  Map<String, dynamic> toJson() => {'text': text};
}

class LessonImage {
  final String imageId;
  final String caption;
  final String filePath;

  LessonImage({
    required this.imageId,
    required this.caption,
    required this.filePath,
  });

  factory LessonImage.fromJson(Map<String, dynamic> json) {
    return LessonImage(
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

class CourseLesson {
  final int lessonNumber;
  final String lessonTitle;
  final List<BulletPoint> bullets;
  final List<LessonImage> images;

  CourseLesson({
    required this.lessonNumber,
    required this.lessonTitle,
    required this.bullets,
    required this.images,
  });

  factory CourseLesson.fromJson(Map<String, dynamic> json) {
    return CourseLesson(
      lessonNumber: (json['lesson_number'] as num?)?.toInt() ?? 0,
      lessonTitle: json['lesson_title']?.toString() ?? '',
      bullets: (json['bullets'] as List? ?? [])
          .map((b) => BulletPoint.fromJson(b as Map<String, dynamic>))
          .toList(),
      images: (json['images'] as List? ?? [])
          .map((img) => LessonImage.fromJson(img as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'lesson_number': lessonNumber,
        'lesson_title': lessonTitle,
        'bullets': bullets.map((b) => b.toJson()).toList(),
        'images': images.map((img) => img.toJson()).toList(),
      };
}

// ---------- Module Model ----------

class CourseModule {
  final int moduleNumber;
  final String title;
  final String sourceText;
  final String startLine;
  final String endLine;
  final List<CourseLesson> lessons;
  final int numQuestions;
  final Map<String, dynamic>? quiz;
  final List<dynamic> slides;
  final String? videoPath;
  final String notes;
  final List<dynamic> captions;

  CourseModule({
    required this.moduleNumber,
    required this.title,
    required this.sourceText,
    required this.startLine,
    required this.endLine,
    this.lessons = const [],
    this.numQuestions = 3,
    this.quiz,
    this.slides = const [],
    this.videoPath,
    this.notes = '',
    this.captions = const [],
  });

  factory CourseModule.fromJson(Map<String, dynamic> json) {
    final list = json['lessons'] as List? ?? [];
    final slideList = json['slides'] as List? ?? [];
    return CourseModule(
      moduleNumber: (json['module_number'] as num?)?.toInt() ?? 0,
      title: json['title']?.toString() ?? '',
      sourceText: json['source_text']?.toString() ?? '',
      startLine: json['start_line']?.toString() ?? '',
      endLine: json['end_line']?.toString() ?? '',
      lessons: list
          .map((s) => CourseLesson.fromJson(s as Map<String, dynamic>))
          .toList(),
      numQuestions: (json['num_questions'] as num?)?.toInt() ?? 3,
      quiz: json['quiz'] as Map<String, dynamic>?,
      slides: slideList,
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
        'lessons': lessons.map((s) => s.toJson()).toList(),
        'num_questions': numQuestions,
        'quiz': quiz,
        'slides': slides,
        'video_path': videoPath,
        'notes': notes,
        'captions': captions,
      };
}

class EmployeeModuleProgress {
  final bool videoWatched;
  final bool quizPassed;
  final num? quizScore;
  final Map<int, String>? selectedAnswers;
  final int attemptCount;

  EmployeeModuleProgress({
    this.videoWatched = false,
    this.quizPassed = false,
    this.quizScore,
    this.selectedAnswers,
    this.attemptCount = 0,
  });

  factory EmployeeModuleProgress.fromJson(Map<String, dynamic> json) {
    Map<int, String>? parsedAnswers;
    final bool quizPassed = json['quiz_passed'] == true;

    // Only load saved answers if the user actually passed the quiz.
    // If they failed, we ignore any saved answers so they can retake it.
    if (quizPassed &&
        json['selected_answers'] != null &&
        json['selected_answers'] is Map) {
      parsedAnswers = {};
      (json['selected_answers'] as Map).forEach((key, value) {
        final parsedKey = int.tryParse(key.toString());
        if (parsedKey != null) {
          parsedAnswers![parsedKey] = value.toString();
        }
      });
    }

    return EmployeeModuleProgress(
      videoWatched: json['video_watched'] == true,
      quizPassed: quizPassed,
      quizScore: json['quiz_score'] as num?,
      selectedAnswers: parsedAnswers,
      attemptCount: (json['attempt_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class PublishedQuizQuestion {
  final String questionId;
  final String question;
  final List<String> options;
  final String correct;
  final String explanation;

  PublishedQuizQuestion({
    required this.questionId,
    required this.question,
    required this.options,
    required this.correct,
    required this.explanation,
  });

  factory PublishedQuizQuestion.fromJson(Map<String, dynamic> json) {
    return PublishedQuizQuestion(
      questionId: json['question_id']?.toString() ?? '',
      question: json['question']?.toString() ?? '',
      options:
          (json['options'] as List? ?? []).map((e) => e.toString()).toList(),
      correct: json['correct']?.toString() ?? '',
      explanation: json['explanation']?.toString() ?? '',
    );
  }
}

class PublishedCourseModule {
  final int moduleNumber;
  final String title;
  final String notes;
  final String videoPath;
  final List<PublishedQuizQuestion> quiz;
  final double passMark;
  final List<dynamic> captions;

  PublishedCourseModule({
    required this.moduleNumber,
    required this.title,
    this.notes = '',
    required this.videoPath,
    required this.quiz,
    required this.passMark,
    this.captions = const [],
  });

  factory PublishedCourseModule.fromJson(Map<String, dynamic> json) {
    return PublishedCourseModule(
      moduleNumber: (json['module_number'] as num?)?.toInt() ?? 0,
      title: json['title']?.toString() ?? '',
      notes: json['notes']?.toString() ?? '',
      videoPath: json['video_path']?.toString() ?? '',
      quiz: (json['quiz'] as List? ?? [])
          .map((q) => PublishedQuizQuestion.fromJson(q as Map<String, dynamic>))
          .toList(),
      passMark: (json['pass_mark'] as num?)?.toDouble() ?? 0.67,
      captions: json['captions'] as List? ?? [],
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
  final List<LessonImage> images;
  final String thumbnailPath;
  final String createdAt;
  final String? assignmentStatus;
  final String? assignedAt;
  final String? deadline;
  final String? startedAt;
  final String? completedAt;

  final List<PublishedCourseModule> publishedModules;
  final Map<String, EmployeeModuleProgress> moduleProgress;

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
    this.assignmentStatus,
    this.assignedAt,
    this.deadline,
    this.startedAt,
    this.completedAt,
    this.publishedModules = const [],
    this.moduleProgress = const {},
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
      modules: (json['modules'] as List).map((item) {
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
          .map((img) => LessonImage.fromJson(img as Map<String, dynamic>))
          .toList(),
      thumbnailPath: json['thumbnail_path']?.toString() ?? '',
      createdAt: json['created_at']?.toString() ?? '',
      assignmentStatus: json['assignment_status'] as String?,
      assignedAt: json['assigned_at'] as String?,
      deadline: json['deadline'] as String?,
      startedAt: json['started_at'] as String?,
      completedAt: json['completed_at'] as String?,
    );
  }

  factory Course.fromPublishedJson(Map<String, dynamic> json) {
    final progressMap = <String, EmployeeModuleProgress>{};
    final progJson = json['module_progress'] as Map<String, dynamic>? ?? {};
    final attemptsJson =
        json['quiz_attempts'] as Map<String, dynamic>? ?? {};
    progJson.forEach((key, value) {
      if (value is Map<String, dynamic>) {
        final merged = Map<String, dynamic>.from(value);
        final attempt = attemptsJson[key];
        if (attempt is Map<String, dynamic>) {
          merged['attempt_count'] = attempt['count'];
        }
        progressMap[key] = EmployeeModuleProgress.fromJson(merged);
      }
    });

    return Course(
      courseId: json['course_id'] as String? ?? '',
      courseName: json['course_name'] as String? ?? '',
      courseDescription: json['course_description'] as String? ?? '',
      courseObjective: '',
      courseDifficulty: '',
      language: '',
      targetAudience: '',
      modules: [], // simplified for employee dashboard
      images: (json['images'] as List? ?? [])
          .map((img) => LessonImage.fromJson(img as Map<String, dynamic>))
          .toList(),
      thumbnailPath: json['thumbnail_path']?.toString() ?? '',
      createdAt: json['created_at']?.toString() ?? '',
      assignmentStatus: json['assignment_status'] as String?,
      assignedAt: json['assigned_at'] as String?,
      deadline: json['deadline'] as String?,
      startedAt: json['started_at'] as String?,
      completedAt: json['completed_at'] as String?,
      publishedModules: (json['modules'] as List? ?? [])
          .map((m) => PublishedCourseModule.fromJson(m as Map<String, dynamic>))
          .toList(),
      moduleProgress: progressMap,
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
