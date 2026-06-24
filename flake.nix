{
  description = "Freilite VCV Rack Plugins";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  inputs.nixpkgs-unfree.url = "github:numtide/nixpkgs-unfree";
  inputs.nixpkgs-unfree.inputs.nixpkgs.follows = "nixpkgs";

  outputs =
    {
      self,
      nixpkgs,
      nixpkgs-unfree,
      flake-utils,
    }:
    let
      systems = with flake-utils.lib.system; [
        # Add or remove systems from this list if your project can be developed on them or not
        # See https://github.com/numtide/flake-utils/blob/main/allSystems.nix for a complete list
        x86_64-linux
        # aarch64-linux (VCV Rack SDK is not available for Linux on ARM yet)
        x86_64-darwin
        aarch64-darwin
      ];
    in
    flake-utils.lib.eachSystem systems (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pkgs-unfree = nixpkgs-unfree.legacyPackages.${system};
        rack-sdk = pkgs.callPackage nix/rack-sdk.nix { };
      in
      {
        packages = {
          inherit rack-sdk;
          vcv-rack = pkgs-unfree.vcv-rack;
        };
        devShell = pkgs.mkShell {
          # Only tested for macOS right now, see https://vcvrack.com/manual/Building
          # for Linux dependencies
          buildInputs = with pkgs; [
            # Useful for testing, launch from terminal like so:
            #   Rack
            pkgs-unfree.vcv-rack
            # Rack SDK, see package definition
            rack-sdk
            # Requirements listed for macOS
            wget
            cmake
            autoconf
            automake
            libtool
            jq
            python3
            zstd
            pkg-config
            # Additional requirements for scripts and experiments
            uv
            # C++ test framework for src/tests/cpp/
            catch2_3
          ];
          shellHook = ''
            uv sync
          '';
        };
      }
    );
}
