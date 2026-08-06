import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/data/models/models.dart';

void main() {
  test('PDF file model formats metadata', () {
    final file = PDFFile(
      documentId: 'document-test',
      fileName: 'trainer_0001__training.pdf',
      displayName: 'training.pdf',
      size: 1536,
      createdAt: '2026-01-01T00:00:00+00:00',
    );

    expect(file.displayName, 'training.pdf');
    expect(file.formattedSize, '1.5 KB');
    expect(file.formattedDate, contains('2026'));
  });
}
