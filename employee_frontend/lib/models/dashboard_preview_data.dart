import 'models.dart';

class DashboardPreviewData {
  const DashboardPreviewData._();

  static List<Course> courses() {
    final now = DateTime.now();
    return [
      _course(
        id: 'preview-compliance',
        title: 'Compliance Essentials 2026',
        description:
            'Build a practical understanding of our core compliance responsibilities.',
        assignedAt: now.subtract(const Duration(days: 1)),
        deadline: now.add(const Duration(days: 12)),
        modules: 4,
      ),
      _course(
        id: 'preview-privacy',
        title: 'Data Privacy and Information Security',
        description:
            'Handle customer information confidently and respond to common security risks.',
        assignedAt: now.subtract(const Duration(days: 4)),
        deadline: now.add(const Duration(days: 4)),
        modules: 5,
        watched: const [1, 2],
        passed: const [1],
      ),
      _course(
        id: 'preview-risk',
        title: 'Operational Risk Management',
        description:
            'Recognize operational risks and take the right action when they arise.',
        assignedAt: now.subtract(const Duration(days: 10)),
        deadline: now.subtract(const Duration(days: 2)),
        modules: 3,
      ),
      _course(
        id: 'preview-conduct',
        title: 'Market Conduct and Ethics',
        description:
            'Apply fair dealing principles to everyday client and market interactions.',
        assignedAt: now.subtract(const Duration(days: 20)),
        deadline: now.subtract(const Duration(days: 5)),
        modules: 4,
        watched: const [1, 2, 3, 4],
        passed: const [1, 2, 3, 4],
      ),
      _course(
        id: 'preview-analysis',
        title: 'Reading Financial Statements',
        description:
            'Interpret key statements and identify the signals that matter for decisions.',
        assignedAt: now.subtract(const Duration(days: 28)),
        deadline: now.subtract(const Duration(days: 14)),
        modules: 3,
        watched: const [1, 2, 3],
        passed: const [1, 2, 3],
      ),
    ];
  }

  static Course _course({
    required String id,
    required String title,
    required String description,
    required DateTime assignedAt,
    required DateTime deadline,
    required int modules,
    List<int> watched = const [],
    List<int> passed = const [],
  }) {
    final publishedModules = List.generate(
      modules,
      (index) => PublishedCourseModule(
        moduleNumber: index + 1,
        title: 'Module ${index + 1}',
        notes:
            'Use this module to build practical understanding through the lesson video and knowledge check.',
        videoUrl:
            'https://flutter.github.io/assets-for-api-docs/assets/videos/butterfly.mp4',
        quiz: [
          PublishedQuizQuestion(
            questionId: 'preview-${index + 1}-1',
            question: 'What is the main purpose of this learning module?',
            options: const [
              'Build practical understanding',
              'Skip required controls',
              'Avoid assessment'
            ],
            correct: 'A',
            explanation:
                'Each module is designed to build practical understanding before the knowledge check.',
          ),
          PublishedQuizQuestion(
            questionId: 'preview-${index + 1}-2',
            question: 'What should you do after completing the video lesson?',
            options: const [
              'Complete the quiz',
              'Move to any locked module',
              'Exit without reviewing'
            ],
            correct: 'A',
            explanation:
                'The quiz confirms understanding and unlocks the next module after a passing score.',
          ),
        ],
        passMark: 0.7,
      ),
    );
    final progress = <String, EmployeeModuleProgress>{
      for (final module in publishedModules)
        if (watched.contains(module.moduleNumber) ||
            passed.contains(module.moduleNumber))
          '${module.moduleNumber}': EmployeeModuleProgress(
            videoWatched: watched.contains(module.moduleNumber) ||
                passed.contains(module.moduleNumber),
            quizPassed: passed.contains(module.moduleNumber),
          ),
    };
    return Course(
      id: id,
      courseName: title,
      courseDescription: description,
      courseObjective: '',
      courseDifficulty: '',
      language: 'English',
      targetAudience: 'Employees',
      modules: const [],
      images: [
        LessonImage(
          imageId: 'preview-thumbnail',
          caption: 'Learning dashboard preview thumbnail',
          filePath: 'assets/thumbnails/learning-preview.png',
        ),
      ],
      sourceFile: '',
      createdAt: assignedAt.millisecondsSinceEpoch.toDouble(),
      assignedAt: assignedAt.toIso8601String(),
      deadline: deadline.toIso8601String(),
      publishedModules: publishedModules,
      employeeProgress: progress,
    );
  }
}
