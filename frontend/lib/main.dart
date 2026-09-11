import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:frontend/app/trainer_app.dart';

Future<void> main() async {
  // The target VM has no internet. Fonts ship as bundled assets.
  GoogleFonts.config.allowRuntimeFetching = false;
  await dotenv.load(fileName: ".env");
  runApp(
    const ProviderScope(
      child: LMSApp(),
    ),
  );
}
