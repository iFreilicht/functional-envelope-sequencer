{
  description = "Freilite VCV Rack Plugins";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    let
      systems = with flake-utils.lib.system; [
        # Add or remove systems from this list if your project can be developed on them or not
        # See https://github.com/numtide/flake-utils/blob/main/allSystems.nix for a complete list
        x86_64-linux
        aarch64-linux
        x86_64-darwin
        aarch64-darwin
      ];
    in
    flake-utils.lib.eachSystem systems (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShell = pkgs.mkShell {
          # Only tested for macOS right now, see https://vcvrack.com/manual/Building
          # for Linux dependencies
          buildInputs = with pkgs; [
            (callPackage nix/rack-sdk.nix { })
            wget
            cmake
            autoconf
            automake
            libtool
            jq
            python3
            zstd
            pkg-config
          ];
          shellHook = "";
        };
      }
    );
}
