class PDFFile {
  final String filename;
  final int size;
  final double created;

  PDFFile({
    required this.filename,
    required this.size,
    required this.created,
  });

  factory PDFFile.fromJson(Map<String, dynamic> json) {
    return PDFFile(
      filename: json['filename'] as String,
      size: json['size'] as int,
      created: (json['created'] as num).toDouble(),
    );
  }

  String get formattedSize {
    if (size < 1024) return '$size B';
    if (size < 1024 * 1024) return '${(size / 1024).toStringAsFixed(1)} KB';
    return '${(size / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  String get formattedDate {
    final dateTime = DateTime.fromMillisecondsSinceEpoch((created * 1000).toInt());
    return '${dateTime.day}/${dateTime.month}/${dateTime.year} ${dateTime.hour.toString().padLeft(2, '0')}:${dateTime.minute.toString().padLeft(2, '0')}';
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
  final String text;
  final String startLine;
  final String endLine;
  final List<CourseLesson> lessons;
  final int numQuestions;
  final Map<String, dynamic>? quiz;
  final List<dynamic> slides;
  final String? videoPath;

  CourseModule({
    required this.moduleNumber,
    required this.title,
    required this.text,
    required this.startLine,
    required this.endLine,
    this.lessons = const [],
    this.numQuestions = 0,
    this.quiz,
    this.slides = const [],
    this.videoPath,
  });

  factory CourseModule.fromJson(Map<String, dynamic> json) {
    final list = json['lessons'] as List? ?? [];
    final slideList = json['slides'] as List? ?? [];
    return CourseModule(
      moduleNumber: (json['module_number'] as num?)?.toInt() ?? 0,
      title: json['title']?.toString() ?? '',
      text: json['text']?.toString() ?? '',
      startLine: json['start_line']?.toString() ?? '',
      endLine: json['end_line']?.toString() ?? '',
      lessons: list
          .map((s) => CourseLesson.fromJson(s as Map<String, dynamic>))
          .toList(),
      numQuestions: (json['num_questions'] as num?)?.toInt() ?? 0,
      quiz: json['quiz'] as Map<String, dynamic>?,
      slides: slideList,
      videoPath: json['video_path']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
    'module_number': moduleNumber,
    'title': title,
    'text': text,
    'start_line': startLine,
    'end_line': endLine,
    'lessons': lessons.map((s) => s.toJson()).toList(),
    'num_questions': numQuestions,
    'quiz': quiz,
    'slides': slides,
    'video_path': videoPath,
  };
}

// Model for Generated Course Outline
class Course {
  final String id;
  final String courseName;
  final String courseDescription;
  final String courseObjective;
  final String courseDifficulty;
  final String language;
  final String targetAudience;
  final List<CourseModule> modules;
  final List<LessonImage> images;
  final String sourceFile;
  final double createdAt;

  Course({
    required this.id,
    required this.courseName,
    required this.courseDescription,
    required this.courseObjective,
    required this.courseDifficulty,
    required this.language,
    required this.targetAudience,
    required this.modules,
    required this.images,
    required this.sourceFile,
    required this.createdAt,
  });

  factory Course.fromJson(Map<String, dynamic> json) {
    return Course(
      id: json['id'] as String,
      courseName: json['course_name'] as String,
      courseDescription: json['course_description'] as String,
      courseObjective: json['course_objective'] as String,
      courseDifficulty: json['course_difficulty'] as String,
      language: json['language'] as String,
      targetAudience: json['target_audience'] as String,
      modules: (json['modules'] as List).map((item) {
        if (item is Map<String, dynamic>) {
          return CourseModule.fromJson(item);
        }
        // Legacy fallback
        return CourseModule(
          moduleNumber: 0,
          title: item.toString(),
          text: '',
          startLine: '',
          endLine: '',
        );
      }).toList(),
      images: (json['images'] as List? ?? [])
          .map((img) => LessonImage.fromJson(img as Map<String, dynamic>))
          .toList(),
      sourceFile: json['source_file'] as String,
      createdAt: (json['created_at'] as num).toDouble(),
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
