"""
LinkedIn Content Skill

Generates business-relevant LinkedIn post content using Claude.
Posts go through the approval workflow before publishing.

Task T040: Create LinkedInContentSkill for post generation
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional

from core.base_skill import BaseSkill, SkillResult
from core.vault_interface import VaultInterface
from core.logger import Logger
from core.post_manager import PostManager
from core.approval_generator import ApprovalGenerator


class LinkedInContentSkill(BaseSkill):
    """
    Generates LinkedIn post content using Claude and creates approval requests.
    All posts require human approval before publishing.
    """

    def __init__(
        self,
        vault_interface: VaultInterface,
        logger: Logger,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        super().__init__(
            name="linkedin_content",
            vault_interface=vault_interface,
            logger=logger,
        )
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.post_manager = PostManager(vault_interface, logger)
        self.approval_generator = ApprovalGenerator(vault_interface, logger)
        self._client = None

    @property
    def id(self) -> str:
        return "linkedin_content"

    @property
    def description(self) -> str:
        return "Generates business-relevant LinkedIn post content"

    def _get_client(self):
        """Lazy-initialize the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except Exception:
                return None
        return self._client

    async def execute_async(self, input_data: Dict[str, Any]) -> SkillResult:
        """
        Generate a LinkedIn post and create an approval request.

        Args:
            input_data: Dict with optional keys:
                - topic: Topic for the post
                - tone: Desired tone (professional, casual, thought-leader)
                - context: Additional context
                - manual_content: If provided, skip generation and use this content

        Returns:
            SkillResult with post and approval data
        """
        manual_content = input_data.get("manual_content")

        if manual_content:
            content = manual_content
        else:
            content = self._generate_content(input_data)

        if not content:
            return SkillResult(
                success=False,
                error="Failed to generate LinkedIn content",
            )

        # Create post draft
        post_data = self.post_manager.create_post(
            content=content,
            generation_context={
                "source": "ai_generated" if not manual_content else "manual",
                "topic": input_data.get("topic", ""),
                "model": self.model,
            },
        )

        # Update to pending_approval
        self.post_manager.update_status(post_data["file_path"], "pending_approval")

        # Create approval request
        approval = self.approval_generator.create_approval_request(
            action_type="linkedin_post",
            description=f"Publish LinkedIn post: {content[:80]}...",
            context=f"AI-generated LinkedIn post about: {input_data.get('topic', 'business')}",
            plan_id=input_data.get("plan_id", ""),
            proposed_content=content,
            risk_level="medium",
        )

        return SkillResult(
            success=True,
            data={
                "post": post_data,
                "approval": approval,
                "content_preview": content[:200],
            },
        )

    def _generate_content(self, input_data: Dict[str, Any]) -> Optional[str]:
        """Generate LinkedIn content using Claude."""
        client = self._get_client()

        topic = input_data.get("topic", "business insights")
        tone = input_data.get("tone", "professional")
        context = input_data.get("context", "")

        prompt = f"""Generate a LinkedIn post for a business professional.

Topic: {topic}
Tone: {tone}
{f'Additional context: {context}' if context else ''}

Requirements:
- Keep it under 1300 characters (LinkedIn optimal length)
- Use a hook in the first line
- Include 2-3 relevant hashtags at the end
- Sound authentic, not robotic
- Focus on providing value to the reader

Return ONLY the post content, no explanations."""

        if not client:
            # Fallback: return a template
            return f"""Sharing some thoughts on {topic}.

In my experience, the key to success in this area is consistency and continuous learning.

What are your thoughts? I'd love to hear your perspective in the comments.

#Business #{topic.replace(' ', '')} #ProfessionalGrowth"""

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            if self.logger:
                self.logger.log_system_event(
                    event_type="content_generation_error",
                    component="linkedin_content_skill",
                    message=f"Claude content generation failed: {e}",
                )
            return None
