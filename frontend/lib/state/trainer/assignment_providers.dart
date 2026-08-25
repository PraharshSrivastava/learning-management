part of '../trainer_providers.dart';

class AssignmentState {
  final AssignmentOptions options;
  final List<SavedAssignmentGroup> savedGroups;
  final AssignmentRule rule;
  final List<Employee> previewEmployees;
  final int matchCount;
  final int? assignedCount;
  final bool isLoading;
  final bool isSaving;
  final bool isPublishing;
  final String? error;
  final String? message;
  final String? loadedCourseId;

  AssignmentState({
    this.options = const AssignmentOptions(),
    this.savedGroups = const [],
    this.rule = const AssignmentRule(),
    this.previewEmployees = const [],
    this.matchCount = 0,
    this.assignedCount,
    this.isLoading = false,
    this.isSaving = false,
    this.isPublishing = false,
    this.error,
    this.message,
    this.loadedCourseId,
  });

  AssignmentState copyWith({
    AssignmentOptions? options,
    List<SavedAssignmentGroup>? savedGroups,
    AssignmentRule? rule,
    List<Employee>? previewEmployees,
    int? matchCount,
    int? assignedCount,
    bool? isLoading,
    bool? isSaving,
    bool? isPublishing,
    String? error,
    String? message,
    String? loadedCourseId,
  }) {
    return AssignmentState(
      options: options ?? this.options,
      savedGroups: savedGroups ?? this.savedGroups,
      rule: rule ?? this.rule,
      previewEmployees: previewEmployees ?? this.previewEmployees,
      matchCount: matchCount ?? this.matchCount,
      assignedCount: assignedCount ?? this.assignedCount,
      isLoading: isLoading ?? this.isLoading,
      isSaving: isSaving ?? this.isSaving,
      isPublishing: isPublishing ?? this.isPublishing,
      error: error,
      message: message,
      loadedCourseId: loadedCourseId ?? this.loadedCourseId,
    );
  }
}

class AssignmentNotifier extends StateNotifier<AssignmentState> {
  final Ref ref;

  AssignmentNotifier(this.ref) : super(AssignmentState()) {
    fetchOptions();
    fetchSavedGroups();
  }

  Future<void> fetchOptions() async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await http.get(
        Uri.parse(AppConstants.assignmentOptionsEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        state = state.copyWith(
          options: AssignmentOptions.fromJson(jsonDecode(response.body)),
          isLoading: false,
        );
      } else {
        state = state.copyWith(
            isLoading: false, error: 'Server returned ${response.statusCode}');
      }
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> refreshOptionsAndGroups() async {
    await Future.wait([fetchOptions(), fetchSavedGroups()]);
  }

  Future<void> fetchSavedGroups() async {
    try {
      final response = await http.get(
        Uri.parse(AppConstants.savedAssignmentGroupsEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        state = state.copyWith(
          savedGroups: (jsonDecode(response.body) as List? ?? [])
              .map((item) =>
                  SavedAssignmentGroup.fromJson(item as Map<String, dynamic>))
              .toList(),
        );
      }
    } catch (_) {
      // Saved groups are a convenience layer; assignment authoring still works
      // if this fetch fails and the main rule endpoint succeeds.
    }
  }

  Future<void> loadForCourse(String courseId) async {
    if (state.loadedCourseId == courseId) return;
    state = state.copyWith(isLoading: true, loadedCourseId: courseId);
    try {
      await refreshOptionsAndGroups();
      final response = await http.get(
        Uri.parse(AppConstants.courseAssignmentEndpoint(courseId)),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        _applyAssignmentResponse(
            jsonDecode(response.body) as Map<String, dynamic>,
            isLoading: false,
            loadedCourseId: courseId);
      } else {
        state = state.copyWith(
            isLoading: false, error: 'Server returned ${response.statusCode}');
      }
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  void updateRule(AssignmentRule rule) {
    state = state.copyWith(rule: rule, message: null, assignedCount: null);
  }

  String? _groupValidationError(AssignmentRule rule) {
    String? validate(List<AssignmentGroup> groups, String label) {
      for (var index = 0; index < groups.length; index++) {
        final group = groups[index];
        if (group.hasMixedSelection) {
          return '$label group ${index + 1} mixes specific employees with filters. Clear one side before saving.';
        }
        if (group.joinedLessThanDaysAgo == 0) {
          return '$label group ${index + 1} joined-days filter must be at least 1.';
        }
      }
      return null;
    }

    return validate(rule.includeGroups, 'Include') ??
        validate(rule.excludeGroups, 'Exclude');
  }

  Future<void> save(String courseId) async {
    final validationError = _groupValidationError(state.rule);
    if (validationError != null) {
      state = state.copyWith(error: validationError);
      return;
    }
    state = state.copyWith(isSaving: true);
    try {
      final ruleToSave = await _persistReusableGroups(state.rule);
      final response = await http.put(
        Uri.parse(AppConstants.courseAssignmentEndpoint(courseId)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
        body: jsonEncode(ruleToSave.toJson()),
      );
      if (response.statusCode == 200) {
        _applyAssignmentResponse(
            jsonDecode(response.body) as Map<String, dynamic>,
            isSaving: false,
            message: 'Assignment rule saved.');
        await fetchSavedGroups();
      } else {
        final decoded = jsonDecode(response.body);
        state = state.copyWith(
          isSaving: false,
          error:
              decoded['detail']?.toString() ?? 'Failed to save assignment rule',
        );
      }
    } catch (e) {
      state = state.copyWith(isSaving: false, error: e.toString());
    }
  }

  Future<void> publish(String courseId) async {
    final validationError = _groupValidationError(state.rule);
    if (validationError != null) {
      state = state.copyWith(error: validationError);
      return;
    }
    state = state.copyWith(isPublishing: true);
    try {
      final ruleToPublish = await _persistReusableGroups(state.rule);
      final response = await http.post(
        Uri.parse(AppConstants.publishCourseAssignmentEndpoint(courseId)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
        body: jsonEncode(ruleToPublish.toJson()),
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        final matchCount = decoded['match_count'] ?? 0;
        final assignedCount = decoded['assigned_count'] ?? 0;
        final removedCount = decoded['removed_count'] ?? 0;
        final reactivatedCount = decoded['reactivated_count'] ?? 0;
        final deadlineUpdateCount = decoded['deadline_update_count'] ?? 0;
        _applyAssignmentResponse(
          decoded,
          isPublishing: false,
          message: 'Published assignment for $matchCount matching employees. '
              '$assignedCount added, $reactivatedCount restored, $removedCount removed, '
              '$deadlineUpdateCount deadlines updated.',
          assignedCount: (decoded['assigned_count'] as num?)?.toInt(),
        );
        await ref.read(assignableCourseListProvider.notifier).fetchCourses();
        await ref.read(performanceProvider.notifier).fetch();
        await fetchSavedGroups();
      } else {
        final decoded = jsonDecode(response.body);
        state = state.copyWith(
          isPublishing: false,
          error:
              decoded['detail']?.toString() ?? 'Failed to publish assignment',
        );
      }
    } catch (e) {
      state = state.copyWith(isPublishing: false, error: e.toString());
    }
  }

  Future<AssignmentRule> _persistReusableGroups(AssignmentRule rule) async {
    Future<AssignmentGroup> persist(
      AssignmentGroup group,
      String groupType,
      int index,
    ) async {
      if (group.isEmpty) return group;
      final name = group.name.trim().isNotEmpty
          ? group.name.trim()
          : '${groupType == 'include' ? 'Include' : 'Exclude'} group '
              '${index + 1}';
      final payload = {
        'name': name,
        'group_type': groupType,
        'employee_ids': group.employeeIds,
        'departments': group.departments,
        'mailing_lists': group.mailingLists,
        'job_titles': group.jobTitles,
        'joined_less_than_days_ago': group.joinedLessThanDaysAgo,
      };
      final savedGroupId = group.savedGroupId;
      final response = savedGroupId == null
          ? await http.post(
              Uri.parse(AppConstants.savedAssignmentGroupsEndpoint),
              headers: {
                'Content-Type': 'application/json',
                ...ref.read(trainerAuthHeadersProvider),
              },
              body: jsonEncode(payload),
            )
          : await http.put(
              Uri.parse(
                  AppConstants.savedAssignmentGroupEndpoint(savedGroupId)),
              headers: {
                'Content-Type': 'application/json',
                ...ref.read(trainerAuthHeadersProvider),
              },
              body: jsonEncode(payload),
            );
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final decoded = jsonDecode(response.body);
        throw Exception(
          decoded['detail']?.toString() ?? 'Failed to save reusable group',
        );
      }
      return SavedAssignmentGroup.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      ).group;
    }

    final includeGroups = <AssignmentGroup>[];
    for (var index = 0; index < rule.includeGroups.length; index++) {
      includeGroups.add(
        await persist(rule.includeGroups[index], 'include', index),
      );
    }
    final excludeGroups = <AssignmentGroup>[];
    for (var index = 0; index < rule.excludeGroups.length; index++) {
      excludeGroups.add(
        await persist(rule.excludeGroups[index], 'exclude', index),
      );
    }
    final updatedRule = rule.copyWith(
      includeGroups: includeGroups,
      excludeGroups: excludeGroups,
    );
    state = state.copyWith(rule: updatedRule);
    return updatedRule;
  }

  Future<void> disable(String courseId) async {
    state = state.copyWith(isPublishing: true);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.disableCourseAssignmentEndpoint(courseId)),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (response.statusCode == 200) {
        _applyAssignmentResponse(
          jsonDecode(response.body) as Map<String, dynamic>,
          isPublishing: false,
          message: 'Course disabled for employees. Progress is preserved.',
        );
        await ref.read(assignableCourseListProvider.notifier).fetchCourses();
        await ref.read(performanceProvider.notifier).fetch();
      } else {
        final decoded = jsonDecode(response.body);
        state = state.copyWith(
          isPublishing: false,
          error: decoded['detail']?.toString() ?? 'Failed to disable course',
        );
      }
    } catch (e) {
      state = state.copyWith(isPublishing: false, error: e.toString());
    }
  }

  void _applyAssignmentResponse(
    Map<String, dynamic> decoded, {
    bool? isLoading,
    bool? isSaving,
    bool? isPublishing,
    String? message,
    String? loadedCourseId,
    int? assignedCount,
  }) {
    state = state.copyWith(
      rule: AssignmentRule.fromJson(decoded['rule'] as Map<String, dynamic>),
      matchCount: (decoded['match_count'] as num?)?.toInt() ?? 0,
      assignedCount: assignedCount,
      previewEmployees: (decoded['preview_employees'] as List? ?? [])
          .map((item) => Employee.fromJson(item as Map<String, dynamic>))
          .toList(),
      isLoading: isLoading ?? state.isLoading,
      isSaving: isSaving ?? state.isSaving,
      isPublishing: isPublishing ?? state.isPublishing,
      message: message,
      loadedCourseId: loadedCourseId,
    );
  }
}

final assignmentProvider =
    StateNotifierProvider<AssignmentNotifier, AssignmentState>((ref) {
  return AssignmentNotifier(ref);
});
