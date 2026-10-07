import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/state/trainer_providers.dart';
import 'package:frontend/data/models/models.dart';

class QuietAuth extends TrainerAuthNotifier {
  @override
  Future<void> fetchHubSession() async {}
}

class QuietCourses extends AssignableCourseListNotifier {
  int reloads = 0;
  QuietCourses(super.ref);
  @override
  Future<void> fetchCourses() async {
    reloads++;
  }
}

Map<String, dynamic> saved(String id, {int days = 7}) => {
      'rule': {
        'course_id': id,
        'include_all': true,
        'deadline_days': days,
        'updated_at': 'v1'
      },
      'match_count': 3,
      'total_assigned_count': 2,
      'preview_employees': []
    };
http.Response jsonResponse(Object value, {int status = 200}) =>
    http.Response(jsonEncode(value), status,
        headers: {'content-type': 'application/json'});
ProviderContainer container(http.Client client) =>
    ProviderContainer(overrides: [
      assignmentHttpClientProvider.overrideWithValue(client),
      trainerAuthProvider.overrideWith((ref) => QuietAuth()),
      trainerAuthHeadersProvider.overrideWithValue({'X-LMS-App': 'trainer'}),
      assignableCourseListProvider.overrideWith((ref) => QuietCourses(ref)),
    ]);
void main() {
  setUp(() {
    dotenv.loadFromString(envString: 'API_BASE_URL=http://localhost:8000');
  });
  test(
      'same-course Refresh reloads rule/options/groups/counts and preserves edited deadline',
      () async {
    final requests = <http.Request>[];
    var version = 1;
    final c = container(MockClient((r) async {
      requests.add(r);
      if (r.url.path.endsWith('/options'))
        return jsonResponse({
          'departments': ['Department $version'],
          'employees': []
        });
      if (r.url.path.endsWith('/saved-groups')) return jsonResponse([]);
      if (r.url.path.endsWith('/employee-preview')) {
        expect(r.headers['X-LMS-App'], 'trainer');
        return jsonResponse(
            {'total': 3, 'total_assigned_count': version + 1, 'employees': []});
      }
      return jsonResponse(saved('one'));
    }));
    addTearDown(c.dispose);
    final n = c.read(assignmentProvider.notifier);
    await n.loadForCourse('one');
    n.updateRule(c.read(assignmentProvider).rule.copyWith(deadlineDays: 15));
    version = 2;
    await n.refreshOptionsAndGroups();
    final state = c.read(assignmentProvider);
    expect(state.rule.deadlineDays, 15);
    expect(state.dirty, isTrue);
    expect(state.options.departments, ['Department 2']);
    expect(state.totalAssignedCount, 3);
    expect(state.refreshGeneration, 2);
    expect(requests.where((r) => r.url.path.endsWith('/assignment')).length, 2);
    expect(
        requests.where((r) => r.url.path.endsWith('/saved-groups')).length, 2);
    expect(
        requests
            .where((r) => r.url.path.endsWith('/employee-preview'))
            .last
            .body,
        contains('15'));
    expect(requests.where((r) => r.method == 'PUT'), isEmpty);
    expect(
        (c.read(assignableCourseListProvider.notifier) as QuietCourses).reloads,
        2);
  });
  test(
      'partial refresh failure is visible and does not erase last employee options',
      () async {
    var fail = false;
    final c = container(MockClient((r) async {
      if (r.url.path.endsWith('/options'))
        return jsonResponse(
            fail
                ? {}
                : {
                    'departments': ['Risk']
                  },
            status: fail ? 503 : 200);
      if (r.url.path.endsWith('/saved-groups')) return jsonResponse([]);
      if (r.url.path.endsWith('/employee-preview'))
        return jsonResponse(
            {'total': 3, 'total_assigned_count': 2, 'employees': []});
      return jsonResponse(saved('one'));
    }));
    addTearDown(c.dispose);
    final n = c.read(assignmentProvider.notifier);
    await n.loadForCourse('one');
    fail = true;
    await n.refreshOptionsAndGroups();
    expect(c.read(assignmentProvider).options.departments, ['Risk']);
    expect(c.read(assignmentProvider).error, contains('Employee options'));
    expect(c.read(assignmentProvider).isLoading, isFalse);
  });
  test('earlier course response cannot replace newly selected course',
      () async {
    final gate = Completer<http.Response>();
    final c = container(MockClient((r) async {
      if (r.url.path.endsWith('/options')) return jsonResponse({});
      if (r.url.path.endsWith('/saved-groups')) return jsonResponse([]);
      if (r.url.path.endsWith('/employee-preview'))
        return jsonResponse(
            {'total': 0, 'total_assigned_count': 0, 'employees': []});
      if (r.url.path.contains('/one/')) return gate.future;
      return jsonResponse(saved('two', days: 12));
    }));
    addTearDown(c.dispose);
    final n = c.read(assignmentProvider.notifier);
    final old = n.loadForCourse('one');
    await Future<void>.delayed(Duration.zero);
    await n.loadForCourse('two');
    gate.complete(jsonResponse(saved('one', days: 3)));
    await old;
    expect(c.read(assignmentProvider).loadedCourseId, 'two');
    expect(c.read(assignmentProvider).rule.deadlineDays, 12);
  });
  test(
      'assignment count can be cleared rather than retained from old publication',
      () {
    final state = const AssignmentState(assignedCount: 25)
        .copyWith(clearAssignedCount: true);
    expect(state.assignedCount, isNull);
  });
  test(
      'fixed deadline model survives roundtrip and relative mode clears date payload',
      () {
    final rule = AssignmentRule.fromJson({
      'deadline_mode': 'fixed',
      'deadline_date': '2099-10-31',
      'deadline_days': 7
    });
    expect(rule.toJson()['deadline_date'], '2099-10-31');
    expect(rule.copyWith(deadlineMode: 'relative').toJson()['deadline_date'],
        isNull);
  });
  test('expired course access clears cached employee data', () async {
    var expired = false;
    final c = container(MockClient((r) async {
      if (expired) return jsonResponse({}, status: 401);
      if (r.url.path.endsWith('/options'))
        return jsonResponse({
          'departments': ['Risk']
        });
      if (r.url.path.endsWith('/saved-groups')) return jsonResponse([]);
      if (r.url.path.endsWith('/employee-preview'))
        return jsonResponse(
            {'total': 3, 'total_assigned_count': 2, 'employees': []});
      return jsonResponse(saved('one'));
    }));
    addTearDown(c.dispose);
    final n = c.read(assignmentProvider.notifier);
    await n.loadForCourse('one');
    expired = true;
    await n.refreshOptionsAndGroups();
    expect(c.read(assignmentProvider).options.departments, isEmpty);
    expect(c.read(assignmentProvider).totalAssignedCount, 0);
    expect(c.read(assignmentProvider).error, contains('Sign in again'));
  });

  test(
      'unsaved Observer conflicts block publication before any assignment mutation',
      () async {
    int mutations = 0;
    final c = container(MockClient((r) async {
      if (r.url.path.endsWith('/options'))
        return jsonResponse({
          'employees': [
            {'employee_id': 'observer', 'name': 'Aditya'}
          ]
        });
      if (r.url.path.endsWith('/saved-groups')) return jsonResponse([]);
      if (r.url.path.endsWith('/employee-preview')) {
        final payload = jsonDecode(r.body) as Map<String, dynamic>;
        final conflicts = (payload['observer_employee_ids'] as List).isEmpty
            ? []
            : ['observer'];
        return jsonResponse({
          'total': 3,
          'total_assigned_count': 2,
          'employees': [],
          'conflicting_observer_ids': conflicts
        });
      }
      if (r.method != 'GET') mutations++;
      return jsonResponse(saved('one'));
    }));
    addTearDown(c.dispose);
    final n = c.read(assignmentProvider.notifier);
    await n.loadForCourse('one');
    n.updateDraftObservers(['observer']);
    await n.publish('one');
    expect(mutations, 0);
    expect(c.read(assignmentProvider).error, contains('Aditya'));
    expect(c.read(assignmentProvider).error, contains('Observers'));
  });
}
