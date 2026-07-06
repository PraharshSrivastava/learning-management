import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

import '../constants.dart';
import '../models/models.dart';

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
  WebSocketChannel? _channel;
  bool _isDisposed = false;

  EmployeeCourseListNotifier() : super(EmployeeCourseListState()) {
    _connectWebSocket();
  }

  void _connectWebSocket() {
    if (_isDisposed) return;
    
    state = EmployeeCourseListState(courses: state.courses, isLoading: true);
    try {
      final wsUrl = Uri.parse(AppConstants.employeeCoursesWsEndpoint);
      _channel = WebSocketChannel.connect(wsUrl);
      
      _channel!.stream.listen(
        (message) {
          try {
            final List<dynamic> decoded = jsonDecode(message);
            final List<Course> courseList = decoded.map((item) => Course.fromPublishedJson(item)).toList();
            if (!_isDisposed) {
              state = EmployeeCourseListState(courses: courseList, isLoading: false);
            }
          } catch (e) {
            if (!_isDisposed) {
              state = EmployeeCourseListState(courses: state.courses, isLoading: false, error: 'Failed to parse data');
            }
          }
        },
        onError: (error) {
          if (!_isDisposed) {
            state = EmployeeCourseListState(courses: state.courses, isLoading: false, error: 'WebSocket Error: $error');
          }
          _scheduleReconnect();
        },
        onDone: () {
          _scheduleReconnect();
        },
      );
    } catch (e) {
      if (!_isDisposed) {
        state = EmployeeCourseListState(courses: state.courses, isLoading: false, error: e.toString());
      }
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_isDisposed) return;
    Future.delayed(const Duration(seconds: 5), () {
      _connectWebSocket();
    });
  }

  Future<void> updateModuleProgress(String courseId, int moduleNumber, Map<String, dynamic> payload) async {
    try {
      final url = Uri.parse('${AppConstants.employeeCoursesEndpoint}/$courseId/modules/$moduleNumber');
      final response = await http.put(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to update module progress: ${response.body}');
      }
      
      // The websocket will push the updated course list shortly, so we don't strictly need to manually mutate state here,
      // but it's fine to let the stream handle the update.
    } catch (e) {
      print('Error updating module progress: $e');
    }
  }

  @override
  void dispose() {
    _isDisposed = true;
    _channel?.sink.close();
    super.dispose();
  }

  Future<void> updateCourseStatus(String courseId, String status) async {
    try {
      final response = await http.put(
        Uri.parse(AppConstants.updateEmployeeCourseStatusEndpoint(courseId)),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'status': status}),
      );
      if (response.statusCode != 200) {
        throw Exception('Failed to update status');
      }
      // We don't need to fetch courses manually because the backend 
      // will broadcast the updated list through the WebSocket instantly!
    } catch (e) {
      rethrow;
    }
  }
}

final employeeCourseListProvider = StateNotifierProvider<EmployeeCourseListNotifier, EmployeeCourseListState>((ref) {
  return EmployeeCourseListNotifier();
});
