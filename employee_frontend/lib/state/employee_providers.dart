import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

import 'package:employee_frontend/core/config/app_constants.dart';
import 'package:employee_frontend/data/models/models.dart';



part 'employee/auth_providers.dart';
part 'employee/hub_providers.dart';
part 'employee/course_progress_providers.dart';
part 'employee/team_performance_provider.dart';
part 'employee/lms_access_providers.dart';
part 'employee/performance_filter.dart';
part 'employee/performance_report_providers.dart';

final employeeAuthHeadersProvider = Provider<Map<String, String>>((ref) {
  final token = ref.watch(employeeAuthProvider).token;
  return {'X-LMS-App': 'employee', if (token != null) 'Authorization': 'Bearer $token'};
});
