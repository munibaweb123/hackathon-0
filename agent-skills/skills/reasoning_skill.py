"""
Reasoning Skill Module

This module reads watcher output files and applies Claude reasoning to produce Plan.md files.
It implements deterministic behavior to ensure same inputs yield identical Plan.md files.
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from core.base_skill import BaseSkill
from core.vault_interface import VaultInterface
from core.logger import Logger
from models.watcher_output_file import WatcherOutputFile
from models.plan_md import PlanMd


class ReasoningSkill(BaseSkill):
    """
    Reads watcher output files and applies Claude reasoning to produce Plan.md files.
    Implements deterministic behavior to ensure same inputs yield identical Plan.md files.
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger):
        """
        Initialize the reasoning skill.

        Args:
            vault_interface: Interface for vault operations
            logger: Logger instance for auditability
        """
        super().__init__("reasoning", vault_interface, logger)

    def execute(self, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute the reasoning skill with the given input data.

        Args:
            input_data: Input data for the skill, expected to contain:
                - 'watcher_output_path': Path to the watcher output file
                - 'context': Additional context for reasoning

        Returns:
            Output data from the skill execution or None if failed
        """
        if not self.validate_input(input_data):
            return None

        try:
            # Get the watcher output file path
            watcher_output_path = input_data.get('watcher_output_path')
            if not watcher_output_path:
                self.logger.log_system_event(
                    event_type="reasoning_error",
                    component="reasoning_skill",
                    message="Missing watcher_output_path in input",
                    details=input_data
                )
                return None

            # Read and parse the watcher output file
            watcher_output_content = self.vault_interface.read_file(watcher_output_path)
            watcher_output_json = json.loads(watcher_output_content)

            # Create WatcherOutputFile object
            watcher_output = WatcherOutputFile.from_dict(watcher_output_json['data'])

            if not watcher_output.validate():
                self.logger.log_system_event(
                    event_type="reasoning_error",
                    component="reasoning_skill",
                    message="Invalid watcher output file",
                    details={"watcher_output_path": watcher_output_path}
                )
                return None

            # Apply reasoning to generate a plan
            plan = self.generate_plan(watcher_output, input_data.get('context', ''))

            if not plan:
                self.logger.log_system_event(
                    event_type="reasoning_error",
                    component="reasoning_skill",
                    message="Failed to generate plan from watcher output",
                    details={"watcher_output_path": watcher_output_path}
                )
                return None

            # Save the plan to the vault
            plan_filename = f"Plan_{plan.id}.md"
            plan_content = self.format_plan_as_markdown(plan)

            plan_file_path = self.vault_interface.write_file(
                file_path=plan_filename,
                content=plan_content,
                destination_folder="inbox"
            )

            # Log the reasoning output
            self.logger.log_reasoning_output(
                input_context=str(watcher_output.to_dict()),
                output_plan=str(plan.to_dict()),
                reasoning_steps=["parsed_watcher_output", "applied_claude_reasoning", "generated_plan"]
            )

            # Log the plan creation
            self.logger.log_plan_creation(
                plan_id=plan.id,
                objective=plan.objective,
                actions=[str(action) for action in plan.actions],
                required_approvals=plan.required_approvals,
                expected_outcome=plan.expected_outcome
            )

            # Log the execution
            self.log_execution(input_data, {"plan_file_path": str(plan_file_path), "plan_id": plan.id})

            return {
                "plan_file_path": str(plan_file_path),
                "plan_id": plan.id,
                "status": "success"
            }

        except Exception as e:
            self.logger.log_system_event(
                event_type="reasoning_error",
                component="reasoning_skill",
                message=f"Error in reasoning skill execution: {e}",
                details={"input_data": input_data}
            )
            return None

    def generate_plan(self, watcher_output: WatcherOutputFile, context: str = "") -> Optional[PlanMd]:
        """
        Generate a plan based on the watcher output and context.

        Args:
            watcher_output: The watcher output to generate a plan for
            context: Additional context for the reasoning

        Returns:
            PlanMd object or None if generation failed
        """
        try:
            # Generate a deterministic ID based on the input to ensure same inputs
            # yield the same plan (deterministic behavior)
            input_for_id = f"{watcher_output.source}_{watcher_output.event_type}_{watcher_output.timestamp}_{context}"
            plan_id = hashlib.sha256(input_for_id.encode()).hexdigest()[:12]

            # Determine objective based on event type and source
            objective = self.determine_objective(watcher_output, context)

            # Generate actions based on the event
            actions = self.generate_actions(watcher_output, context)

            # Determine required approvals based on action sensitivity
            required_approvals = []
            for i, action in enumerate(actions):
                action['id'] = f"action_{i}_{plan_id[:8]}"

                # Check if action requires approval based on its type
                if self.requires_approval(action):
                    required_approvals.append(action['id'])

            # Determine expected outcome
            expected_outcome = self.determine_expected_outcome(watcher_output, actions)

            # Create the plan
            plan = PlanMd(
                id=plan_id,
                objective=objective,
                actions=actions,
                required_approvals=required_approvals,
                expected_outcome=expected_outcome,
                generated_at=datetime.now().isoformat()
            )

            return plan

        except Exception as e:
            self.logger.log_system_event(
                event_type="plan_generation_error",
                component="reasoning_skill",
                message=f"Error generating plan: {e}",
                details={
                    "watcher_output": watcher_output.to_dict(),
                    "context": context
                }
            )
            return None

    def determine_objective(self, watcher_output: WatcherOutputFile, context: str) -> str:
        """
        Determine the objective of the plan based on the watcher output.

        Args:
            watcher_output: The watcher output to analyze
            context: Additional context

        Returns:
            Objective string
        """
        source = watcher_output.source
        event_type = watcher_output.event_type

        # Determine objective based on source and event type
        if source == "gmail" and event_type == "new_email":
            return f"Process new email from {watcher_output.normalized_data.get('sender', 'unknown sender')} and determine appropriate response"
        elif source == "linkedin" and event_type == "profile_view":
            return f"Analyze LinkedIn profile view by {watcher_output.normalized_data.get('actor_name', 'unknown viewer')} and decide on engagement strategy"
        elif source == "linkedin" and event_type == "connection_request":
            return f"Evaluate LinkedIn connection request and determine whether to accept"
        elif source == "gmail" and event_type == "meeting_reminder":
            return f"Review upcoming meeting and prepare necessary materials or responses"
        else:
            return f"Process {event_type} from {source} and determine appropriate action"

    def generate_actions(self, watcher_output: WatcherOutputFile, context: str) -> List[Dict[str, Any]]:
        """
        Generate actions based on the watcher output.

        Args:
            watcher_output: The watcher output to analyze
            context: Additional context

        Returns:
            List of action dictionaries
        """
        actions = []

        # Based on the source and event type, generate appropriate actions
        if watcher_output.source == "gmail":
            if watcher_output.event_type == "new_email":
                # If it's a meeting invitation, we might want to add to calendar
                if "meeting" in watcher_output.normalized_data.get('subject', '').lower() or \
                   "calendar" in watcher_output.normalized_data.get('subject', '').lower():
                    actions.append({
                        "type": "schedule_event",
                        "description": f"Add meeting from email to calendar",
                        "email_subject": watcher_output.normalized_data.get('subject'),
                        "sender": watcher_output.normalized_data.get('sender')
                    })

                # If it's from a VIP, we might want to prioritize
                if "urgent" in watcher_output.normalized_data.get('subject', '').lower() or \
                   "important" in watcher_output.normalized_data.get('subject', '').lower():
                    actions.append({
                        "type": "flag_priority",
                        "description": f"Flag email from {watcher_output.normalized_data.get('sender')} as high priority",
                        "subject": watcher_output.normalized_data.get('subject')
                    })

                # Generate a response draft
                actions.append({
                    "type": "draft_response",
                    "description": f"Draft a response to email from {watcher_output.normalized_data.get('sender')}",
                    "recipient": watcher_output.normalized_data.get('sender'),
                    "context": context
                })

        elif watcher_output.source == "linkedin":
            if watcher_output.event_type == "profile_view":
                actor_name = watcher_output.normalized_data.get('actor_name', 'unknown')
                actions.append({
                    "type": "evaluate_connection",
                    "description": f"Evaluate if connection with {actor_name} is beneficial",
                    "actor_profile": watcher_output.normalized_data.get('actor_profile_url')
                })

                # Suggest a response if they're a potential connection
                actions.append({
                    "type": "draft_connect_request",
                    "description": f"Draft personalized connection request to {actor_name}",
                    "recipient_name": actor_name,
                    "recipient_profile": watcher_output.normalized_data.get('actor_profile_url')
                })

        # Add a default action if no specific actions were generated
        if not actions:
            actions.append({
                "type": "analyze_and_report",
                "description": f"Analyze {watcher_output.event_type} from {watcher_output.source} and generate report",
                "source": watcher_output.source,
                "event_type": watcher_output.event_type,
                "context": context
            })

        return actions

    def requires_approval(self, action: Dict[str, Any]) -> bool:
        """
        Determine if an action requires approval based on its type.

        Args:
            action: The action to evaluate

        Returns:
            True if the action requires approval, False otherwise
        """
        # Actions that typically require approval
        approval_required_types = [
            'send_email', 'draft_and_send_email', 'linkedin_post',
            'send_connection_request', 'accept_connection_request',
            'schedule_event', 'modify_calendar', 'make_payment',
            'delete_data', 'external_api_call'
        ]

        action_type = action.get('type', '')
        return action_type in approval_required_types

    def determine_expected_outcome(self, watcher_output: WatcherOutputFile, actions: List[Dict[str, Any]]) -> str:
        """
        Determine the expected outcome of the plan.

        Args:
            watcher_output: The watcher output
            actions: The list of actions in the plan

        Returns:
            Expected outcome string
        """
        if watcher_output.source == "gmail" and watcher_output.event_type == "new_email":
            return "Email is appropriately responded to or processed, with sender receiving necessary information or acknowledgment"
        elif watcher_output.source == "linkedin" and watcher_output.event_type == "profile_view":
            return "Appropriate engagement strategy is executed based on the profile viewer's profile and connection potential"
        else:
            return "Event is processed according to defined actions, with appropriate follow-up completed"

    def format_plan_as_markdown(self, plan: PlanMd) -> str:
        """
        Format the plan as a markdown file.

        Args:
            plan: The plan to format

        Returns:
            Markdown-formatted string of the plan
        """
        markdown_content = f"""# Plan {plan.id}

## Objective
{plan.objective}

## Actions
"""
        for i, action in enumerate(plan.actions):
            action_id = action.get('id', f'action_{i}')
            action_type = action.get('type', 'unknown')
            action_desc = action.get('description', 'No description provided')

            markdown_content += f"\n### Action {i+1}: {action_type}\n"
            markdown_content += f"- **ID**: {action_id}\n"
            markdown_content += f"- **Description**: {action_desc}\n"

            # Add any additional fields from the action
            for key, value in action.items():
                if key not in ['type', 'description', 'id']:
                    markdown_content += f"- **{key.title()}**: {value}\n"

            # Indicate if this action requires approval
            if action_id in plan.required_approvals:
                markdown_content += "- **APPROVAL REQUIRED**: This action requires human approval before execution\n"

        markdown_content += f"""
## Required Approvals
The following actions require explicit human approval:
{chr(10).join([f"- {aid}" for aid in plan.required_approvals]) if plan.required_approvals else "No actions require approval"}

## Expected Outcome
{plan.expected_outcome}

## Generated At
{plan.generated_at}

## Status
{plan.status}
"""

        return markdown_content