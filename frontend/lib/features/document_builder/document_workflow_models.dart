/// Canonical workflow contracts. Browser selection offsets are UTF-16; persisted
/// offsets are Unicode code points, matching the backend range contract.
class WorkflowBlock {
  final Map<String, dynamic> _value;
  WorkflowBlock.fromJson(Map<String, dynamic> value)
      : _value = Map<String, dynamic>.from(value) {
    if (value['id'] is! String ||
        !const [
          'paragraph',
          'heading',
          'scenario',
          'takeaway',
          'list',
          'table',
          'image'
        ].contains(value['type'])) {
      throw const FormatException('Unsupported document block');
    }
  }

  factory WorkflowBlock.paragraph(String id, String text) =>
      WorkflowBlock.fromJson({
        'id': id,
        'type': 'paragraph',
        'text': text,
        'marks': <Map<String, dynamic>>[]
      });

  String get id => _value['id'] as String;
  String get type => _value['type'] as String;
  String get text => _value['text'] as String? ?? '';
  Map<String, dynamic> toJson() => Map<String, dynamic>.from(_value);
}

class WorkflowSelection {
  final String blockId;
  final int start, end;
  final String text;
  const WorkflowSelection(this.blockId, this.start, this.end, this.text);
}

int utf16ToCodePoint(String text, int offset) {
  if (offset < 0 || offset > text.length) {
    throw const FormatException('Selection is out of bounds');
  }
  var units = 0;
  var points = 0;
  for (final rune in text.runes) {
    if (units == offset) return points;
    units += rune > 0xffff ? 2 : 1;
    if (units > offset) {
      throw const FormatException('Selection splits a surrogate pair');
    }
    points++;
  }
  return points;
}

int codePointToUtf16(String text, int offset) {
  if (offset < 0) throw const FormatException('Negative selection');
  var units = 0;
  var points = 0;
  for (final rune in text.runes) {
    if (points == offset) return units;
    units += rune > 0xffff ? 2 : 1;
    points++;
  }
  if (points != offset) {
    throw const FormatException('Selection is out of bounds');
  }
  return units;
}
