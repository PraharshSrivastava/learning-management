part of '../employee_providers.dart';

final currentEmployeeTabProvider = StateProvider<int>((ref) => 0);

Map<String, String> _authHeaders(String? token) => {
      'Content-Type': 'application/json',
      'X-LMS-App': 'employee',
      if (token != null) 'Authorization': 'Bearer $token',
    };

class EmployeeAuthState {
  final List<Employee> employees;
  final Employee? employee;
  final String? token;
  final bool isLoading;
  final String? error;

  EmployeeAuthState({
    this.employees = const [],
    this.employee,
    this.token,
    this.isLoading = false,
    this.error,
  });

  bool get isAuthenticated => employee != null;

  EmployeeAuthState copyWith({
    List<Employee>? employees,
    Employee? employee,
    String? token,
    bool? isLoading,
    String? error,
    bool clearSession = false,
  }) {
    return EmployeeAuthState(
      employees: employees ?? this.employees,
      employee: clearSession ? null : (employee ?? this.employee),
      token: clearSession ? null : (token ?? this.token),
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class EmployeeAuthNotifier extends StateNotifier<EmployeeAuthState> {
  EmployeeAuthNotifier({bool autoFetch = true}) : super(EmployeeAuthState()) {
    if (autoFetch) {
      fetchHubSession();
    }
  }

  Future<void> fetchHubSession() async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await http.get(
        Uri.parse(AppConstants.hubSessionEndpoint),
        headers: const {'X-LMS-App': 'employee'},
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        final employeeJson = decoded['employee'];
        if (decoded['authenticated'] == true &&
            employeeJson is Map<String, dynamic>) {
          state = state.copyWith(
            employee: Employee.fromJson(employeeJson),
            token: null,
            isLoading: false,
          );
          return;
        }
      }
      await fetchEmployees();
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
      await fetchEmployees();
    }
  }

  Future<void> fetchEmployees() async {
    state = state.copyWith(isLoading: true);
    try {
      final response =
          await http.get(Uri.parse(AppConstants.employeesEndpoint));
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as List<dynamic>;
        final employees = decoded
            .map((item) => Employee.fromJson(item as Map<String, dynamic>))
            .toList();
        state = state.copyWith(employees: employees, isLoading: false);
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

  Future<void> login(Employee employee) async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await http.post(
        Uri.parse(AppConstants.localEmployeeLoginEndpoint),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'employee_id': employee.employeeId}),
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        state = state.copyWith(
          employee:
              Employee.fromJson(decoded['employee'] as Map<String, dynamic>),
          token: decoded['token']?.toString(),
          isLoading: false,
        );
      } else {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        state = state.copyWith(
          isLoading: false,
          error: decoded['detail']?.toString() ?? 'Login failed',
        );
      }
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  void logout() {
    http.post(
      Uri.parse(AppConstants.hubLogoutEndpoint),
      headers: const {'X-LMS-App': 'employee'},
    );
    state = state.copyWith(clearSession: true);
    fetchEmployees();
  }
}

final employeeAuthProvider =
    StateNotifierProvider<EmployeeAuthNotifier, EmployeeAuthState>((ref) {
  return EmployeeAuthNotifier();
});
