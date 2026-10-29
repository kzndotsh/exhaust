{
  description = "exhaust dev shell: uv, just, and the Rig's pinned tools";

  inputs = {
    # Pinned to the exact commit NixHub indexes for nmap 7.991 (src/exhaust/rig/catalog.py's
    # PINNED_TOOLS entry): the newest nmap this provisioning path can actually provide today,
    # one patch behind the upstream tag the entry originally named (ADR 0026's own named gap).
    nixpkgs.url = "github:NixOS/nixpkgs/55ba7f49ef2962b42cbd126522b7df5f95037679";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShellNoCC {
          # uv manages the Python toolchain, every Python dependency, and lefthook
          # itself (pyproject.toml's dev group); `just` runs this repo's task
          # recipes (justfile); nmap and curl are the Rig's pinned tools today
          # (ADR 0026, ADR 0027). Nothing else here: everything else a Workspace
          # run needs, uv handles.
          packages = [
            pkgs.uv
            pkgs.just
            pkgs.nmap
            pkgs.curl
          ];

          shellHook = ''
            export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
            echo "exhaust dev shell — $(uv --version)"
            echo "  uv sync --group dev && uv run lefthook install"
            echo "  uv run exhaust doctor   # check the Rig's pinned tools are on PATH"
            echo "  just check"
            echo "  uv run exhaust run <target> --model <model>"
          '';
        };
      }
    );
}
