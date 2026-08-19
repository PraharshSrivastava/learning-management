part of '../trainer_providers.dart';

class HubSessionState {
  final bool isLoading;
  final bool isAuthenticated;
  final bool isLocalDevMode;
  final String? email;
  final String? error;

  const HubSessionState({
    this.isLoading = true,
    this.isAuthenticated = false,
    this.isLocalDevMode = false,
    this.email,
    this.error,
  });

  HubSessionState copyWith({
    bool? isLoading,
    bool? isAuthenticated,
    bool? isLocalDevMode,
    String? email,
    String? error,
  }) {
    return HubSessionState(
      isLoading: isLoading ?? this.isLoading,
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      isLocalDevMode: isLocalDevMode ?? this.isLocalDevMode,
      email: email ?? this.email,
      error: error,
    );
  }
}

class HubSessionNotifier extends StateNotifier<HubSessionState> {
  HubSessionNotifier({bool autoFetch = true}) : super(const HubSessionState()) {
    if (autoFetch) {
      refresh();
    }
  }

  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final response = await http.get(
        Uri.parse(AppConstants.hubSessionEndpoint),
        headers: const {'X-LMS-App': 'trainer'},
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        final authenticated = decoded['authenticated'] == true;
        state = HubSessionState(
          isLoading: false,
          isAuthenticated: authenticated,
          isLocalDevMode: decoded['local_dev_mode'] == true,
          email: authenticated ? decoded['email']?.toString() : null,
        );
        return;
      }
      state = const HubSessionState(
        isLoading: false,
        error: 'Open this application from the Hub dashboard.',
      );
    } catch (error) {
      state = HubSessionState(isLoading: false, error: error.toString());
    }
  }

  Future<void> logout() async {
    await http.post(
      Uri.parse(AppConstants.hubLogoutEndpoint),
      headers: const {'X-LMS-App': 'trainer'},
    );
    state = const HubSessionState(
      isLoading: false,
      error: 'Open this application from the Hub dashboard.',
    );
  }
}

final hubSessionProvider =
    StateNotifierProvider<HubSessionNotifier, HubSessionState>((ref) {
  return HubSessionNotifier();
});
