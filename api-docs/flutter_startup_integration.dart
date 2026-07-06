///  ‌نمونه کد اتصال Version Check به Startup اپ
/// =================================================
/// این کد را در main.dart یا SplashScreen خود قرار دهید.
///
/// وابستگی‌های pubspec.yaml:
///   dependencies:
///     http: ^1.2.0
///     package_info_plus: ^8.0.0
///     url_launcher: ^6.3.0
///
/// فایل‌های مورد نیاز:
///   lib/services/version_check_service.dart
///   lib/widgets/force_update_dialog.dart
/// =================================================

/*
// ─── روش ۱: در main.dart (قبل از runApp) ─────────────────
import 'package:flutter/material.dart';
import 'services/version_check_service.dart';
import 'widgets/force_update_dialog.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // ۱. اجرای اپ (بدون منتظر ماندن برای response)
  runApp(const CoinceeperApp());

  // ۲. در پس‌زمینه نسخه را چک کن
  _checkVersionOnStartup();
}

Future<void> _checkVersionOnStartup() async {
  // کمی صبر کن تا اپ لود شود
  await Future.delayed(const Duration(milliseconds: 500));

  final result = await VersionCheckService.checkForUpdate(
    serverUrl: 'https://coinceeper.com',
  );

  if (!result.success) return; // سرور در دسترس نیست → کاری نکن

  if (result.forceUpdate || result.title != null) {
    // نمایش مودال در navigator اصلی
    navigatorKey.currentState?.context.let((ctx) {
      if (ctx != null) ForceUpdateDialog.show(ctx, result);
    });
  }
}
*/

// ─── روش ۲: در SplashScreen (توصیه شده) ──────────────────
/*
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:io';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _checkAndNavigate();
  }

  Future<void> _checkAndNavigate() async {
    // ۱. چک کن نسخه
    final result = await VersionCheckService.checkForUpdate(
      serverUrl: 'https://coinceeper.com',
    );

    if (!mounted) return;

    if (result.success && (result.forceUpdate || result.title != null)) {
      // نمایش مودال — اگر force است نمی‌تواند رد شود
      await ForceUpdateDialog.show(context, result);
      // اگر force=false و user "Later" زد، ادامه بده
    }

    if (!mounted) return;
    // ۲. نویگیشن به صفحه اصلی
    Navigator.of(context).pushReplacementNamed('/home');
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}
*/
