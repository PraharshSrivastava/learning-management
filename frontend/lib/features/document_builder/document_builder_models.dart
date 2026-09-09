class DocumentBuilderMetadata {
  final String courseName, courseDescription, courseObjective;
  final String courseDifficulty, language, targetAudience, courseType;
  const DocumentBuilderMetadata(
      {required this.courseName,
      required this.courseDescription,
      required this.courseObjective,
      required this.courseDifficulty,
      required this.language,
      required this.targetAudience,
      required this.courseType});
  Map<String, dynamic> toJson() => {
        'courseName': courseName.trim(),
        'courseDescription': courseDescription.trim(),
        'courseObjective': courseObjective.trim(),
        'courseDifficulty': courseDifficulty.trim(),
        'language': language.trim(),
        'targetAudience': targetAudience.trim(),
        'courseType': courseType.trim()
      };
  List<String> get missingFields => {
        courseName: 'Course name',
        courseDescription: 'Course description',
        courseObjective: 'Course objective',
        courseDifficulty: 'Course difficulty',
        language: 'Language',
        targetAudience: 'Target audience',
        courseType: 'Course type'
      }
          .entries
          .where((entry) => entry.key.trim().isEmpty)
          .map((entry) => entry.value)
          .toList();
}

class DocumentBuilderSettings {
  final int moduleCount;
  final String detailLevel, tone, writingFocus;
  final bool includeScenarios,
      includeBadGood,
      includeTakeaways,
      includeMistakes;
  const DocumentBuilderSettings(
      {this.moduleCount = 4,
      this.detailLevel = 'standard',
      this.tone = 'Clear and professional',
      this.writingFocus = 'balanced',
      this.includeScenarios = true,
      this.includeBadGood = true,
      this.includeTakeaways = true,
      this.includeMistakes = true});
  Map<String, dynamic> toJson() => {
        'moduleCount': moduleCount,
        'detailLevel': detailLevel,
        'tone': tone,
        'writingFocus': writingFocus,
        'includeScenarios': includeScenarios,
        'includeBadGood': includeBadGood,
        'includeTakeaways': includeTakeaways,
        'includeMistakes': includeMistakes
      };
}

class DocumentBuilderBlock {
  final String type, text, src, align, caption;
  final int width;
  const DocumentBuilderBlock.text(this.text)
      : type = 'text',
        src = '',
        align = 'left',
        caption = '',
        width = 60;
  const DocumentBuilderBlock.image(
      {required this.src,
      required this.width,
      required this.align,
      required this.caption})
      : type = 'image',
        text = '';
  Map<String, dynamic> toJson() => {
        'type': type,
        'text': text,
        'src': src,
        'width': width,
        'align': align,
        'caption': caption
      };
}

class BuilderChatMessage {
  final bool user;
  final String text;
  const BuilderChatMessage(this.user, this.text);
}
