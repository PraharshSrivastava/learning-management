part of '../trainer_providers.dart';

class AssignmentState {
  final AssignmentOptions options;
  final List<SavedAssignmentGroup> savedGroups;
  final AssignmentRule rule;
  final List<Employee> previewEmployees;
  final int matchCount;
  final int totalAssignedCount;
  final int previewTotal;
  final int previewPage;
  final String previewView;
  final String previewSearch;
  final bool isPreviewLoading;
  final bool previewStale;
  final bool dirty;
  final int refreshGeneration;
  final int blockedEmployeeCount;
  final List<String> draftObserverIds;
  final List<String> conflictingObserverIds;
  final bool isLoading;
  final bool isSaving;
  final bool isPublishing;
  final int? assignedCount;
  final String? error;
  final String? message;
  final String? loadedCourseId;
  const AssignmentState({
    this.options = const AssignmentOptions(),
    this.savedGroups = const [],
    this.rule = const AssignmentRule(),
    this.previewEmployees = const [],
    this.matchCount = 0,
    this.totalAssignedCount = 0,
    this.previewTotal = 0,
    this.previewPage = 1,
    this.previewView = 'matching',
    this.previewSearch = '',
    this.isPreviewLoading = false,
    this.previewStale = false,
    this.dirty = false,
    this.refreshGeneration = 0,
    this.blockedEmployeeCount = 0,
    this.draftObserverIds = const [],
    this.conflictingObserverIds = const [],
    this.isLoading = false,
    this.isSaving = false,
    this.isPublishing = false,
    this.assignedCount,
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
    int? totalAssignedCount,
    int? previewTotal,
    int? previewPage,
    String? previewView,
    String? previewSearch,
    bool? isPreviewLoading,
    bool? previewStale,
    bool? dirty,
    int? refreshGeneration,
    int? blockedEmployeeCount,
    List<String>? draftObserverIds,
    List<String>? conflictingObserverIds,
    bool? isLoading,
    bool? isSaving,
    bool? isPublishing,
    int? assignedCount,
    String? error,
    String? message,
    String? loadedCourseId,
    bool clearAssignedCount = false,
  }) =>
      AssignmentState(
        options: options ?? this.options,
        savedGroups: savedGroups ?? this.savedGroups,
        rule: rule ?? this.rule,
        previewEmployees: previewEmployees ?? this.previewEmployees,
        matchCount: matchCount ?? this.matchCount,
        totalAssignedCount: totalAssignedCount ?? this.totalAssignedCount,
        previewTotal: previewTotal ?? this.previewTotal,
        previewPage: previewPage ?? this.previewPage,
        previewView: previewView ?? this.previewView,
        previewSearch: previewSearch ?? this.previewSearch,
        isPreviewLoading: isPreviewLoading ?? this.isPreviewLoading,
        previewStale: previewStale ?? this.previewStale,
        dirty: dirty ?? this.dirty,
        refreshGeneration: refreshGeneration ?? this.refreshGeneration,
        blockedEmployeeCount: blockedEmployeeCount ?? this.blockedEmployeeCount,
        draftObserverIds: draftObserverIds ?? this.draftObserverIds,
        conflictingObserverIds:
            conflictingObserverIds ?? this.conflictingObserverIds,
        isLoading: isLoading ?? this.isLoading,
        isSaving: isSaving ?? this.isSaving,
        isPublishing: isPublishing ?? this.isPublishing,
        assignedCount:
            clearAssignedCount ? null : assignedCount ?? this.assignedCount,
        error: error,
        message: message,
        loadedCourseId: loadedCourseId ?? this.loadedCourseId,
      );
}

class AssignmentNotifier extends StateNotifier<AssignmentState> {
  final Ref ref;
  int _request = 0;
  int _previewRequest = 0;
  Timer? _previewTimer;
  String? _baseline;
  String? _expectedUpdatedAt;
  void dismissMessage() {
    state = state.copyWith(error: state.error);
  }

  void clearForAuthChange() {
    ++_request;
    ++_previewRequest;
    _previewTimer?.cancel();
    _baseline = null;
    _expectedUpdatedAt = null;
    state = const AssignmentState();
  }

  http.Client get _client => ref.read(assignmentHttpClientProvider);

  AssignmentNotifier(this.ref) : super(AssignmentState()) {
    ref.onDispose(() => _previewTimer?.cancel());
  }

  Future<void> fetchOptions() async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await _client.get(
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
    final courseId = state.loadedCourseId;
    if (courseId != null) await refreshAssignmentWorkspace(courseId);
  }

  Future<Map<String, dynamic>> _read(String url) async {
    final response = await _client.get(Uri.parse(url),
        headers: ref.read(trainerAuthHeadersProvider));
    if (response.statusCode == 401 || response.statusCode == 403)
      throw const AssignmentSessionExpired();
    if (response.statusCode != 200)
      throw Exception(
          'Refresh failed (${response.statusCode}). Sign in again if your session expired.');
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> refreshAssignmentWorkspace(String courseId,
      {bool initial = false}) async {
    final serial = ++_request;
    ++_previewRequest;
    if (initial) {
      _baseline = null;
      _expectedUpdatedAt = null;
    }
    state = initial
        ? AssignmentState(loadedCourseId: courseId, isLoading: true)
        : state.copyWith(isLoading: true);
    final errors = <String>[];
    bool sessionExpired = false;
    Map<String, dynamic>? saved;
    AssignmentOptions? options;
    List<SavedAssignmentGroup>? groups;
    await Future.wait([
      () async {
        try {
          options = AssignmentOptions.fromJson(
              await _read(AppConstants.assignmentOptionsEndpoint));
        } catch (e) {
          sessionExpired = sessionExpired || e is AssignmentSessionExpired;
          errors.add('Employee options could not be refreshed.');
        }
      }(),
      () async {
        try {
          saved = await _read(AppConstants.courseAssignmentEndpoint(courseId));
        } catch (e) {
          sessionExpired = sessionExpired || e is AssignmentSessionExpired;
          errors
              .add('Saved rule and assignment totals could not be refreshed.');
        }
      }(),
      () async {
        try {
          final result = await _client.get(
              Uri.parse(AppConstants.savedAssignmentGroupsEndpoint),
              headers: ref.read(trainerAuthHeadersProvider));
          if (result.statusCode == 401 || result.statusCode == 403)
            sessionExpired = true;
          if (result.statusCode != 200)
            throw Exception('Saved groups unavailable');
          groups = (jsonDecode(result.body) as List)
              .map((e) =>
                  SavedAssignmentGroup.fromJson(e as Map<String, dynamic>))
              .toList();
        } catch (_) {
          errors.add('Saved groups could not be refreshed.');
        }
      }(),
      () async {
        try {
          await ref.read(assignableCourseListProvider.notifier).fetchCourses();
          if (ref.read(assignableCourseListProvider).error != null)
            errors.add('Course status could not be refreshed.');
        } catch (_) {
          errors.add('Course status could not be refreshed.');
        }
      }(),
    ]);
    if (!mounted || serial != _request || state.loadedCourseId != courseId)
      return;
    if (sessionExpired) {
      state = const AssignmentState(
          error:
              'Your session or course access changed. Sign in again to reload assignment data.');
      return;
    }
    String? warning;
    AssignmentRule? freshRule;
    if (saved != null) {
      final baseline = jsonEncode(saved!['rule']);
      if (state.dirty && _baseline != null && baseline != _baseline)
        warning =
            'The saved rule changed in another session. Your edits are preserved; review the saved version before saving.';
      if (!state.dirty) {
        freshRule = _ruleForEditor(saved!['rule'] as Map<String, dynamic>);
        _baseline = baseline;
        _expectedUpdatedAt = saved!['rule']['updated_at']?.toString();
      }
    }
    state = state.copyWith(
        options: options,
        savedGroups: groups,
        rule: freshRule,
        totalAssignedCount: (saved?['total_assigned_count'] as num?)?.toInt(),
        matchCount:
            state.dirty ? null : (saved?['match_count'] as num?)?.toInt(),
        refreshGeneration: state.refreshGeneration + 1,
        isLoading: false,
        error: [...errors, if (warning != null) warning].isEmpty
            ? null
            : [...errors, if (warning != null) warning].join(' '));
    await fetchEmployeePreview();
  }

  Future<void> fetchSavedGroups() async {
    final serial = _request;
    try {
      final response = await _client.get(
        Uri.parse(AppConstants.savedAssignmentGroupsEndpoint),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (!mounted || serial != _request) return;
      if (response.statusCode == 200) {
        state = state.copyWith(
          message: state.message,
          error: state.error,
          savedGroups: (jsonDecode(response.body) as List? ?? [])
              .map((item) =>
                  SavedAssignmentGroup.fromJson(item as Map<String, dynamic>))
              .toList(),
        );
      } else {
        state = state.copyWith(
            error: 'Saved groups could not be refreshed.',
            message: state.message);
      }
    } catch (_) {
      if (!mounted || serial != _request) return;
      state = state.copyWith(
          error: 'Saved groups could not be refreshed.',
          message: state.message);
    }
  }

  Future<void> reloadSavedRule(String courseId) async {
    final serial = _request;
    state = state.copyWith(isLoading: true, error: state.error);
    try {
      final data = await _read(AppConstants.courseAssignmentEndpoint(courseId));
      if (!mounted || serial != _request || state.loadedCourseId != courseId)
        return;
      _applyAssignmentResponse(data, isLoading: false);
      await fetchEmployeePreview();
    } catch (error) {
      if (mounted && serial == _request && state.loadedCourseId == courseId)
        state = state.copyWith(isLoading: false, error: '$error');
    }
  }

  Future<void> loadForCourse(String courseId) async {
    if (state.loadedCourseId == courseId) return;
    await refreshAssignmentWorkspace(courseId, initial: true);
  }

  void updateDraftObservers(List<String> ids) {
    if (jsonEncode(ids) == jsonEncode(state.draftObserverIds)) return;
    state = state.copyWith(
        draftObserverIds: ids,
        previewStale: true,
        error: state.error,
        message: state.message);
    ++_previewRequest;
    _previewTimer?.cancel();
    _previewTimer =
        Timer(const Duration(milliseconds: 350), () => fetchEmployeePreview());
  }

  void updateRule(AssignmentRule rule) {
    state = state.copyWith(
        rule: rule, dirty: true, previewStale: true, clearAssignedCount: true);
    ++_previewRequest;
    _previewTimer?.cancel();
    _previewTimer = Timer(
        const Duration(milliseconds: 350), () => fetchEmployeePreview(page: 1));
  }

  Future<void> fetchEmployeePreview(
      {String? view, String? search, int? page}) async {
    final courseId = state.loadedCourseId;
    if (courseId == null) return;
    final serial = ++_previewRequest;
    final draft = jsonEncode(state.rule.toJson());
    state = state.copyWith(
        previewView: view,
        previewSearch: search,
        previewPage: page,
        isPreviewLoading: true,
        error: state.error,
        message: state.message);
    try {
      final uri = Uri.parse(
              '${AppConstants.courseAssignmentEndpoint(courseId)}/employee-preview')
          .replace(queryParameters: {
        'view': state.previewView,
        'search': state.previewSearch,
        'page': '${state.previewPage}',
        'page_size': '25'
      });
      final result = await _client.post(uri,
          headers: {
            ...ref.read(trainerAuthHeadersProvider),
            'Content-Type': 'application/json'
          },
          body: jsonEncode({
            ...jsonDecode(draft) as Map<String, dynamic>,
            'observer_employee_ids': state.draftObserverIds
          }));
      if (result.statusCode == 401 || result.statusCode == 403) {
        throw const AssignmentSessionExpired();
      }
      if (result.statusCode != 200)
        throw Exception(
            'Employee preview could not be refreshed (${result.statusCode}).');
      final data = jsonDecode(result.body) as Map<String, dynamic>;
      if (!mounted ||
          serial != _previewRequest ||
          state.loadedCourseId != courseId ||
          draft != jsonEncode(state.rule.toJson())) return;
      state = state.copyWith(
          previewEmployees: (data['employees'] as List)
              .map((e) => Employee.fromJson(e as Map<String, dynamic>))
              .toList(),
          previewTotal: (data['total'] as num).toInt(),
          blockedEmployeeCount:
              (data['blocked_employee_count'] as num?)?.toInt() ?? 0,
          conflictingObserverIds:
              (data['conflicting_observer_ids'] as List? ?? [])
                  .map((e) => e.toString())
                  .toList(),
          totalAssignedCount: (data['total_assigned_count'] as num).toInt(),
          matchCount:
              state.previewView == 'matching' && state.previewSearch.isEmpty
                  ? (data['total'] as num).toInt()
                  : null,
          previewStale: false,
          isPreviewLoading: false,
          error: state.error,
          message: state.message);
    } catch (e) {
      if (mounted &&
          serial == _previewRequest &&
          state.loadedCourseId == courseId) {
        if (e is AssignmentSessionExpired) {
          clearForAuthChange();
          state = const AssignmentState(
              error:
                  'Your session or course access changed. Sign in again to reload assignment data.');
        } else {
          state = state.copyWith(
              isPreviewLoading: false,
              previewStale: true,
              error: '$e',
              message: state.message);
        }
      }
    }
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
    final operationRequest = _request;
    if (state.loadedCourseId != courseId ||
        state.isSaving ||
        state.isPublishing ||
        state.isLoading) return;
    await fetchEmployeePreview();
    if (state.loadedCourseId != courseId || operationRequest != _request)
      return;
    if (state.previewStale) {
      state = state.copyWith(
          error: 'Refresh the employee preview before saving or publishing.');
      return;
    }
    if (state.conflictingObserverIds.isNotEmpty) {
      final names = state.options.employees
          .where((e) => state.conflictingObserverIds.contains(e.employeeId))
          .map((e) => e.name)
          .join(', ');
      state = state.copyWith(
          error:
              '${names.isEmpty ? "Selected employees" : names} are selected as both employees and Observers for this course. Remove the conflicting selection before continuing.');
      return;
    }
    final validationError = _groupValidationError(state.rule);
    if (validationError != null) {
      state = state.copyWith(error: validationError);
      return;
    }
    if (state.isSaving ||
        state.isPublishing ||
        state.isLoading ||
        state.loadedCourseId != courseId) return;
    state = state.copyWith(isSaving: true);
    try {
      final ruleToSave = await _persistReusableGroups(state.rule);
      if (!mounted ||
          state.loadedCourseId != courseId ||
          operationRequest != _request) return;
      final response = await _client.put(
        Uri.parse(AppConstants.courseAssignmentEndpoint(courseId)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
        body: jsonEncode({
          ...ruleToSave.toJson(),
          if (_expectedUpdatedAt != null)
            'expected_updated_at': _expectedUpdatedAt
        }),
      );
      if (!mounted ||
          state.loadedCourseId != courseId ||
          operationRequest != _request) return;
      if (response.statusCode == 200) {
        _applyAssignmentResponse(
            jsonDecode(response.body) as Map<String, dynamic>,
            isSaving: false,
            message: 'Assignment rule saved.');
        await fetchSavedGroups();
        await fetchEmployeePreview();
      } else {
        final decoded = jsonDecode(response.body);
        state = state.copyWith(
          isSaving: false,
          error:
              decoded['detail']?.toString() ?? 'Failed to save assignment rule',
        );
      }
    } catch (e) {
      if (mounted &&
          state.loadedCourseId == courseId &&
          operationRequest == _request)
        state = state.copyWith(
            isSaving: false, error: e.toString(), message: state.message);
    }
  }

  Future<void> publish(String courseId) async {
    final operationRequest = _request;
    if (state.loadedCourseId != courseId ||
        state.isSaving ||
        state.isPublishing ||
        state.isLoading) return;
    await fetchEmployeePreview();
    if (state.loadedCourseId != courseId || operationRequest != _request)
      return;
    if (state.previewStale) {
      state = state.copyWith(
          error: 'Refresh the employee preview before saving or publishing.');
      return;
    }
    if (state.conflictingObserverIds.isNotEmpty) {
      final names = state.options.employees
          .where((e) => state.conflictingObserverIds.contains(e.employeeId))
          .map((e) => e.name)
          .join(', ');
      state = state.copyWith(
          error:
              '${names.isEmpty ? "Selected employees" : names} are selected as both employees and Observers for this course. Remove the conflicting selection before continuing.');
      return;
    }
    final validationError = _groupValidationError(state.rule);
    if (validationError != null) {
      state = state.copyWith(error: validationError);
      return;
    }
    if (state.isSaving ||
        state.isPublishing ||
        state.isLoading ||
        state.loadedCourseId != courseId) return;
    state = state.copyWith(isPublishing: true);
    try {
      final ruleToPublish = await _persistReusableGroups(state.rule);
      if (!mounted ||
          state.loadedCourseId != courseId ||
          operationRequest != _request) return;
      final response = await _client.post(
        Uri.parse(AppConstants.publishCourseAssignmentEndpoint(courseId)),
        headers: {
          'Content-Type': 'application/json',
          ...ref.read(trainerAuthHeadersProvider),
        },
        body: jsonEncode({
          ...ruleToPublish.toJson(),
          if (_expectedUpdatedAt != null)
            'expected_updated_at': _expectedUpdatedAt
        }),
      );
      if (!mounted ||
          state.loadedCourseId != courseId ||
          operationRequest != _request) return;
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        final total = decoded['total_assigned_count'] ?? 0;
        final assignedCount = decoded['assigned_count'] ?? 0;
        final removedCount = decoded['removed_count'] ?? 0;
        final reactivatedCount = decoded['reactivated_count'] ?? 0;
        final deadlineUpdateCount = decoded['deadline_update_count'] ?? 0;
        _applyAssignmentResponse(
          decoded,
          isPublishing: false,
          message:
              'Course published and assigned successfully. $total employees currently assigned. '
              '$assignedCount new assignments created, $reactivatedCount restored, $removedCount removed, '
              '$deadlineUpdateCount deadlines updated.',
          assignedCount: (decoded['assigned_count'] as num?)?.toInt(),
        );
        try {
          await ref.read(assignableCourseListProvider.notifier).fetchCourses();
          await ref.read(performanceReportProvider.notifier).refresh();
        } catch (_) {
          state = state.copyWith(
              error:
                  'The operation succeeded, but course/report data could not be refreshed. Click Refresh.',
              message: state.message);
        }
        await fetchSavedGroups();
        await fetchEmployeePreview();
      } else {
        final decoded = jsonDecode(response.body);
        state = state.copyWith(
          isPublishing: false,
          error:
              decoded['detail']?.toString() ?? 'Failed to publish assignment',
        );
      }
    } catch (e) {
      if (mounted &&
          state.loadedCourseId == courseId &&
          operationRequest == _request)
        state = state.copyWith(
            isPublishing: false, error: e.toString(), message: state.message);
    }
  }

  Future<AssignmentRule> _persistReusableGroups(AssignmentRule rule) async {
    final originalCourseId = state.loadedCourseId;
    final originalRequest = _request;
    Future<AssignmentGroup> persist(
      AssignmentGroup group,
      String groupType,
      int index,
    ) async {
      if (group.isEmpty) return group;
      final name = group.name.trim().isNotEmpty
          ? group.name.trim()
          : '${groupType == 'include' ? 'Employee selection' : 'Employee exclusion'} group '
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
          ? await _client.post(
              Uri.parse(AppConstants.savedAssignmentGroupsEndpoint),
              headers: {
                'Content-Type': 'application/json',
                ...ref.read(trainerAuthHeadersProvider),
              },
              body: jsonEncode(payload),
            )
          : await _client.put(
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
    if (mounted &&
        state.loadedCourseId == originalCourseId &&
        originalRequest == _request) state = state.copyWith(rule: updatedRule);
    return updatedRule;
  }

  Future<void> disable(String courseId) async {
    final operationRequest = _request;
    if (state.isSaving ||
        state.isPublishing ||
        state.isLoading ||
        state.loadedCourseId != courseId) return;
    state = state.copyWith(isPublishing: true);
    try {
      final response = await _client.post(
        Uri.parse(AppConstants.disableCourseAssignmentEndpoint(courseId)),
        headers: ref.read(trainerAuthHeadersProvider),
      );
      if (!mounted ||
          state.loadedCourseId != courseId ||
          operationRequest != _request) return;
      if (response.statusCode == 200) {
        _applyAssignmentResponse(
          jsonDecode(response.body) as Map<String, dynamic>,
          isPublishing: false,
          message: 'Course disabled for employees. Progress is preserved.',
        );
        try {
          await ref.read(assignableCourseListProvider.notifier).fetchCourses();
          await ref.read(performanceReportProvider.notifier).refresh();
        } catch (_) {
          state = state.copyWith(
              error:
                  'The operation succeeded, but course/report data could not be refreshed. Click Refresh.',
              message: state.message);
        }
        await fetchEmployeePreview();
      } else {
        final decoded = jsonDecode(response.body);
        state = state.copyWith(
          isPublishing: false,
          error: decoded['detail']?.toString() ?? 'Failed to disable course',
        );
      }
    } catch (e) {
      if (mounted &&
          state.loadedCourseId == courseId &&
          operationRequest == _request)
        state = state.copyWith(
            isPublishing: false, error: e.toString(), message: state.message);
    }
  }

  AssignmentRule _ruleForEditor(Map<String, dynamic> rawRule) {
    final rule = AssignmentRule.fromJson(rawRule);
    // Only an unsaved rule gets the new UI default; persisted relative
    // deadlines (including legacy records) keep their original meaning.
    return rawRule['updated_at'] == null && rawRule['published_at'] == null
        ? rule.copyWith(deadlineMode: 'fixed')
        : rule;
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
    _baseline = jsonEncode(decoded['rule']);
    _expectedUpdatedAt = decoded['rule']['updated_at']?.toString();
    state = state.copyWith(
      rule: _ruleForEditor(decoded['rule'] as Map<String, dynamic>),
      dirty: false,
      totalAssignedCount: (decoded['total_assigned_count'] as num?)?.toInt(),
      refreshGeneration: state.refreshGeneration + 1,
      matchCount: (decoded['match_count'] as num?)?.toInt() ?? 0,
      assignedCount: assignedCount,
      previewStale: true,
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
  final notifier = AssignmentNotifier(ref);
  ref.listen(trainerAuthProvider, (previous, next) {
    if (previous?.trainer?.trainerId != next.trainer?.trainerId ||
        previous?.token != next.token) notifier.clearForAuthChange();
  });
  return notifier;
});

final assignmentHttpClientProvider = Provider<http.Client>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return client;
});

class AssignmentSessionExpired implements Exception {
  const AssignmentSessionExpired();
}
