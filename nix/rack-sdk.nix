{
  lib,
  stdenvNoCC,
  fetchzip,
}:

let
  version = "2.6.6";

  platforms = {
    # Check for new versions at https://vcvrack.com/downloads/
    # You can get the correct hashes for fetchzip like this:
    # $ curl -sL -o sdk.zip "https://vcvrack.com/downloads/Rack-SDK-{version}-{platform}.zip"
    # $ mkdir unpack && cd unpack && unzip -q ../sdk.zip && cd */
    # $ nix hash path .
    x86_64-darwin = {
      url = "https://vcvrack.com/downloads/Rack-SDK-${version}-mac-x64.zip";
      hash = "sha256-zc6SDqycji2Rj2kVJf90Ul+zqGPnld+iEBPZxOL3t9g=";
    };
    aarch64-darwin = {
      url = "https://vcvrack.com/downloads/Rack-SDK-${version}-mac-arm64.zip";
      hash = "sha256-2254CeiYzqZrcr9qw8ZtBCdj2+lrXYTgfHdl1s65EAg=";
    };
    x86_64-linux = {
      url = "https://vcvrack.com/downloads/Rack-SDK-${version}-lin-x64.zip";
      hash = "sha256-Wlc6uA8yGypUPAXPc+4Xg+Fi6Xp1QfEt1nx/hikPsIU=";
    };
    # There's also a Windows version available at https://vcvrack.com/downloads/Rack-SDK-${version}-win-x64.zip,
    # but in that case the build process uses MinGW and I don't know how that slots into nixpkgs.
    # See https://vcvrack.com/manual/Building for more info on how VCV Rack recommends building on Windows.
  };
in
stdenvNoCC.mkDerivation {
  pname = "vcv-rack-sdk";
  inherit version;

  src =
    let
      system = stdenvNoCC.hostPlatform.system;
      platform =
        platforms.${system}
          or (throw "vcv-rack-sdk: unsupported platform '${system}'. Supported: ${toString (lib.attrNames platforms)}");
    in
    fetchzip {
      inherit (platform) url hash;
    };

  # The zip extracts straight into the SDK layout (include/, dep/include/,
  # Makefile, helper.py, etc). There's no build step, it's just headers
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
    license = licenses.gpl3Plus;
    platforms = builtins.attrNames platforms;
    sourceProvenance = with sourceTypes; [ binaryNativeCode ];
  };
}
