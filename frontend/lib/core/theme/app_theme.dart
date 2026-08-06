import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const Color primaryBlue = Color(0xFF00317A);
  static const Color lightGray = Color(0xFFEEEEEE);
  static const Color gray = Color(0xFFAAAAAA);
  static const Color textBlack = Color(0xFF000000);

  // Sub-Brand / Accent Colors
  static const Color accentBlue = Color(0xFF0080FF);
  static const Color accentCyan = Color(0xFF17BCE2);
  static const Color accentOrange = Color(0xFFF78F20);
  static const Color accentGreen = Color(0xFF14C496);
  static const Color accentLightOrange = Color(0xFFFFBA6F);
  static const Color accentPink = Color(0xFFE561D2);
  static const Color accentRed = Color(0xFFFF1515);

  // "P" Geometric Border Radius - Top-Right and Bottom-Left rounded, Top-Left and Bottom-Right sharp
  static BorderRadius get pShapeRadius => const BorderRadius.only(
        topRight: Radius.circular(16.0),
        bottomLeft: Radius.circular(16.0),
        topLeft: Radius.zero,
        bottomRight: Radius.zero,
      );

  static BorderRadius pShapeRadiusCustom(double radius) => BorderRadius.only(
        topRight: Radius.circular(radius),
        bottomLeft: Radius.circular(radius),
        topLeft: Radius.zero,
        bottomRight: Radius.zero,
      );

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      primaryColor: primaryBlue,
      scaffoldBackgroundColor: Colors.white,
      colorScheme: const ColorScheme.light(
        primary: primaryBlue,
        secondary: gray,
        surface: lightGray,
        onPrimary: Colors.white,
        onSecondary: textBlack,
      ),
      textTheme: GoogleFonts.dmSansTextTheme().copyWith(
        bodyLarge: GoogleFonts.dmSans(
          fontSize: 16.0,
          fontWeight: FontWeight.normal,
          color: textBlack,
        ),
        bodyMedium: GoogleFonts.dmSans(
          fontSize: 14.0,
          fontWeight: FontWeight.normal,
          color: textBlack,
        ),
        bodySmall: GoogleFonts.dmSans(
          fontSize: 12.0,
          fontWeight: FontWeight.normal,
          color: gray,
        ),
        titleMedium: GoogleFonts.manrope(
          fontSize: 18.0,
          fontWeight: FontWeight.w700,
          color: primaryBlue,
        ),
        displayLarge: GoogleFonts.manrope(
          fontSize: 32.0,
          fontWeight: FontWeight.bold,
          color: primaryBlue,
        ),
        displayMedium: GoogleFonts.manrope(
          fontSize: 24.0,
          fontWeight: FontWeight.bold,
          color: primaryBlue,
        ),
        displaySmall: GoogleFonts.manrope(
          fontSize: 20.0,
          fontWeight: FontWeight.w600,
          color: primaryBlue,
        ),
        labelLarge: GoogleFonts.dmSans(
          fontSize: 14.0,
          fontWeight: FontWeight.w600,
          color: primaryBlue,
        ),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.white,
        elevation: 0,
        titleTextStyle: GoogleFonts.manrope(
          fontSize: 20.0,
          fontWeight: FontWeight.bold,
          color: primaryBlue,
        ),
        iconTheme: const IconThemeData(color: primaryBlue),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryBlue,
          foregroundColor: Colors.white,
          elevation: 2,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: pShapeRadiusCustom(8.0),
          ),
          textStyle: GoogleFonts.dmSans(
            fontSize: 14.0,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}
