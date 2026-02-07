"""
Communication Skill Module

This module drafts professional emails and LinkedIn posts based on context.
It prepares message payloads only and does not send them directly.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from core.base_skill import BaseSkill
from core.vault_interface import VaultInterface
from core.logger import Logger


class CommunicationSkill(BaseSkill):
    """
    Drafts professional emails and LinkedIn posts based on context.
    Prepares message payloads only (does not send).
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger):
        """
        Initialize the communication skill.

        Args:
            vault_interface: Interface for vault operations
            logger: Logger instance for auditability
        """
        super().__init__("communication", vault_interface, logger)

    def execute(self, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute the communication skill with the given input data.

        Args:
            input_data: Input data for the skill, expected to contain:
                - 'communication_type': 'email' or 'linkedin_post'
                - 'context': Context for generating the communication
                - 'recipient_info': Information about the recipient (for emails)
                - 'post_topic': Topic for the LinkedIn post (for LinkedIn posts)

        Returns:
            Output data from the skill execution or None if failed
        """
        if not self.validate_input(input_data):
            return None

        try:
            # Extract required parameters
            communication_type = input_data.get('communication_type', '').lower()
            context = input_data.get('context', '')
            recipient_info = input_data.get('recipient_info', {})
            post_topic = input_data.get('post_topic', '')

            if not communication_type:
                self.logger.log_system_event(
                    event_type="communication_error",
                    component="communication_skill",
                    message="Missing communication_type in input",
                    details=input_data
                )
                return None

            # Generate the communication based on type
            if communication_type == 'email':
                result = self.generate_email(context, recipient_info)
            elif communication_type == 'linkedin_post':
                result = self.generate_linkedin_post(context, post_topic)
            else:
                self.logger.log_system_event(
                    event_type="communication_error",
                    component="communication_skill",
                    message=f"Invalid communication type: {communication_type}",
                    details=input_data
                )
                return None

            if result:
                # Log the communication generation
                self.logger.log_system_event(
                    event_type="communication_generated",
                    component="communication_skill",
                    message=f"{communication_type.replace('_', ' ').title()} generated successfully",
                    details={
                        "communication_type": communication_type,
                        "context_summary": context[:50] + "..." if len(context) > 50 else context
                    }
                )

                # Log the execution
                self.log_execution(input_data, result)

                return result
            else:
                self.logger.log_system_event(
                    event_type="communication_error",
                    component="communication_skill",
                    message=f"Failed to generate {communication_type}",
                    details={"input_data": input_data}
                )
                return None

        except Exception as e:
            self.logger.log_system_event(
                event_type="communication_error",
                component="communication_skill",
                message=f"Error in communication skill: {e}",
                details={"input_data": input_data}
            )
            return None

    def generate_email(self, context: str, recipient_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate an email based on context and recipient information.

        Args:
            context: Context for generating the email
            recipient_info: Information about the recipient

        Returns:
            Dictionary with email data or None if generation failed
        """
        try:
            # Extract recipient information
            recipient_name = recipient_info.get('name', 'Valued Contact')
            recipient_email = recipient_info.get('email', 'recipient@example.com')
            subject_hint = recipient_info.get('subject_hint', '')

            # Generate email components based on context
            subject = self._generate_email_subject(context, subject_hint)
            body = self._generate_email_body(context, recipient_name)

            # Create a unique ID for the email draft
            email_id = f"email_draft_{uuid.uuid4()}"

            # Create email data structure
            email_data = {
                "id": email_id,
                "type": "email",
                "to": [recipient_email],
                "subject": subject,
                "body": body,
                "timestamp": datetime.now().isoformat(),
                "context_used": context,
                "recipient_info": recipient_info,
                "status": "draft"
            }

            # Optionally add salutation and closing based on context
            if "formal" in context.lower():
                email_data["salutation"] = f"Dear {recipient_name},"
                email_data["closing"] = f"Best regards,\n[Your Name]"
            else:
                email_data["salutation"] = f"Hi {recipient_name},"
                email_data["closing"] = f"Thanks,\n[Your Name]"

            return {
                "communication_type": "email",
                "email_data": email_data,
                "status": "success",
                "message": "Email draft generated successfully"
            }

        except Exception as e:
            self.logger.log_system_event(
                event_type="email_generation_error",
                component="communication_skill",
                message=f"Error generating email: {e}",
                details={"context": context, "recipient_info": recipient_info}
            )
            return None

    def generate_linkedin_post(self, context: str, topic: str) -> Optional[Dict[str, Any]]:
        """
        Generate a LinkedIn post based on context and topic.

        Args:
            context: Context for generating the post
            topic: Topic for the LinkedIn post

        Returns:
            Dictionary with post data or None if generation failed
        """
        try:
            # Generate post content based on context and topic
            post_content = self._generate_linkedin_post_content(context, topic)

            # Generate relevant hashtags
            hashtags = self._generate_hashtags(topic, context)

            # Create a unique ID for the post draft
            post_id = f"post_draft_{uuid.uuid4()}"

            # Determine visibility based on context
            visibility = "PUBLIC" if "public" in context.lower() else "CONNECTIONS_ONLY"

            # Create post data structure
            post_data = {
                "id": post_id,
                "type": "linkedin_post",
                "content": post_content,
                "hashtags": hashtags,
                "visibility": visibility,
                "timestamp": datetime.now().isoformat(),
                "context_used": context,
                "topic": topic,
                "status": "draft"
            }

            # Add any additional media URLs if context suggests them
            if "image" in context.lower() or "visual" in context.lower():
                post_data["media_urls"] = ["placeholder_image_url"]

            return {
                "communication_type": "linkedin_post",
                "post_data": post_data,
                "status": "success",
                "message": "LinkedIn post draft generated successfully"
            }

        except Exception as e:
            self.logger.log_system_event(
                event_type="linkedin_post_generation_error",
                component="communication_skill",
                message=f"Error generating LinkedIn post: {e}",
                details={"context": context, "topic": topic}
            )
            return None

    def _generate_email_subject(self, context: str, hint: str = "") -> str:
        """
        Generate an appropriate email subject based on context.

        Args:
            context: Context for the email
            hint: Subject hint if provided

        Returns:
            Generated email subject
        """
        if hint:
            return hint

        context_lower = context.lower()

        if "meeting" in context_lower or "appointment" in context_lower:
            return "Meeting Request"
        elif "follow up" in context_lower or "follow-up" in context_lower:
            return "Follow Up on Previous Discussion"
        elif "proposal" in context_lower or "offer" in context_lower:
            return "Business Proposal"
        elif "thank you" in context_lower or "thanks" in context_lower:
            return "Thank You for Your Time"
        elif "introduction" in context_lower or "connect" in context_lower:
            return "Introduction and Connection Request"
        else:
            return "Regarding Our Recent Interaction"

    def _generate_email_body(self, context: str, recipient_name: str) -> str:
        """
        Generate an appropriate email body based on context.

        Args:
            context: Context for the email
            recipient_name: Name of the recipient

        Returns:
            Generated email body
        """
        context_lower = context.lower()

        if "meeting" in context_lower or "appointment" in context_lower:
            return f"""
I hope this email finds you well, {recipient_name}.

I am writing to discuss scheduling a meeting to further our recent conversation about {context[:50]}{'...' if len(context) > 50 else ''}.
Could you please let me know your availability for the next week?

I look forward to hearing from you.

Best regards,
[Your Name]
"""
        elif "follow up" in context_lower or "follow-up" in context_lower:
            return f"""
Dear {recipient_name},

Thank you for our discussion regarding {context[:50]}{'...' if len(context) > 50 else ''}. I wanted to follow up on the key points we covered and explore potential next steps.

Would you be available for a brief call next week to continue our conversation?

I appreciate your time and consideration.

Best regards,
[Your Name]
"""
        elif "proposal" in context_lower or "offer" in context_lower:
            return f"""
Dear {recipient_name},

Following our previous communication, I am pleased to submit a proposal regarding {context[:50]}{'...' if len(context) > 50 else ''}.

I believe this opportunity aligns well with your interests and would be mutually beneficial. Please find the details attached.

I would welcome the chance to discuss this further at your convenience.

Warm regards,
[Your Name]
"""
        else:
            return f"""
Dear {recipient_name},

Thank you for reaching out about {context[:50]}{'...' if len(context) > 50 else ''}. I appreciate your interest in this matter.

I would be happy to discuss this further. Please let me know when would be convenient for a call or meeting.

Looking forward to connecting.

Best regards,
[Your Name]
"""

    def _generate_linkedin_post_content(self, context: str, topic: str) -> str:
        """
        Generate LinkedIn post content based on context and topic.

        Args:
            context: Context for the post
            topic: Topic of the post

        Returns:
            Generated LinkedIn post content
        """
        if topic:
            combined_context = f"{topic}: {context}"
        else:
            combined_context = context

        context_lower = combined_context.lower()

        if "thought leadership" in context_lower or "leadership" in context_lower:
            return f"""
Exciting developments in {topic or 'my field'}!

After reflecting on recent trends, I believe that {combined_context[:100]}{'...' if len(combined_context) > 100 else ''}.

What are your thoughts? I'd love to hear from fellow professionals in the industry.
"""
        elif "achievement" in context_lower or "milestone" in context_lower:
            return f"""
Thrilled to share an important milestone!

{combined_context[:150]}{'...' if len(combined_context) > 150 else ''}.

Grateful for the support of my network and team. This achievement wouldn't have been possible without collaboration and dedication.

#Achievement #Milestone #{topic.replace(' ', '') if topic else 'ProfessionalGrowth'}
"""
        elif "insight" in context_lower or "learning" in context_lower:
            return f"""
Just had a fascinating insight about {topic or 'recent developments'}:

{combined_context[:120]}{'...' if len(combined_context) > 120 else ''}.

Continuous learning is key to staying ahead in our field. What insights have you gained recently?
"""
        else:
            return f"""
Interesting times in {topic or 'our industry'}!

{combined_context[:150]}{'...' if len(combined_context) > 150 else ''}.

Engaging with professionals like yourselves helps broaden perspectives. Looking forward to continued discussions on this topic.
"""

    def _generate_hashtags(self, topic: str, context: str) -> list:
        """
        Generate relevant hashtags for a LinkedIn post.

        Args:
            topic: Topic of the post
            context: Context for the post

        Returns:
            List of relevant hashtags
        """
        hashtags = []

        # Add topic-based hashtags
        if topic:
            clean_topic = topic.replace(' ', '').replace('-', '').replace('_', '')
            if clean_topic:
                hashtags.append(clean_topic)

        # Add context-based hashtags
        context_lower = context.lower()

        if "business" in context_lower or "professional" in context_lower:
            hashtags.extend(["Business", "ProfessionalDevelopment", "Leadership"])
        if "technology" in context_lower or "tech" in context_lower:
            hashtags.extend(["Technology", "Innovation", "Tech"])
        if "startup" in context_lower or "entrepreneur" in context_lower:
            hashtags.extend(["Startup", "Entrepreneurship", "Innovation"])
        if "marketing" in context_lower:
            hashtags.extend(["Marketing", "DigitalMarketing", "Branding"])
        if "networking" in context_lower:
            hashtags.extend(["Networking", "Connections", "RelationshipBuilding"])

        # Add some general professional hashtags
        hashtags.extend(["Professional", "Insights", "Growth"])

        # Remove duplicates and return first 5
        unique_hashtags = list(dict.fromkeys(hashtags))[:5]

        # Prefix with '#' and return
        return [f"#{tag}" for tag in unique_hashtags]

    def validate_communication_context(self, context: str, comm_type: str) -> bool:
        """
        Validate that the communication context is appropriate.

        Args:
            context: The context to validate
            comm_type: Type of communication ('email' or 'linkedin_post')

        Returns:
            True if context is valid, False otherwise
        """
        if not context or not isinstance(context, str):
            return False

        # Check for inappropriate content
        inappropriate_terms = [
            'spam', 'scam', 'click here', 'buy now', '$$$',
            'free money', 'get rich quick', 'investment opportunity'
        ]

        context_lower = context.lower()
        for term in inappropriate_terms:
            if term in context_lower:
                if self.logger:
                    self.logger.log_system_event(
                        event_type="content_validation_error",
                        component="communication_skill",
                        message=f"Inappropriate content detected in {comm_type}: {term}",
                        details={"context_preview": context[:50]}
                    )
                return False

        return True

    def ensure_brand_voice(self, content: str, brand_guidelines: Optional[Dict[str, Any]] = None) -> str:
        """
        Ensure the content maintains the appropriate brand voice.

        Args:
            content: The content to adjust
            brand_guidelines: Brand guidelines to follow (optional)

        Returns:
            Content adjusted to match brand voice
        """
        # If no specific brand guidelines provided, return content as is
        if not brand_guidelines:
            return content

        # Apply brand tone adjustments based on guidelines
        tone = brand_guidelines.get('tone', 'professional').lower()

        if tone == 'professional':
            # Ensure formal language
            content = content.replace("Hi ", "Dear ").replace("Thanks,", "Sincerely,").replace("Thanks!", "Thank you.")
        elif tone == 'friendly':
            # Make language more approachable
            content = content.replace("Dear ", "Hi ").replace("Sincerely,", "Best,").replace("Thank you.", "Thanks!")
        elif tone == 'innovative':
            # Add dynamic language
            content = content.replace(".", ". Exciting possibilities! ")

        return content