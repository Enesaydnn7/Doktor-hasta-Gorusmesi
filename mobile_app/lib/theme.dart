import 'package:flutter/material.dart';

const klinotTeal = Color(0xFF087F78);
const klinotNavy = Color(0xFF0B2438);
const klinotCanvas = Color(0xFFF3F7F8);

ThemeData buildKlinotTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: klinotTeal,
    brightness: Brightness.light,
    primary: klinotTeal,
    secondary: const Color(0xFF28A99F),
    surface: Colors.white,
    error: const Color(0xFFC43C3C),
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: klinotCanvas,
    fontFamily: 'sans-serif',
    appBarTheme: const AppBarTheme(
      backgroundColor: klinotCanvas,
      foregroundColor: klinotNavy,
      elevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(22),
        side: const BorderSide(color: Color(0xFFE1EAEC)),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(0, 54),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 17),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: Color(0xFFD6E2E5)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: Color(0xFFD6E2E5)),
      ),
    ),
  );
}
