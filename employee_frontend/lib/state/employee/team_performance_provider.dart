part of '../employee_providers.dart';

class TeamPerformanceState {
  final Map<String, dynamic> data;
  final bool isLoading;
  final String? error;

  const TeamPerformanceState({
    this.data = const {},
    this.isLoading = false,
    this.error,
  });
}

class TeamPerformanceNotifier extends StateNotifier<TeamPerformanceState> {
  final Ref ref;

  TeamPerformanceNotifier(this.ref) : super(const TeamPerformanceState());

  Future<void> fetch({String? status}) async {
    state = const TeamPerformanceState(isLoading: true);
    try {
      final uri = Uri.parse(AppConstants.teamPerformanceEndpoint).replace(
        queryParameters:
            status == null || status.isEmpty || status == 'assigned'
                ? null
                : {'status': status},
      );
      final token = ref.read(employeeAuthProvider).token;
      final response = await http.get(uri, headers: _authHeaders(token));
      if (response.statusCode != 200) {
        state = TeamPerformanceState(
          error: 'Unable to load team report (${response.statusCode})',
        );
        return;
      }
      state = TeamPerformanceState(
        data: jsonDecode(response.body) as Map<String, dynamic>,
      );
    } catch (error) {
      state = TeamPerformanceState(error: error.toString());
    }
  }
}

final teamPerformanceProvider =
    StateNotifierProvider<TeamPerformanceNotifier, TeamPerformanceState>((ref) {
  return TeamPerformanceNotifier(ref);
});
