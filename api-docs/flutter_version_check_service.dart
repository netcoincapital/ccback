import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';

/// نتیجه بررسی نسخه از سرور
class VersionCheckResult {
  final bool success;
  final String? minVersion;
  final String? latestVersion;
  final String? updateUrl;
  final bool forceUpdate;
  final String? title;
  final String? body;

  VersionCheckResult({
    required this.success,
    this.minVersion,
    this.latestVersion,
    this.updateUrl,
    this.forceUpdate = false,
    this.title,
    this.body,
  });
}

/// سرویس بررسی نسخه اجباری اپلیکیشن
class VersionCheckService {
  static const Duration _timeout = Duration(seconds: 10);

  /// دریافت نسخه فعلی اپ از device
  static Future<String> _getCurrentAppVersion() async {
    try {
      final info = await PackageInfo.fromPlatform();
      return info.version; // مثلاً "1.0.0"
    } catch (e) {
      return '0.0.0';
    }
  }

  /// مقایسه دو نسخه semantic (returns true if v1 < v2)
  static bool _isVersionLower(String v1, String v2) {
    try {
      final parts1 = v1.split('.').map((e) => int.tryParse(e) ?? 0).toList();
      final parts2 = v2.split('.').map((e) => int.tryParse(e) ?? 0).toList();

      // Pad shorter list with zeros
      while (parts1.length < 3) parts1.add(0);
      while (parts2.length < 3) parts2.add(0);

      for (int i = 0; i < 3; i++) {
        if (parts1[i] < parts2[i]) return true;
        if (parts1[i] > parts2[i]) return false;
      }
      return false; // equal
    } catch (e) {
      return false;
    }
  }

  /// پلتفرم فعلی
  static String _getPlatform() {
    if (Platform.isAndroid) return 'android';
    if (Platform.isIOS) return 'ios';
    return 'unknown';
  }

  /// اصلی: دریافت نسخه از سرور و مقایسه با نسخه فعلی اپ
  ///
  /// Returns:
  ///   - [forceUpdate] = true: کاربر باید حتماً آپدیت کند
  ///   - [latestVersion] > current: آپدیت اختیاری موجود است
  ///   - [success] = false: سرور در دسترس نبود (اپ به کار خود ادامه می‌دهد)
  static Future<VersionCheckResult> checkForUpdate({
    required String serverUrl,
  }) async {
    final currentVersion = await _getCurrentAppVersion();
    final platform = _getPlatform();

    try {
      final uri = Uri.parse('$serverUrl/api/app/version');
      final response = await http
          .get(uri, headers: {'Origin': 'https://coinceeper.com'})
          .timeout(_timeout);

      if (response.statusCode != 200) {
        return VersionCheckResult(success: false);
      }

      final data = json.decode(response.body);
      if (data['success'] != true) {
        return VersionCheckResult(success: false);
      }

      final platformData = data[platform];
      if (platformData == null) {
        return VersionCheckResult(success: false);
      }

      final minVersion = platformData['min_version'] as String?;
      final latestVersion = platformData['latest_version'] as String?;
      final updateUrl = platformData['update_url'] as String?;

      // آیا نسخه فعلی کاربر از min_version پایین‌تر است؟
      final needsForceUpdate = minVersion != null &&
          _isVersionLower(currentVersion, minVersion);

      // آیا آپدیت اختیاری موجود است؟
      final hasOptionalUpdate = latestVersion != null &&
          !needsForceUpdate &&
          _isVersionLower(currentVersion, latestVersion);

      // انتخاب پیام مناسب
      String? title, body;
      if (needsForceUpdate) {
        title = data['force_update_message']?['title'] ?? 'Update Required';
        body = data['force_update_message']?['body'] ??
            'Please update to continue.';
      } else if (hasOptionalUpdate) {
        title = data['optional_update_message']?['title'] ??
            'New Version Available';
        body = data['optional_update_message']?['body'] ??
            'Would you like to update?';
      }

      return VersionCheckResult(
        success: true,
        minVersion: minVersion,
        latestVersion: latestVersion,
        updateUrl: updateUrl,
        forceUpdate: needsForceUpdate,
        title: title,
        body: body,
      );
    } catch (e) {
      // سرور در دسترس نیست → اپ به کار ادامه می‌دهد
      return VersionCheckResult(success: false);
    }
  }
}
