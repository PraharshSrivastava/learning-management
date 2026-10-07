{{flutter_js}}
{{flutter_build_config}}

// The nginx entry HTML sets the base for this mount. Keep engine assets local.
_flutter.loader.load({
  config: {
    entrypointBaseUrl: document.baseURI,
    // Flutter 3.24 uses the earlier spelling; newer loaders use the key above.
    entryPointBaseUrl: document.baseURI,
    assetBase: document.baseURI,
    canvasKitBaseUrl: new URL('canvaskit/', document.baseURI).href
  }
});
