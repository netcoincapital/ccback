import 'dart:io';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'version_check_service.dart';

/// مودال آپدیت اجباری - کاربر نمی‌تواند از آن خارج شود (dismissible: false)
///
/// دو حالت:
///   - [forceUpdate] = true:  دکمه بستن ندارد، کاربر مجبور به آپدیت است
///   - [forceUpdate] = false: دکمه "Later" دارد، آپدیت اختیاری است
class ForceUpdateDialog extends StatelessWidget {
  final VersionCheckResult result;

  const ForceUpdateDialog({super.key, required this.result});

  /// نمایش دیالوگ (از هر جای اپ صدا بزنید)
  static Future<void> show(BuildContext context, VersionCheckResult result) {
    return showDialog(
      context: context,
      barrierDismissible: !result.forceUpdate, // اگر force است، نمی‌شود بست
      builder: (_) => ForceUpdateDialog(result: result),
    );
  }

  Future<void> _openStore() async {
    final url = result.updateUrl;
    if (url == null || url.isEmpty) return;

    final uri = Uri.tryParse(url);
    if (uri != null && await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isForce = result.forceUpdate;
    final title = result.title ?? 'Update Required';
    final body = result.body ?? 'A new version is available.';

    return PopScope(
      canPop: !isForce, // if force, back button does nothing
      child: AlertDialog(
        title: Row(
          children: [
            Icon(
              isForce ? Icons.system_update : Icons.new_releases,
              color: isForce ? Colors.orange : theme.colorScheme.primary,
              size: 28,
            ),
            const SizedBox(width: 12),
            Expanded(child: Text(title)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(body),
            const SizedBox(height: 16),
            if (result.minVersion != null || result.latestVersion != null) ...[
              _versionRow(
                'Your version',
                _getCurrentVersion(),
              ),
              if (isForce && result.minVersion != null)
                _versionRow('Minimum required', result.minVersion!),
              if (!isForce && result.latestVersion != null)
                _versionRow('Latest version', result.latestVersion!),
            ],
          ],
        ),
        actions: [
          if (!isForce)
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Later'),
            ),
          FilledButton.icon(
            onPressed: _openStore,
            icon: const Icon(Icons.open_in_new),
            label: Text(Platform.isAndroid ? 'Open Play Store' : 'Open App Store'),
          ),
        ],
      ),
    );
  }

  Widget _versionRow(String label, String version) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Text('$label: ', style: const TextStyle(fontWeight: FontWeight.w500)),
          Text(version),
        ],
      ),
    );
  }

  String _getCurrentVersion() {
    // مقدار جایگزین می‌شود — یا از PackageInfo یا از State
    return '';
  }
}
