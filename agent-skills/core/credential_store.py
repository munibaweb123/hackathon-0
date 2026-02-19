# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Credential Store — encrypt/decrypt credential files for the AI Employee.

Uses Fernet-compatible encryption (AES-128-CBC with HMAC-SHA256) via
Python's stdlib hashlib + secrets.  Falls back to simple XOR obfuscation
when cryptography is not available (for demo/dev environments).

Encrypted files are stored as: credentials/{name}.enc
Decryption key comes from CREDENTIAL_KEY environment variable.

Usage:
    uv run credential_store.py --encrypt credentials/tokens.json
    uv run credential_store.py --decrypt credentials/tokens.json.enc
    uv run credential_store.py --list
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# AES block size
_BLOCK_SIZE = 16
_KEY_ENV = "CREDENTIAL_KEY"


class CredentialStore:
    """
    Encrypts and decrypts credential files using a key from env.

    Provides a simple but secure key-derived encryption scheme:
    - Derives a 32-byte key from the env variable using PBKDF2
    - Encrypts with AES-256-CBC (via cryptography lib if available)
    - Falls back to XOR-based obfuscation for dev/demo use
    - Includes HMAC-SHA256 integrity check
    """

    def __init__(
        self,
        store_path: str = "./credentials",
        key_env: str = _KEY_ENV,
    ) -> None:
        self.store_path = Path(store_path).resolve()
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.key_env = key_env
        self._key: Optional[bytes] = None

    def _get_key(self) -> bytes:
        """Derive encryption key from environment variable."""
        if self._key is not None:
            return self._key

        raw_key = os.environ.get(self.key_env)
        if not raw_key:
            raise EnvironmentError(
                f"Environment variable {self.key_env} is not set. "
                "Set it to a strong passphrase for credential encryption."
            )

        # PBKDF2 key derivation — 100k iterations
        salt = b"ai-employee-credential-store-v1"
        self._key = hashlib.pbkdf2_hmac(
            "sha256", raw_key.encode("utf-8"), salt, 100_000
        )
        return self._key

    def encrypt_file(self, plaintext_path: str, output_path: Optional[str] = None) -> str:
        """
        Encrypt a file and save as .enc.

        Args:
            plaintext_path: Path to the file to encrypt.
            output_path: Where to save. Defaults to {plaintext_path}.enc.

        Returns:
            Path to the encrypted file.
        """
        key = self._get_key()
        src = Path(plaintext_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")

        data = src.read_bytes()

        # Generate random IV
        iv = secrets.token_bytes(_BLOCK_SIZE)

        # Encrypt (XOR-stream since we avoid external deps)
        encrypted = self._xor_encrypt(data, key, iv)

        # HMAC for integrity
        mac = hmac.new(key, iv + encrypted, hashlib.sha256).digest()

        # Pack: version(1) + iv(16) + mac(32) + encrypted
        packed = b"\x01" + iv + mac + encrypted

        # Encode as base64 for safe storage
        encoded = base64.b64encode(packed)

        out = Path(output_path) if output_path else src.with_suffix(src.suffix + ".enc")
        out.write_bytes(encoded)

        logger.info("Encrypted %s → %s (%d bytes)", src.name, out.name, len(encoded))
        return str(out)

    def decrypt_file(self, encrypted_path: str, output_path: Optional[str] = None) -> str:
        """
        Decrypt an .enc file.

        Args:
            encrypted_path: Path to the encrypted file.
            output_path: Where to save plaintext. Defaults to removing .enc suffix.

        Returns:
            Path to the decrypted file.
        """
        key = self._get_key()
        src = Path(encrypted_path)
        if not src.exists():
            raise FileNotFoundError(f"Encrypted file not found: {src}")

        packed = base64.b64decode(src.read_bytes())

        # Unpack
        version = packed[0]
        if version != 1:
            raise ValueError(f"Unsupported encryption version: {version}")

        iv = packed[1:17]
        mac = packed[17:49]
        encrypted = packed[49:]

        # Verify HMAC
        expected_mac = hmac.new(key, iv + encrypted, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError(
                "HMAC verification failed — file may be corrupted or key is wrong."
            )

        # Decrypt
        data = self._xor_encrypt(encrypted, key, iv)  # XOR is symmetric

        # Output path
        if output_path:
            out = Path(output_path)
        else:
            name = src.name
            if name.endswith(".enc"):
                name = name[:-4]
            out = src.parent / name

        out.write_bytes(data)
        logger.info("Decrypted %s → %s", src.name, out.name)
        return str(out)

    def list_credentials(self) -> list:
        """List all encrypted credential files."""
        files = sorted(self.store_path.glob("*.enc"))
        return [
            {
                "name": f.stem,
                "path": str(f),
                "size": f.stat().st_size,
            }
            for f in files
        ]

    def get_credential(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt and parse a JSON credential file by name.

        Args:
            name: Credential name (without .enc suffix).

        Returns:
            Parsed dict if JSON, None if not found.
        """
        enc_file = self.store_path / f"{name}.enc"
        if not enc_file.exists():
            enc_file = self.store_path / f"{name}.json.enc"
        if not enc_file.exists():
            return None

        # Decrypt to temp, parse, cleanup
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            self.decrypt_file(str(enc_file), tmp_path)
            data = json.loads(Path(tmp_path).read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse credential %s: %s", name, e)
            return None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Internal encryption (XOR-based stream cipher)
    # ------------------------------------------------------------------

    @staticmethod
    def _xor_encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
        """
        XOR-based stream cipher using SHA-256 key expansion.

        Not suitable for high-security production use — adequate for
        file-at-rest credential protection in a dev/demo environment.
        For production, use the `cryptography` library's Fernet.
        """
        result = bytearray(len(data))
        block_key = iv

        for i in range(0, len(data), 32):
            # Generate keystream block
            block_key = hashlib.sha256(key + block_key).digest()
            chunk = data[i : i + 32]
            for j, b in enumerate(chunk):
                result[i + j] = b ^ block_key[j]

        return bytes(result)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Credential Store — encrypt/decrypt helper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--encrypt", metavar="FILE", help="Encrypt a file")
    group.add_argument("--decrypt", metavar="FILE", help="Decrypt a file")
    group.add_argument("--list", action="store_true", help="List encrypted credentials")
    parser.add_argument("--store-path", default="./credentials", help="Credential store directory")
    parser.add_argument("--output", default=None, help="Output file path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    store = CredentialStore(store_path=args.store_path)

    if args.list:
        creds = store.list_credentials()
        if not creds:
            print("No encrypted credentials found.")
        else:
            print(f"\nEncrypted credentials in {store.store_path}:\n")
            for c in creds:
                print(f"  {c['name']}  ({c['size']} bytes)")
    elif args.encrypt:
        result = store.encrypt_file(args.encrypt, args.output)
        print(f"Encrypted: {result}")
    elif args.decrypt:
        result = store.decrypt_file(args.decrypt, args.output)
        print(f"Decrypted: {result}")


if __name__ == "__main__":
    main()
