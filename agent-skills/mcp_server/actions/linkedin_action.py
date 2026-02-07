"""
LinkedIn Action Module

This module handles LinkedIn posting actions through the MCP server.
It implements proper validation and security checks before posting to LinkedIn.
"""

from typing import Dict, Any, Optional
import uuid
from ...core.logger import Logger


class LinkedInAction:
    """
    Handles LinkedIn posting actions through the MCP server.
    Implements proper validation and security checks before posting to LinkedIn.
    """

    def __init__(self, logger: Optional[Logger] = None):
        """
        Initialize the LinkedIn action handler.

        Args:
            logger: Logger instance for auditability
        """
        self.logger = logger

    def execute(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the LinkedIn posting action.

        Args:
            action_data: Dictionary containing LinkedIn post parameters

        Returns:
            Dictionary with execution result
        """
        try:
            # Extract post parameters
            content = action_data.get('content', '')
            visibility = action_data.get('visibility', 'PUBLIC')  # PUBLIC, CONNECTIONS_ONLY
            hashtags = action_data.get('hashtags', [])
            media_urls = action_data.get('media_urls', [])

            # Validate post parameters
            if not self.validate_post_params(content, visibility, hashtags, media_urls):
                return {
                    "success": False,
                    "error": "Invalid LinkedIn post parameters",
                    "post_id": None
                }

            # For demo purposes, we'll simulate posting to LinkedIn
            # In a real implementation, this would connect to LinkedIn API
            post_id = self._simulate_post_to_linkedin(content, visibility, hashtags, media_urls)

            if self.logger:
                self.logger.log_system_event(
                    event_type="linkedin_posted",
                    component="linkedin_action",
                    message="LinkedIn post created successfully",
                    details={
                        "content_preview": content[:50] + "..." if len(content) > 50 else content,
                        "visibility": visibility,
                        "post_id": post_id
                    }
                )

            return {
                "success": True,
                "post_id": post_id,
                "details": f"LinkedIn post created with visibility '{visibility}'"
            }

        except Exception as e:
            if self.logger:
                self.logger.log_system_event(
                    event_type="linkedin_error",
                    component="linkedin_action",
                    message=f"Error creating LinkedIn post: {e}",
                    details={"action_data": action_data}
                )

            return {
                "success": False,
                "error": str(e),
                "post_id": None
            }

    def validate_post_params(self, content: str, visibility: str, hashtags: list, media_urls: list) -> bool:
        """
        Validate LinkedIn post parameters before posting.

        Args:
            content: The post content
            visibility: The visibility setting (PUBLIC, CONNECTIONS_ONLY)
            hashtags: List of hashtags
            media_urls: List of media URLs to attach

        Returns:
            True if parameters are valid, False otherwise
        """
        # Check if content is provided
        if not content or not isinstance(content, str) or len(content.strip()) == 0:
            if self.logger:
                self.logger.log_system_event(
                    event_type="validation_error",
                    component="linkedin_action",
                    message="No content provided for LinkedIn post",
                    details={"content_length": len(content) if content else 0}
                )
            return False

        # Check content length limits (LinkedIn has a 3000 character limit)
        if len(content) > 3000:
            if self.logger:
                self.logger.log_system_event(
                    event_type="validation_error",
                    component="linkedin_action",
                    message="LinkedIn post content exceeds character limit",
                    details={"content_length": len(content), "limit": 3000}
                )
            return False

        # Validate visibility setting
        valid_visibilities = ['PUBLIC', 'CONNECTIONS_ONLY']
        if visibility.upper() not in valid_visibilities:
            if self.logger:
                self.logger.log_system_event(
                    event_type="validation_error",
                    component="linkedin_action",
                    message=f"Invalid visibility setting: {visibility}",
                    details={"valid_options": valid_visibilities}
                )
            return False

        # Validate hashtags
        if hashtags and not isinstance(hashtags, list):
            if self.logger:
                self.logger.log_system_event(
                    event_type="validation_error",
                    component="linkedin_action",
                    message="Hashtags must be provided as a list",
                    details={"hashtags_type": type(hashtags).__name__}
                )
            return False

        # Limit number of hashtags (LinkedIn recommends no more than 3-5)
        if hashtags and len(hashtags) > 5:
            if self.logger:
                self.logger.log_system_event(
                    event_type="validation_warning",
                    component="linkedin_action",
                    message=f"Too many hashtags: {len(hashtags)} (recommended maximum: 5)",
                    details={"hashtags_count": len(hashtags)}
                )

        # Validate media URLs
        if media_urls and not isinstance(media_urls, list):
            if self.logger:
                self.logger.log_system_event(
                    event_type="validation_error",
                    component="linkedin_action",
                    message="Media URLs must be provided as a list",
                    details={"media_urls_type": type(media_urls).__name__}
                )
            return False

        # Check if media URLs are valid format (basic validation)
        if media_urls:
            import re
            url_pattern = re.compile(
                r'http[s]?://'  # http:// or https://
                r'(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'  # URL characters
            )

            for url in media_urls:
                if not isinstance(url, str) or not url_pattern.match(url):
                    if self.logger:
                        self.logger.log_system_event(
                            event_type="validation_error",
                            component="linkedin_action",
                            message=f"Invalid media URL format: {url}",
                            details={"media_urls": media_urls}
                        )
                    return False

        return True

    def _simulate_post_to_linkedin(self, content: str, visibility: str, hashtags: list, media_urls: list) -> str:
        """
        Simulate posting to LinkedIn (for demo purposes).
        In a real implementation, this would connect to LinkedIn API.

        Args:
            content: The post content
            visibility: The visibility setting
            hashtags: List of hashtags to include
            media_urls: List of media URLs to attach

        Returns:
            Mock post ID
        """
        # Create a mock post ID
        post_id = f"post_{uuid.uuid4()}"

        # In a real implementation, this would:
        # 1. Connect to LinkedIn API using OAuth token from environment
        # 2. Prepare the post payload
        # 3. Submit the post
        # 4. Handle any errors

        print(f"SIMULATED: LinkedIn post created")
        print(f"Content preview: {content[:100]}...")
        print(f"Visibility: {visibility}")
        print(f"Hashtags: {hashtags}")
        print(f"Media URLs: {media_urls}")
        print(f"Post ID: {post_id}")

        return post_id

    def validate_business_alignment(self, content: str) -> bool:
        """
        Validate that the post content aligns with business goals.

        Args:
            content: The post content to validate

        Returns:
            True if content aligns with business goals, False otherwise
        """
        # In a real implementation, this would check against business rules
        # For demo purposes, we'll just check for basic appropriateness

        # Check for inappropriate content
        inappropriate_terms = [
            'spam', 'scam', 'click here', 'buy now', '$$$',
            'free money', 'get rich quick', 'investment opportunity'
        ]

        lower_content = content.lower()
        for term in inappropriate_terms:
            if term in lower_content:
                if self.logger:
                    self.logger.log_system_event(
                        event_type="content_validation_error",
                        component="linkedin_action",
                        message=f"Inappropriate content detected: {term}",
                        details={"content_preview": content[:50]}
                    )
                return False

        return True