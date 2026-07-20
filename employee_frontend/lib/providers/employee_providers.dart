import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

import '../constants.dart';
import '../models/models.dart';

final currentEmployeeTabProvider = StateProvider<int>((ref) => 0);

Map<String, String> _authHeaders(String token) => {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };

class DemoAuthState {
  final List<Employee> employees;
  final Employee? employee;
  final String? token;
  final bool isLoading;
  final String? error;

  DemoAuthState({
    this.employees = const [],
    this.employee,
    this.token,
    this.isLoading = false,
    this.error,
  });

  bool get isAuthenticated => employee != null && token != null;

  DemoAuthState copyWith({
    List<Employee>? employees,
    Employee? employee,
    String? token,
    bool? isLoading,
    String? error,
    bool clearSession = false,
  }) {
    return DemoAuthState(
      employees: employees ?? this.employees,
      employee: clearSession ? null : (employee ?? this.employee),
      token: clearSession ? null : (token ?? this.token),
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class DemoAuthNotifier extends StateNotifier<DemoAuthState> {
  DemoAuthNotifier({bool autoFetch = true}) : super(DemoAuthState()) {
    if (autoFetch) {
      fetchEmployees();
    }
  }

  Future<void> fetchEmployees() async {
    state = state.copyWith(isLoading: true);
    try {
      final response = await http.get(Uri.parse(AppConstants.employeesEndpoint));
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
        Uri.parse(AppConstants.demoLoginEndpoint),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'employee_id': employee.id}),
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        state = state.copyWith(
          employee: Employee.fromJson(decoded['employee'] as Map<String, dynamic>),
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
    state = state.copyWith(clearSession: true);
  }
}

final demoAuthProvider = StateNotifierProvider<DemoAuthNotifier, DemoAuthState>((ref) {
  return DemoAuthNotifier();
});

class EmployeeCourseListState {
  final List<Course> courses;
  final bool isLoading;
  final String? error;

  EmployeeCourseListState({
    this.courses = const [],
    this.isLoading = false,
    this.error,
  });
}

class EmployeeCourseListNotifier extends StateNotifier<EmployeeCourseListState> {
  final String? token;
  WebSocketChannel? _channel;
  bool _isDisposed = false;

  EmployeeCourseListNotifier({required this.token}) : super(EmployeeCourseListState()) {
    if (token != null) {
      fetchCourses();
      _connectWebSocket();
    }
  }

  void _connectWebSocket() {
    if (_isDisposed || token == null) return;

    state = EmployeeCourseListState(courses: state.courses, isLoading: true);
    try {
      final wsUrl = Uri.parse(AppConstants.myCoursesWsEndpoint(token!));
      _channel = WebSocketChannel.connect(wsUrl);

      _channel!.stream.listen(
        (message) {
          try {
            final decoded = jsonDecode(message) as List<dynamic>;
            final courseList = decoded
                .map((item) => Course.fromPublishedJson(item as Map<String, dynamic>))
                .toList();
            if (!_isDisposed) {
              state = EmployeeCourseListState(courses: courseList, isLoading: false);
            }
          } catch (_) {
            if (!_isDisposed) {
              state = EmployeeCourseListState(
                courses: state.courses,
                isLoading: false,
                error: 'Failed to parse learning data',
              );
            }
          }
        },
        onError: (error) {
          if (!_isDisposed) {
            state = EmployeeCourseListState(
              courses: state.courses,
              isLoading: false,
              error: 'WebSocket error: $error',
            );
          }
          _scheduleReconnect();
        },
        onDone: _scheduleReconnect,
      );
    } catch (e) {
      if (!_isDisposed) {
        state = EmployeeCourseListState(
          courses: state.courses,
          isLoading: false,
          error: e.toString(),
        );
      }
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_isDisposed || token == null) return;
    Future.delayed(const Duration(seconds: 5), () {
      _connectWebSocket();
    });
  }

  Future<void> fetchCourses() async {
    if (token == null) return;
    state = EmployeeCourseListState(courses: state.courses, isLoading: true);
    try {
      final response = await http.get(
        Uri.parse(AppConstants.myCoursesEndpoint),
        headers: _authHeaders(token!),
      );
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body) as List<dynamic>;
        final courseList = decoded
            .map((item) => Course.fromPublishedJson(item as Map<String, dynamic>))
            .toList();
        state = EmployeeCourseListState(courses: courseList, isLoading: false);
      } else {
        state = EmployeeCourseListState(
          courses: state.courses,
          isLoading: false,
          error: 'Server returned ${response.statusCode}',
        );
      }
    } catch (e) {
      state = EmployeeCourseListState(
        courses: state.courses,
        isLoading: false,
        error: e.toString(),
      );
    }
  }

  Future<void> updateModuleProgress(
    String courseId,
    int moduleNumber,
    Map<String, dynamic> payload,
  ) async {
    if (token == null) return;
    try {
      final response = await http.put(
        Uri.parse(AppConstants.updateMyModuleProgressEndpoint(courseId, moduleNumber)),
        headers: _authHeaders(token!),
        body: jsonEncode(payload),
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to update module progress: ${response.body}');
      }
    } catch (e) {
      debugPrint('Error updating module progress: $e');
    }
  }

  Future<void> updateCourseStatus(String courseId, String status) async {
    if (token == null) return;
    final response = await http.put(
      Uri.parse(AppConstants.updateMyCourseStatusEndpoint(courseId)),
      headers: _authHeaders(token!),
      body: jsonEncode({'status': status}),
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to update status');
    }
  }

  @override
  void dispose() {
    _isDisposed = true;
    _channel?.sink.close();
    super.dispose();
  }
}

final employeeCourseListProvider =
    StateNotifierProvider<EmployeeCourseListNotifier, EmployeeCourseListState>((ref) {
  final token = ref.watch(demoAuthProvider.select((state) => state.token));
  return EmployeeCourseListNotifier(token: token);
});
