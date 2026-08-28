import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const Color brandBlueLight = Color(0xFF3E75C8);
  static const Color primaryBlue = Color(0xFF00317A);
  static const Color brandBlue700 = Color(0xFF0B4E9B);
  static const Color brandBlue100 = Color(0xFFEAF3FC);
  static const Color brandBlue50 = Color(0xFFF4F9FE);

  static const Color textBlack = Color(0xFF172033);
  static const Color textSecondary = Color(0xFF5F6878);
  static const Color gray = Color(0xFF8B94A3);
  static const Color lightGray = Color(0xFFEBEFF4);
  static const Color surfaceSecondary = Color(0xFFF7F9FC);
  static const Color surfaceDisabled = Color(0xFFECEFF3);

  static const Color accentBlue = Color(0xFF2878D7);
  static const Color accentCyan = Color(0xFF2878D7);
  static const Color accentOrange = Color(0xFFD59A00);
  static const Color accentGreen = Color(0xFF00A878);
  static const Color accentLightOrange = Color(0xFFFFF6D8);
  static const Color accentPink = Color(0xFF3E75C8);
  static const Color accentRed = Color(0xFFD92D20);

  static const LinearGradient pageGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [
      Color(0x66D5EBF9),
      Color(0x66FFB996),
    ],
  );

  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [brandBlueLight, primaryBlue],
  );

  static BorderRadius get pShapeRadius => BorderRadius.circular(16);

  static BorderRadius pShapeRadiusCustom(double radius) =>
      BorderRadius.circular(radius);

  static BoxDecoration pageBackground() => const BoxDecoration(
        color: Colors.white,
        gradient: pageGradient,
      );

  static BoxDecoration cardDecoration({
    Color color = Colors.white,
    double radius = 16,
    Color borderColor = lightGray,
    bool shadow = true,
  }) {
    return BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(color: borderColor),
      boxShadow: shadow
          ? [
              BoxShadow(
                color: const Color(0xFF12263F).withOpacity(0.08),
                blurRadius: 8,
                offset: const Offset(0, 2),
              ),
            ]
          : null,
    );
  }

  static ButtonStyle primaryButtonStyle({
    EdgeInsetsGeometry? padding,
    double radius = 999,
  }) {
    return FilledButton.styleFrom(
      backgroundColor: primaryBlue,
      foregroundColor: Colors.white,
      disabledBackgroundColor: surfaceDisabled,
      disabledForegroundColor: gray,
      minimumSize: const Size(44, 44),
      padding: padding ?? const EdgeInsets.symmetric(horizontal: 24),
      textStyle: GoogleFonts.dmSans(
        fontSize: 14,
        fontWeight: FontWeight.w700,
      ),
      shape:
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(radius)),
    );
  }

  static ButtonStyle secondaryButtonStyle({
    EdgeInsetsGeometry? padding,
    double radius = 999,
  }) {
    return OutlinedButton.styleFrom(
      foregroundColor: textBlack,
      side: const BorderSide(color: Color(0xFFDDE3EA)),
      minimumSize: const Size(44, 44),
      padding: padding ?? const EdgeInsets.symmetric(horizontal: 22),
      textStyle: GoogleFonts.dmSans(
        fontSize: 14,
        fontWeight: FontWeight.w700,
      ),
      shape:
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(radius)),
    );
  }

  static ThemeData get lightTheme {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryBlue,
        brightness: Brightness.light,
        primary: primaryBlue,
        secondary: brandBlue700,
        surface: Colors.white,
        error: accentRed,
      ),
    );
    final textTheme = GoogleFonts.dmSansTextTheme(base.textTheme).copyWith(
      bodyLarge: GoogleFonts.dmSans(
        fontSize: 15,
        height: 1.5,
        color: textBlack,
      ),
      bodyMedium: GoogleFonts.dmSans(
        fontSize: 14,
        height: 1.5,
        color: textBlack,
      ),
      bodySmall: GoogleFonts.dmSans(
        fontSize: 12,
        height: 1.4,
        color: gray,
      ),
      titleMedium: GoogleFonts.manrope(
        fontSize: 18,
        height: 1.35,
        fontWeight: FontWeight.w700,
        color: primaryBlue,
      ),
      headlineSmall: GoogleFonts.manrope(
        fontSize: 24,
        height: 1.25,
        fontWeight: FontWeight.w800,
        color: textBlack,
      ),
      displayLarge: GoogleFonts.manrope(
        fontSize: 40,
        height: 1.1,
        fontWeight: FontWeight.w800,
        color: primaryBlue,
      ),
      displayMedium: GoogleFonts.manrope(
        fontSize: 24,
        height: 1.25,
        fontWeight: FontWeight.w800,
        color: primaryBlue,
      ),
      displaySmall: GoogleFonts.manrope(
        fontSize: 20,
        height: 1.25,
        fontWeight: FontWeight.w700,
        color: primaryBlue,
      ),
      labelLarge: GoogleFonts.dmSans(
        fontSize: 14,
        fontWeight: FontWeight.w700,
        color: primaryBlue,
      ),
    );

    return base.copyWith(
      primaryColor: primaryBlue,
      scaffoldBackgroundColor: Colors.white,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.white.withOpacity(0.94),
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        titleTextStyle: GoogleFonts.manrope(
          fontSize: 20,
          fontWeight: FontWeight.w800,
          color: primaryBlue,
        ),
        iconTheme: const IconThemeData(color: primaryBlue),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Color(0xFFDDE3EA)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Color(0xFFDDE3EA)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: brandBlueLight, width: 1.4),
        ),
        labelStyle: const TextStyle(color: textSecondary),
        hintStyle: const TextStyle(color: gray),
      ),
      filledButtonTheme: FilledButtonThemeData(style: primaryButtonStyle()),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryBlue,
          foregroundColor: Colors.white,
          elevation: 0,
          minimumSize: const Size(44, 44),
          padding: const EdgeInsets.symmetric(horizontal: 24),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(999),
          ),
          textStyle: GoogleFonts.dmSans(
            fontSize: 14,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      outlinedButtonTheme:
          OutlinedButtonThemeData(style: secondaryButtonStyle()),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primaryBlue,
          minimumSize: const Size(44, 44),
          textStyle: GoogleFonts.dmSans(
            fontSize: 14,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        backgroundColor: Colors.white,
        selectedColor: brandBlue100,
        side: const BorderSide(color: lightGray),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
        labelStyle: const TextStyle(color: textBlack),
      ),
      dividerTheme: const DividerThemeData(
        color: lightGray,
        thickness: 1,
        space: 1,
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: primaryBlue,
        linearTrackColor: lightGray,
      ),
    );
  }
}
