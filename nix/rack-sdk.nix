{
  lib,
  stdenvNoCC,
  fetchzip,
}:

stdenvNoCC.mkDerivation rec {
  pname = "vcv-rack-sdk";
  version = "2.6.6";

  src = fetchzip {
    url = "https://vcvrack.com/downloads/Rack-SDK-${version}-mac-arm64.zip";
    hash = "sha256-2254CeiYzqZrcr9qw8ZtBCdj2+lrXYTgfHdl1s65EAg=";
  };

  # The zip extracts straight into the SDK layout (include/, dep/include/,
  # Makefile, helper.py, etc). There's no build step -- it's just headers
  # and build-system glue that downstream plugin Makefiles consume via
  # $RACK_DIR, so we simply install the whole tree as-is.
  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out
    cp -r . $out/
    runHook postInstall
  '';

  # Plugins built against the SDK expect $RACK_DIR to point at a directory
  # containing include/ and dep/include/. setupHook wires that up
  # automatically for anything that depends on this derivation, and it's
  # also exposed as passthru for manual use (e.g. in a devShell).
  setupHook = ./rack-sdk-setup-hook.sh;

  passthru.rackDir = placeholder "out";

  meta = with lib; {
    description = "Development SDK (headers only) for building VCV Rack plugins";
    homepage = "https://vcvrack.com/manual/PluginDevelopmentTutorial";
    license = licenses.gpl3; # check actual SDK license before publishing
    platforms = [
      "aarch64-darwin"
    ];
    sourceProvenance = with sourceTypes; [ binaryNativeCode ];
  };
}
