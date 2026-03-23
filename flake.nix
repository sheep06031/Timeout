{
  description = "Timeout – Django productivity app";

  inputs = {
    nixpkgs.url     = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem [ "x86_64-linux" ] (system:
      let
        pkgs    = nixpkgs.legacyPackages.${system};
        pyPkgs  = pkgs.python312Packages;

        # Custom packages absent from nixpkgs 24.11

        starkbankEcdsa = pyPkgs.buildPythonPackage rec {
          pname   = "starkbank-ecdsa";
          version = "2.2.0";
          format  = "setuptools";
          src = pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-k5nDNxuJnUojW2ih7XkZ0gL78CS9LIY66Ova00PCpjo=";
          };
          nativeBuildInputs = [ pyPkgs.setuptools ];
          doCheck = false;
        };

        pythonHttpClient = pyPkgs.buildPythonPackage rec {
          pname   = "python_http_client";
          version = "3.3.7";
          format  = "setuptools";
          src = pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-v4Qe5FJidH4A3sfumXHfuMfYMIP1cTWWSI1nc5FwzqA=";
          };
          nativeBuildInputs = [ pyPkgs.setuptools ];
          doCheck = false;
        };

        sendgrid = pyPkgs.buildPythonPackage rec {
          pname   = "sendgrid";
          version = "6.11.0";
          format  = "setuptools";
          src = pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-cUJLKpf1oDQSHqOyZmxlO6DtMVmC8NV7eFHAyVA9xas=";
          };
          nativeBuildInputs    = [ pyPkgs.setuptools ];
          propagatedBuildInputs = [ pythonHttpClient starkbankEcdsa ];
          doCheck = false;
        };

        # Python environment

        pythonEnv = pkgs.python312.withPackages (ps: [
          ps.django
          ps.pillow
          ps.faker
          ps.argon2-cffi
          ps.coverage
          ps.django-allauth
          ps.requests
          ps.pyjwt
          ps.cryptography
          ps.python-dotenv
          ps.openai
          sendgrid
        ]);

        # Shared guard: must run from project root

        guard = ''
          if [ ! -f manage.py ]; then
            echo "ERROR: Run this command from the project root (where manage.py lives)." >&2
            exit 1
          fi
          export DJANGO_SETTINGS_MODULE=timeout_pwa.settings
        '';

        # Script builder helper

        mkApp = name: scriptText:
          let
            drv = pkgs.writeShellApplication {
              inherit name;
              runtimeInputs = [ pythonEnv ];
              text = scriptText;
            };
          in
          { type = "app"; program = "${drv}/bin/${name}"; };

      in
      {
        # Entrypoints 

        apps = {
          init = mkApp "timeout-init" ''
            ${guard}
            mkdir -p media
            python manage.py migrate --run-syncdb
            python manage.py init_site
            python manage.py seed
            echo ""
            echo "Ready.  Login: johndoe / Password123"
          '';

          run = mkApp "timeout-run" ''
            ${guard}
            echo "Starting development server at http://127.0.0.1:8000"
            python manage.py runserver 0.0.0.0:8000
          '';

          tests = mkApp "timeout-tests" ''
            ${guard}
            mkdir -p coverage
            python -m coverage run --rcfile=.coveragerc manage.py test --verbosity=2
            python -m coverage html  --rcfile=.coveragerc --fail-under=0 -d coverage/
            python -m coverage report --rcfile=.coveragerc --fail-under=0
            echo ""
            echo "HTML report: ./coverage/index.html"
          '';

          seed = mkApp "timeout-seed" ''
            ${guard}
            python manage.py seed
          '';

          unseed = mkApp "timeout-unseed" ''
            ${guard}
            python manage.py unseed
          '';
        };

        # Dev shell

        devShells.default = pkgs.mkShell {
          buildInputs = [ pythonEnv ];
          shellHook = ''
            export DJANGO_SETTINGS_MODULE=timeout_pwa.settings
            echo "Timeout dev shell — python $(python --version)"
          '';
        };
      }
    );
}
