import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:frontend/data/models/models.dart';
import 'package:frontend/state/trainer_providers.dart';
import 'package:frontend/features/courses/course_actions_menu.dart';

class MenuAuth extends TrainerAuthNotifier {
  MenuAuth(String id) {
    state = TrainerAuthState(
        trainer: Trainer(trainerId: id, name: 'Trainer', status: 'active'),
        token: 'test');
  }
  @override
  Future<void> fetchHubSession() async {}
}

Course course(String state, {bool canDelete = false}) => Course(
    courseId: 'c',
    trainerId: 'owner',
    courseName: 'Course',
    courseDescription: '',
    courseObjective: '',
    courseDifficulty: '',
    language: '',
    targetAudience: '',
    modules: [],
    images: [],
    createdAt: '',
    lifecycleState: state,
    canDelete: canDelete);

void main() {
  for (final entry in {
    'active': ['Disable'],
    'disabled': ['Enable'],
    'draft': ['Delete']
  }.entries) {
    testWidgets('${entry.key} offers only eligible lifecycle actions',
        (tester) async {
      await tester.pumpWidget(ProviderScope(
          overrides: [
            trainerAuthProvider.overrideWith((ref) => MenuAuth('owner'))
          ],
          child: MaterialApp(
              home: Scaffold(
                  body: CourseActionsMenu(
                      course: course(entry.key,
                          canDelete: entry.key == 'draft'))))));
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();
      for (final action in [
        'Disable',
        'Enable',
        'Archive',
        'Restore',
        'Delete'
      ]) {
        expect(find.text(action),
            entry.value.contains(action) ? findsOneWidget : findsNothing);
      }
      if (entry.key == 'draft') {
        await tester.tap(find.text('Delete'));
        await tester.pumpAndSettle();
        expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
            isNull);
        await tester.enterText(find.byType(TextField), 'DELETE');
        await tester.pump();
        expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
            isNotNull);
        await tester.tap(find.text('Cancel'));
        await tester.pumpAndSettle();
      }
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('another trainer has no mutation menu', (tester) async {
    await tester.pumpWidget(ProviderScope(
        overrides: [
          trainerAuthProvider.overrideWith((ref) => MenuAuth('other'))
        ],
        child: MaterialApp(
            home:
                Scaffold(body: CourseActionsMenu(course: course('active'))))));
    expect(find.byType(PopupMenuButton<String>), findsNothing);
  });
}
