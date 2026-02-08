"""
Credential Manager

Handles encrypted storage of OAuth tokens and API credentials.
Uses Fernet symmetric encryption with master key from environment.

Supports Gold Tier requirements:
- FR-031: Store OAuth tokens encrypted in environment variables or secrets manager
- FR-032: Never log or expose credentials in audit entries or error messages
"""

import os
import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
from cryptography.fernet import Fernet, InvalidToken


class CredentialManagerError(Exception):
    """Base exception for credential manager errors."""
    pass


class EncryptionKeyError(CredentialManagerError):
    """Raised when encryption key is missing or invalid."""
    pass


class CredentialNotFoundError(CredentialManagerError):
    """Raised when requested credential is not found."""
    pass


class CredentialManager:
    """
    Manages encrypted storage of OAuth tokens and API credentials.

    Uses Fernet symmetric encryption with a master key stored in
    the GOLD_MASTER_KEY environment variable.

    Per FR-031: Credentials stored encrypted, not plain text
    Per FR-032: Credentials never logged or exposed
    """

    MASTER_KEY_ENV = "GOLD_MASTER_KEY"

    def __init__(self, vault_path: Optional[str] = None):
        """
        Initialize credential manager.

        Args:
            vault_path: Path to vault directory. Defaults to VAULT_PATH env var.
        """
        self.vault_path = vault_path or os.environ.get("VAULT_PATH", "./obsidian-vault")
        self._fernet: Optional[Fernet] = None
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure vault config directory exists."""
        config_dir = Path(self.vault_path) / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

    def _get_fernet(self) -> Fernet:
        """Get or create Fernet cipher instance."""
        if self._fernet is None:
            key = os.environ.get(self.MASTER_KEY_ENV)
            if not key:
                raise EncryptionKeyError(
                    f"Missing {self.MASTER_KEY_ENV} environment variable. "
                    "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            try:
                self._fernet = Fernet(key.encode())
            except Exception as e:
                raise EncryptionKeyError(f"Invalid encryption key: {e}")
        return self._fernet

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        fernet = self._get_fernet()
        return fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string

        Raises:
            CredentialManagerError: If decryption fails
        """
        try:
            fernet = self._get_fernet()
            return fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            raise CredentialManagerError("Failed to decrypt credential - invalid key or corrupted data")

    def _get_credentials_file(self, service: str) -> Path:
        """Get path to credentials file for a service."""
        return Path(self.vault_path) / "config" / f"{service}-connection.yaml"

    def save_credentials(self, service: str, credentials: Dict[str, Any]) -> None:
        """
        Save encrypted credentials for a service.

        Args:
            service: Service name (e.g., "xero", "meta", "twitter")
            credentials: Credential dictionary with tokens
        """
        # Encrypt sensitive fields
        encrypted = {}
        sensitive_fields = {"access_token", "refresh_token", "client_secret", "api_key"}

        for key, value in credentials.items():
            if key in sensitive_fields and value:
                encrypted[key] = self.encrypt(str(value))
            else:
                encrypted[key] = value

        # Add metadata
        encrypted["_encrypted_fields"] = list(sensitive_fields & set(credentials.keys()))
        encrypted["_updated_at"] = datetime.utcnow().isoformat()

        # Save to file
        file_path = self._get_credentials_file(service)
        with open(file_path, "w") as f:
            yaml.dump(encrypted, f, default_flow_style=False)

    def load_credentials(self, service: str) -> Dict[str, Any]:
        """
        Load and decrypt credentials for a service.

        Args:
            service: Service name

        Returns:
            Decrypted credential dictionary

        Raises:
            CredentialNotFoundError: If credentials file not found
        """
        file_path = self._get_credentials_file(service)

        if not file_path.exists():
            raise CredentialNotFoundError(f"No credentials found for service: {service}")

        with open(file_path, "r") as f:
            encrypted = yaml.safe_load(f)

        if not encrypted:
            raise CredentialNotFoundError(f"Empty credentials file for service: {service}")

        # Decrypt sensitive fields
        encrypted_fields = encrypted.pop("_encrypted_fields", [])
        encrypted.pop("_updated_at", None)

        decrypted = {}
        for key, value in encrypted.items():
            if key in encrypted_fields and value:
                decrypted[key] = self.decrypt(value)
            else:
                decrypted[key] = value

        return decrypted

    def delete_credentials(self, service: str) -> bool:
        """
        Delete credentials for a service.

        Args:
            service: Service name

        Returns:
            True if deleted, False if not found
        """
        file_path = self._get_credentials_file(service)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def has_credentials(self, service: str) -> bool:
        """Check if credentials exist for a service."""
        return self._get_credentials_file(service).exists()

    def get_token_expiry(self, service: str) -> Optional[datetime]:
        """
        Get token expiry time for a service.

        Returns None if no expiry set or credentials not found.
        """
        try:
            creds = self.load_credentials(service)
            expiry = creds.get("token_expiry")
            if expiry:
                if isinstance(expiry, str):
                    return datetime.fromisoformat(expiry)
                return expiry
        except CredentialNotFoundError:
            pass
        return None

    def is_token_expired(self, service: str, buffer_hours: int = 24) -> bool:
        """
        Check if token is expired or will expire within buffer period.

        Args:
            service: Service name
            buffer_hours: Hours before expiry to consider "expired"

        Returns:
            True if expired or expiring soon, False otherwise
        """
        from datetime import timedelta

        expiry = self.get_token_expiry(service)
        if expiry is None:
            return True  # No expiry means we should refresh

        buffer = timedelta(hours=buffer_hours)
        return datetime.utcnow() + buffer >= expiry

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key."""
        return Fernet.generate_key().decode()

    def rotate_key(self, new_key: str) -> None:
        """
        Re-encrypt all credentials with a new key.

        Args:
            new_key: New Fernet encryption key
        """
        # Load all credentials with current key
        config_dir = Path(self.vault_path) / "config"
        services = []

        for file_path in config_dir.glob("*-connection.yaml"):
            service = file_path.stem.replace("-connection", "")
            try:
                creds = self.load_credentials(service)
                services.append((service, creds))
            except CredentialManagerError:
                continue

        # Switch to new key
        self._fernet = Fernet(new_key.encode())

        # Re-save all credentials with new key
        for service, creds in services:
            self.save_credentials(service, creds)
