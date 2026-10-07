/// Resolves the active public mount without a build-time origin or port.
class LmsRuntimeUrls {
  LmsRuntimeUrls({
    required this.entrypoint,
    required this.publicMount,
    this.configuredApiBase = '',
  });

  final Uri entrypoint;
  final String publicMount;
  final String configuredApiBase;

  /// The matched entry path selects the mount, not a client-supplied header.
  String get activeMount => entrypoint.path == publicMount ||
          entrypoint.path.startsWith('$publicMount/')
      ? publicMount
      : '';

  /// Relative overrides resolve inside the active mount; absolute ones stay absolute.
  String get apiBaseUrl {
    final configured = configuredApiBase.trim();
    if (configured.isEmpty) return activeMount;
    final uri = Uri.parse(configured);
    if (uri.hasScheme) return configured.replaceFirst(RegExp(r'/+$'), '');
    final mountUri = entrypoint.replace(
      path: '$activeMount/',
      query: '',
      fragment: '',
    );
    return mountUri
        .resolve(configured)
        .toString()
        .replaceFirst(RegExp(r'/+$'), '');
  }

  /// WebSocket URLs always include the entry origin and retain the API mount.
  Uri websocketEndpoint(String path, Map<String, String> queryParameters) {
    final base = entrypoint.resolve('$apiBaseUrl/');
    return base.resolve(path).replace(
          scheme: base.scheme == 'https' ? 'wss' : 'ws',
          queryParameters: queryParameters.isEmpty ? null : queryParameters,
        );
  }
}
