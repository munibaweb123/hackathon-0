"""
Post Manager Module

Manages LinkedIn post lifecycle: draft → pending_approval → approved → published.
Creates and tracks post files in the vault posts folder.

Task T044: Create Post entity file management
Task T045: Implement post status tracking
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.vault_interface import VaultInterface
from core.logger import Logger


class PostManager:
    """
    Manages LinkedIn post files in the vault.
    Tracks status transitions: draft → pending_approval → approved → published → failed.
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger):
        self.vault = vault_interface
        self.logger = logger

    def create_post(
        self,
        content: str,
        generation_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Create a new post draft in the vault.

        Args:
            content: Post content text
            generation_context: How the post was generated (manual, AI, etc.)

        Returns:
            Post metadata dict
        """
        post_id = str(uuid.uuid4())
        now = datetime.utcnow()
        filename = f"POST_{now.strftime('%Y-%m-%d_%H%M%S')}_{post_id[:8]}.md"

        metadata = {
            "id": post_id,
            "type": "linkedin_post",
            "status": "draft",
            "created_at": now.isoformat() + "Z",
            "content_length": len(content),
        }

        if generation_context:
            metadata["generation_context"] = generation_context

        md_content = f"""# LinkedIn Post Draft

**Status**: Draft
**Created**: {now.strftime('%Y-%m-%d %H:%M UTC')}

## Content

{content}

---
_Post managed by AI Employee_
"""

        file_path = self.vault.write_event_file(
            filename=filename,
            metadata=metadata,
            content=md_content,
            destination_folder="posts",
        )

        self.logger.log_system_event(
            event_type="post_created",
            component="post_manager",
            message=f"Post draft created ({len(content)} chars)",
            details={"post_id": post_id, "file_path": str(file_path)},
        )

        return {
            "id": post_id,
            "content": content,
            "status": "draft",
            "file_path": str(file_path),
            "filename": filename,
            "created_at": now.isoformat(),
        }

    def update_status(
        self,
        post_path: str,
        new_status: str,
        extra_metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Update a post's status.

        Args:
            post_path: Path to the post file
            new_status: New status value
            extra_metadata: Additional metadata to merge

        Returns:
            True if successful
        """
        try:
            data = self.vault.read_event_file(post_path)
            metadata = data.get("metadata", {})
            metadata["status"] = new_status
            metadata[f"{new_status}_at"] = datetime.utcnow().isoformat() + "Z"

            if extra_metadata:
                metadata.update(extra_metadata)

            content = data.get("content", "")
            filename = post_path.split("/")[-1] if "/" in str(post_path) else str(post_path)

            self.vault.write_event_file(
                filename=filename,
                metadata=metadata,
                content=content,
                destination_folder="posts",
            )

            self.logger.log_system_event(
                event_type="post_status_updated",
                component="post_manager",
                message=f"Post status: {new_status}",
                details={"post_path": post_path, "status": new_status},
            )
            return True
        except Exception as e:
            self.logger.log_system_event(
                event_type="post_update_error",
                component="post_manager",
                message=f"Failed to update post: {e}",
            )
            return False

    def mark_published(
        self,
        post_path: str,
        linkedin_post_id: str,
    ) -> bool:
        """Mark a post as published with the LinkedIn post ID."""
        return self.update_status(
            post_path,
            "published",
            extra_metadata={"linkedin_post_id": linkedin_post_id},
        )

    def mark_failed(self, post_path: str, error_message: str) -> bool:
        """Mark a post as failed with error details."""
        return self.update_status(
            post_path,
            "failed",
            extra_metadata={"error_message": error_message},
        )

    def get_posts_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all posts with a given status."""
        posts = []
        for file_path in self.vault.get_posts():
            try:
                data = self.vault.read_event_file(file_path)
                metadata = data.get("metadata", {})
                if metadata.get("status") == status:
                    posts.append({
                        "file_path": str(file_path),
                        "metadata": metadata,
                        "content": data.get("content", ""),
                    })
            except Exception:
                pass
        return posts

    def get_all_posts(self) -> List[Dict[str, Any]]:
        """Get all posts from the vault."""
        posts = []
        for file_path in self.vault.get_posts():
            try:
                data = self.vault.read_event_file(file_path)
                posts.append({
                    "file_path": str(file_path),
                    "metadata": data.get("metadata", {}),
                    "content": data.get("content", ""),
                })
            except Exception:
                pass
        return posts
