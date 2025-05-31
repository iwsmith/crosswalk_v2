{
  description = "Development environment for crosswalk-v2";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python313;
        pythonPackages = python.pkgs;
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pythonPackages; [
            python
            pyzmq
            pydantic
          ] ++ [
            pkgs.uv
          ];

          shellHook = ''
            echo "Python $(python --version) development environment loaded"
            echo "Available packages:"
            echo "  - pyzmq"
            echo "  - pydantic"
            echo "  - uv (package manager)"
            
            # Install package in development mode using uv
            echo "Installing local package in development mode..."
            uv pip install -e .
          '';
        };
      }
    );
}
