import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/features/document_builder/document_builder_models.dart';

void main() {
  test('Reports every missing metadata field when values are identical', () {
    const metadata = DocumentBuilderMetadata(
      courseName: '',
      courseDescription: '',
      courseObjective: '',
      courseDifficulty: '',
      language: '',
      targetAudience: '',
      courseType: '',
    );
    expect(metadata.missingFields, [
      'Course name',
      'Course description',
      'Course objective',
      'Course difficulty',
      'Language',
      'Target audience',
      'Course type',
    ]);
  });

  test('Whitespace is missing; supplied metadata is preserved', () {
    const metadata = DocumentBuilderMetadata(
      courseName: 'Customer Service',
      courseDescription: ' ',
      courseObjective: '',
      courseDifficulty: 'Beginner',
      language: 'English',
      targetAudience: 'New staff',
      courseType: 'Training guide',
    );
    expect(metadata.missingFields, ['Course description', 'Course objective']);
    expect(metadata.toJson()['courseName'], 'Customer Service');
  });
}
