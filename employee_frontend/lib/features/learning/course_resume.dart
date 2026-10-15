import 'package:employee_frontend/data/models/models.dart';

bool moduleIsComplete(
    PublishedCourseModule module, EmployeeModuleProgress? progress) {
  return progress?.videoWatched == true &&
      (module.quiz.isEmpty || progress?.quizPassed == true);
}

/// Null means every published module is complete (including an empty course).
int? firstIncompleteModule(Course course) {
  final index = course.publishedModules.indexWhere((module) =>
      !moduleIsComplete(
          module, course.moduleProgress[module.moduleNumber.toString()]));
  return index < 0 ? null : index;
}
