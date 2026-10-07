import 'package:flutter_test/flutter_test.dart';

import '../lib/core/config/lms_runtime_urls.dart';

void main() {
  for (final mount in ['/lms', '/lms/trainer']) {
    test('root and $mount entrypoints infer separate API mounts', () {
      for (final path in ['/', '/dashboard', '$mount/', '$mount/dashboard']) {
        final urls = LmsRuntimeUrls(
          entrypoint: Uri.parse('https://example.test:9443$path?launch=secret'),
          publicMount: mount,
        );
        final expected = path.startsWith('$mount/') ? mount : '';
        expect(urls.apiBaseUrl, expected);
        expect(
          urls.websocketEndpoint(
              'api/me/courses/ws', {'token': 'a&b'}).toString(),
          'wss://example.test:9443$expected/api/me/courses/ws?token=a%26b',
        );
      }
    });

    test('$mount relative API overrides retain origin and mount', () {
      for (final configured in ['proxy/', '/proxy/', 'http://api.test:9000/']) {
        final urls = LmsRuntimeUrls(
          entrypoint: Uri.parse('https://example.test:9443$mount/dashboard'),
          publicMount: mount,
          configuredApiBase: configured,
        );
        final expected = switch (configured) {
          'proxy/' => 'https://example.test:9443$mount/proxy',
          '/proxy/' => 'https://example.test:9443/proxy',
          _ => 'http://api.test:9000',
        };
        expect(urls.apiBaseUrl, expected);
        expect(
          urls.websocketEndpoint('api/me/courses/ws', {}).toString(),
          '${expected.replaceFirst('https:', 'wss:').replaceFirst('http:', 'ws:')}/api/me/courses/ws',
        );
      }
    });
  }

  test('mount inference requires a full path segment', () {
    final urls = LmsRuntimeUrls(
      entrypoint: Uri.parse('http://example.test/lms-other/'),
      publicMount: '/lms',
    );
    expect(urls.apiBaseUrl, '');
  });
}
