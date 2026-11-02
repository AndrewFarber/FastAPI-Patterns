{
  description = "FastAPI Patterns vault: runnable examples and their tests";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      # Nix provides the tools; uv installs the Python packages pinned in examples/uv.lock
      # ruff comes from nixpkgs: the wheel uv would install is a generic Linux binary NixOS can't run
      tools = pkgs: [ pkgs.python3 pkgs.uv pkgs.nodejs pkgs.git pkgs.ruff ];
      uvEnv = pkgs: ''
        export UV_PYTHON=${pkgs.python3}/bin/python3
        export UV_PYTHON_DOWNLOADS=never
        EXAMPLES_DIR="$(git rev-parse --show-toplevel)/examples"
        export EXAMPLES_DIR
      '';
      app = pkgs: name: text: {
        type = "app";
        program = "${pkgs.writeShellApplication {
          inherit name;
          runtimeInputs = tools pkgs;
          text = uvEnv pkgs + text;
        }}/bin/${name}";
      };
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = tools pkgs;
          shellHook = uvEnv pkgs;
        };
      });

      apps = forAllSystems (pkgs: {
        # nix run .#test: run every topic's tests (settings, ...)
        test = app pkgs "test" ''
          cd "$EXAMPLES_DIR"
          for topic in */; do
            if [ -d "$topic/tests" ]; then (cd "$topic" && uv run pytest "$@"); fi
          done
        '';
        # nix run .#sync: copy example code into the notes
        sync = app pkgs "sync" ''
          uv run --project "$EXAMPLES_DIR" python "$EXAMPLES_DIR/sync_notes.py" "$@"
        '';
      });
    };
}
