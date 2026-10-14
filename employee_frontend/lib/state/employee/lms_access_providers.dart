part of '../employee_providers.dart';

class LmsAccessNotifier extends StateNotifier<Map<String, dynamic>> {
  final Ref ref;
  Timer? _timer;
  int _request = 0;
  LmsAccessNotifier(this.ref) : super(const {}) {
    AppConstants.mediaTicket = null;
    Future.microtask(refresh);
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => refresh());
  }
  Future<void> refresh() async {
    final request = ++_request;
    if (!ref.read(employeeAuthProvider).isAuthenticated) return;
    try {
      final response = await http.get(
        Uri.parse('${AppConstants.apiBaseUrl}/api/lms/me?app=employee'),
        headers: ref.read(employeeAuthHeadersProvider),
      );
      final media = response.statusCode == 200 ? await http.get(
        Uri.parse('${AppConstants.apiBaseUrl}/api/media-ticket?app=employee'), headers: ref.read(employeeAuthHeadersProvider)) : null;
      if (!mounted || request != _request) return;
      AppConstants.mediaTicket = media?.statusCode == 200 ? (jsonDecode(media!.body) as Map)['ticket']?.toString() : null;
      final next = response.statusCode == 200
          ? jsonDecode(response.body) as Map<String, dynamic> : <String, dynamic>{};
      if (jsonEncode(next) != jsonEncode(state)) state = next;
    } catch (_) {
      if (mounted && request == _request) { AppConstants.mediaTicket = null; state = const {}; }
    }
  }
  @override
  void dispose() { _timer?.cancel(); _request++; super.dispose(); }
}

final lmsAccessProvider = StateNotifierProvider<LmsAccessNotifier, Map<String, dynamic>>((ref) {
  ref.watch(employeeAuthProvider.select((s) => s.employee?.employeeId));
  ref.watch(employeeAuthProvider.select((s) => s.token));
  return LmsAccessNotifier(ref);
});

final reportViewsProvider = Provider<List<String>>((ref) =>
    (ref.watch(lmsAccessProvider)['performance_views'] as List? ?? const [])
        .map((v) => v.toString()).toList());
