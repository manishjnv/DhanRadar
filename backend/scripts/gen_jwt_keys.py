"""
DhanRadar — Dev RSA keypair generator for JWT RS256 signing.

Writes a 2048-bit RSA private + public key pair to backend/.keys/.
These keys are for LOCAL DEVELOPMENT ONLY — never use them in production.

Usage (from repo root):
    python backend/scripts/gen_jwt_keys.py

Output files:
    backend/.keys/jwt_private.pem   — RSA private key (PEM, PKCS8)
    backend/.keys/jwt_public.pem    — RSA public key  (PEM)

After generation, set in your .env:
    JWT_PRIVATE_KEY="$(cat backend/.keys/jwt_private.pem)"
    JWT_PUBLIC_KEY="$(cat backend/.keys/jwt_public.pem)"

Or, for multi-line PEM in .env on Windows, copy the PEM content with
literal \\n line endings:
    python backend/scripts/gen_jwt_keys.py --print-env

Security notes:
  - backend/.keys/ is gitignored (added to root .gitignore).
  - *.pem is gitignored at root level.
  - NEVER commit these files to version control.
  - Rotate keys by re-running this script and redeploying.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate RSA keypair for DhanRadar JWT RS256 signing (dev only)."
    )
    parser.add_argument(
        "--print-env",
        action="store_true",
        help="Print JWT_PRIVATE_KEY and JWT_PUBLIC_KEY as single-line env vars.",
    )
    args = parser.parse_args()

    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        print(
            "ERROR: 'cryptography' package not found.\n"
            "Install it with: pip install cryptography\n"
            "(It is pulled in transitively by pyjwt[crypto].)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Determine output directory relative to this script's location.
    script_dir = Path(__file__).resolve().parent
    keys_dir = script_dir.parent / ".keys"
    keys_dir.mkdir(mode=0o700, exist_ok=True)

    private_key_path = keys_dir / "jwt_private.pem"
    public_key_path = keys_dir / "jwt_public.pem"

    # Generate 2048-bit RSA key (minimum for RS256; use 4096 in production).
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    # Serialise to PEM (PKCS8 for private key, SubjectPublicKeyInfo for public).
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Write files with restricted permissions.
    private_key_path.write_bytes(private_pem)
    os.chmod(private_key_path, 0o600)
    public_key_path.write_bytes(public_pem)
    os.chmod(public_key_path, 0o644)

    print(f"[OK] Private key written to: {private_key_path}")
    print(f"[OK] Public key  written to: {public_key_path}")
    print()
    print("Add to your .env file:")
    print('  JWT_PRIVATE_KEY="$(cat backend/.keys/jwt_private.pem)"')
    print('  JWT_PUBLIC_KEY="$(cat backend/.keys/jwt_public.pem)"')

    if args.print_env:
        print()
        print("=== Single-line env vars (copy into .env) ===")
        priv_inline = private_pem.decode().replace("\n", "\\n")
        pub_inline = public_pem.decode().replace("\n", "\\n")
        print(f'JWT_PRIVATE_KEY="{priv_inline}"')
        print(f'JWT_PUBLIC_KEY="{pub_inline}"')


if __name__ == "__main__":
    main()
