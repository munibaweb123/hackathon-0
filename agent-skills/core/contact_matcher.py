"""
Contact Matcher

Links contacts across platforms (Xero, Facebook, Twitter, Gmail, LinkedIn)
using email as the primary matching key, with manual linking support.

Supports Gold Tier requirements:
- FR-022: Link contacts across platforms using email as primary key
- FR-023: Provide unified contact context in AI reasoning
"""

import os
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from threading import Lock


class ContactMatcher:
    """
    Matches and links contacts across platforms.

    Uses email as the primary matching key. Stores unified contacts
    as YAML files in the vault for persistence.

    Per FR-022: Email-based matching across Xero, Meta, Twitter
    Per FR-023: Unified context available to reasoning loop
    """

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = vault_path or os.environ.get("VAULT_PATH", "./obsidian-vault")
        self._lock = Lock()
        self._contacts_dir = Path(self.vault_path) / "contacts" / "unified"
        self._contacts_dir.mkdir(parents=True, exist_ok=True)

    def _get_contact_file(self, contact_id: str) -> Path:
        """Get path to a contact file."""
        return self._contacts_dir / f"{contact_id}.yaml"

    def _load_all_contacts(self) -> List[Dict[str, Any]]:
        """Load all unified contacts from disk."""
        contacts = []
        for f in self._contacts_dir.glob("*.yaml"):
            try:
                with open(f, "r") as fh:
                    data = yaml.safe_load(fh)
                    if data:
                        contacts.append(data)
            except Exception:
                continue
        return contacts

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find a unified contact by email address.

        Args:
            email: Email address to search for

        Returns:
            Contact dict or None
        """
        email_lower = email.lower()
        for contact in self._load_all_contacts():
            if contact.get("primary_email", "").lower() == email_lower:
                return contact
            for identity in contact.get("identities", []):
                if identity.get("email", "").lower() == email_lower:
                    return contact
        return None

    def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a unified contact by display name.

        Args:
            name: Display name to search for

        Returns:
            Contact dict or None
        """
        name_lower = name.lower()
        for contact in self._load_all_contacts():
            if contact.get("display_name", "").lower() == name_lower:
                return contact
        return None

    def find_by_platform_id(self, platform: str, platform_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a unified contact by platform-specific ID.

        Args:
            platform: Platform name (xero, facebook, twitter, gmail, linkedin)
            platform_id: ID on that platform

        Returns:
            Contact dict or None
        """
        for contact in self._load_all_contacts():
            for identity in contact.get("identities", []):
                if (identity.get("platform") == platform and
                        identity.get("platform_id") == platform_id):
                    return contact
        return None

    def create_or_update(
        self,
        email: str,
        display_name: str,
        platform: str,
        platform_id: str,
        company: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new unified contact or update an existing one.

        If a contact with the given email exists, adds the platform
        identity to it. Otherwise creates a new contact.

        Args:
            email: Primary email
            display_name: Display name
            platform: Platform name
            platform_id: Platform-specific ID
            company: Company name
            notes: Additional notes

        Returns:
            Created or updated contact dict
        """
        import uuid

        with self._lock:
            existing = self.find_by_email(email)

            if existing:
                # Add identity if not already present
                identities = existing.get("identities", [])
                already_linked = any(
                    i.get("platform") == platform and i.get("platform_id") == platform_id
                    for i in identities
                )
                if not already_linked:
                    identities.append({
                        "platform": platform,
                        "platform_id": platform_id,
                        "email": email,
                        "linked_by": "auto_email",
                        "linked_at": datetime.utcnow().isoformat() + "Z",
                        "confidence": 1.0,
                    })
                    existing["identities"] = identities
                    existing["updated_at"] = datetime.utcnow().isoformat() + "Z"

                    if company and not existing.get("company"):
                        existing["company"] = company

                    # Save
                    filepath = self._get_contact_file(existing["id"])
                    with open(filepath, "w") as f:
                        yaml.dump(existing, f, default_flow_style=False)

                return existing

            # Create new contact
            contact_id = str(uuid.uuid4())[:8]
            now = datetime.utcnow().isoformat() + "Z"

            contact = {
                "id": contact_id,
                "primary_email": email,
                "display_name": display_name,
                "company": company or "",
                "notes": notes or "",
                "created_at": now,
                "updated_at": now,
                "identities": [
                    {
                        "platform": platform,
                        "platform_id": platform_id,
                        "email": email,
                        "linked_by": "auto_email",
                        "linked_at": now,
                        "confidence": 1.0,
                    }
                ],
            }

            filepath = self._get_contact_file(contact_id)
            with open(filepath, "w") as f:
                yaml.dump(contact, f, default_flow_style=False)

            return contact

    def manual_link(
        self,
        contact_id: str,
        platform: str,
        platform_id: str,
        email: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Manually link a platform identity to an existing contact.

        Args:
            contact_id: Existing contact ID
            platform: Platform name
            platform_id: Platform-specific ID
            email: Optional email for this identity

        Returns:
            Updated contact or None if not found
        """
        with self._lock:
            filepath = self._get_contact_file(contact_id)
            if not filepath.exists():
                return None

            with open(filepath, "r") as f:
                contact = yaml.safe_load(f)

            identities = contact.get("identities", [])
            identities.append({
                "platform": platform,
                "platform_id": platform_id,
                "email": email or "",
                "linked_by": "manual",
                "linked_at": datetime.utcnow().isoformat() + "Z",
                "confidence": 1.0,
            })
            contact["identities"] = identities
            contact["updated_at"] = datetime.utcnow().isoformat() + "Z"

            with open(filepath, "w") as f:
                yaml.dump(contact, f, default_flow_style=False)

            return contact

    def get_all_contacts(self) -> List[Dict[str, Any]]:
        """Get all unified contacts."""
        return self._load_all_contacts()

    def get_contact_context(self, email: str) -> Optional[str]:
        """
        Get formatted cross-domain context string for a contact.

        Used by the reasoning loop to enrich event analysis.

        Args:
            email: Email to look up

        Returns:
            Formatted context string or None
        """
        contact = self.find_by_email(email)
        if not contact:
            return None

        platforms = [i.get("platform", "") for i in contact.get("identities", [])]
        company = contact.get("company", "")
        name = contact.get("display_name", email)

        parts = [f"Contact: {name}"]
        if company:
            parts.append(f"Company: {company}")
        parts.append(f"Known on: {', '.join(platforms)}")

        return " | ".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get contact matching statistics."""
        contacts = self._load_all_contacts()
        platform_counts: Dict[str, int] = {}

        for contact in contacts:
            for identity in contact.get("identities", []):
                platform = identity.get("platform", "unknown")
                platform_counts[platform] = platform_counts.get(platform, 0) + 1

        return {
            "total_contacts": len(contacts),
            "platforms": platform_counts,
            "multi_platform": sum(
                1 for c in contacts if len(c.get("identities", [])) > 1
            ),
        }
