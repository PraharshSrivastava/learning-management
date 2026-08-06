part of '../trainer_providers.dart';

class TrainerAuthState {
  final List<Trainer> trainers;
  final Trainer? trainer;
  final String? token;
  final bool isLoading;
  final String? error;

  const TrainerAuthState({
    this.trainers = const [],
    this.trainer,
    this.token,
    this.isLoading = false,
    this.error,
  });

  bool get isAuthenticated => trainer != null && token != null;

  TrainerAuthState copyWith({
    List<Trainer>? trainers,
    Trainer? trainer,
    String? token,
    bool? isLoading,
    String? error,
    bool clearSession = false,
  }) {
    return TrainerAuthState(
      trainers: trainers ?? this.trainers,
      trainer: clearSession ? null : (trainer ?? this.trainer),
      token: clearSession ? null : (token ?? this.token),
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class TrainerAuthNotifier extends StateNotifier<TrainerAuthState> {
  TrainerAuthNotifier() : super(const TrainerAuthState()) {
    fetchTrainers();
  }

  Future<void> fetchTrainers() async {
    state = state.copyWith(isLoading: true);
    try {
      final response =
          await http.get(Uri.parse(AppConstants.trainerListEndpoint));
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as List;
        state = state.copyWith(
          trainers: decoded
              .map((item) => Trainer.fromJson(item as Map<String, dynamic>))
              .toList(),
          isLoading: false,
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          error: 'Server returned ${response.statusCode}',
        );
      }
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> login(Trainer trainer) async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.trainerDemoLoginEndpoint),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'trainer_id': trainer.trainerId}),
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        state = state.copyWith(
          trainer: Trainer.fromJson(decoded['trainer'] as Map<String, dynamic>),
          token: decoded['token']?.toString(),
          isLoading: false,
        );
      } else {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        state = state.copyWith(
          isLoading: false,
          error: decoded['detail']?.toString() ?? 'Could not log in trainer.',
        );
      }
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  void logout() {
    state = state.copyWith(clearSession: true);
  }
}

final trainerAuthProvider =
    StateNotifierProvider<TrainerAuthNotifier, TrainerAuthState>((ref) {
  return TrainerAuthNotifier();
});

final trainerAuthHeadersProvider = Provider<Map<String, String>>((ref) {
  final token = ref.watch(trainerAuthProvider).token;
  return {
    if (token != null) 'Authorization': 'Bearer $token',
  };
});
