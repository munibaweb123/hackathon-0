"""
Planning Skill Module

This module converts reasoning output into executable steps and annotates them as safe or sensitive.
It implements deterministic behavior to ensure same inputs yield identical plans.
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from core.base_skill import BaseSkill
from core.vault_interface import VaultInterface
from core.logger import Logger
from models.plan_md import PlanMd


class PlanningSkill(BaseSkill):
    """
    Converts reasoning output into executable steps and annotates them as safe or sensitive.
    Implements deterministic behavior to ensure same inputs yield identical plans.
    """

    def __init__(self, vault_interface: VaultInterface, logger: Logger):
        """
        Initialize the planning skill.

        Args:
            vault_interface: Interface for vault operations
            logger: Logger instance for auditability
        """
        super().__init__("planning", vault_interface, logger)

    def execute(self, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute the planning skill with the given input data.

        Args:
            input_data: Input data for the skill, expected to contain:
                - 'reasoning_output': The reasoning output to convert to steps
                - 'context': Additional context for planning

        Returns:
            Output data from the skill execution or None if failed
        """
        if not self.validate_input(input_data):
            return None

        try:
            # Get the reasoning output
            reasoning_output = input_data.get('reasoning_output')
            if not reasoning_output:
                self.logger.log_system_event(
                    event_type="planning_error",
                    component="planning_skill",
                    message="Missing reasoning_output in input",
                    details=input_data
                )
                return None

            # Create a plan from the reasoning output
            plan = self.convert_to_plan(reasoning_output, input_data.get('context', ''))

            if not plan:
                self.logger.log_system_event(
                    event_type="planning_error",
                    component="planning_skill",
                    message="Failed to convert reasoning output to plan",
                    details={"reasoning_output": reasoning_output}
                )
                return None

            # Validate the plan
            if not plan.validate():
                self.logger.log_system_event(
                    event_type="planning_error",
                    component="planning_skill",
                    message="Generated plan is invalid",
                    details={"plan_id": plan.id}
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
                "status": "success",
                "required_approvals": plan.required_approvals
            }

        except Exception as e:
            self.logger.log_system_event(
                event_type="planning_error",
                component="planning_skill",
                message=f"Error in planning skill execution: {e}",
                details={"input_data": input_data}
            )
            return None

    def convert_to_plan(self, reasoning_output: Dict[str, Any], context: str = "") -> Optional[PlanMd]:
        """
        Convert reasoning output into an executable plan with annotated steps.

        Args:
            reasoning_output: The reasoning output to convert
            context: Additional context for planning

        Returns:
            PlanMd object or None if conversion failed
        """
        try:
            # Generate a deterministic ID based on the input to ensure same inputs
            # yield the same plan (deterministic behavior)
            input_for_id = f"{json.dumps(reasoning_output, sort_keys=True)}_{context}"
            plan_id = hashlib.sha256(input_for_id.encode()).hexdigest()[:12]

            # Extract objective from reasoning output
            objective = reasoning_output.get('objective', 'Default objective')

            # Extract actions from reasoning output
            raw_actions = reasoning_output.get('actions', [])

            # Process actions and annotate for approval
            processed_actions = []
            required_approvals = []

            for i, action in enumerate(raw_actions):
                # Ensure the action is a dictionary
                if not isinstance(action, dict):
                    action = {'description': str(action)}

                # Add an ID to the action
                action_id = f"action_{i}_{plan_id[:8]}"
                action['id'] = action_id

                # Add to processed actions
                processed_actions.append(action)

                # Determine if action requires approval
                if self.annotates_as_sensitive(action):
                    required_approvals.append(action_id)

            # Extract expected outcome
            expected_outcome = reasoning_output.get('expected_outcome', 'Default expected outcome')

            # Create the plan
            plan = PlanMd(
                id=plan_id,
                objective=objective,
                actions=processed_actions,
                required_approvals=required_approvals,
                expected_outcome=expected_outcome,
                generated_at=datetime.now().isoformat()
            )

            return plan

        except Exception as e:
            self.logger.log_system_event(
                event_type="plan_conversion_error",
                component="planning_skill",
                message=f"Error converting reasoning output to plan: {e}",
                details={
                    "reasoning_output": reasoning_output,
                    "context": context
                }
            )
            return None

    def annotates_as_sensitive(self, action: Dict[str, Any]) -> bool:
        """
        Determine if an action is sensitive and requires approval.

        Args:
            action: The action to evaluate

        Returns:
            True if the action is sensitive, False otherwise
        """
        # Actions that are typically sensitive and require approval
        sensitive_keywords = [
            'send', 'post', 'publish', 'approve', 'authorize', 'execute',
            'delete', 'remove', 'pay', 'transfer', 'share', 'connect',
            'message', 'contact', 'engage', 'reply', 'respond'
        ]

        # Types of sensitive actions
        sensitive_types = [
            'email_send', 'linkedin_post', 'payment_execute', 'data_delete',
            'social_media_post', 'message_send', 'connection_request',
            'approval_needed', 'external_action', 'user_notification'
        ]

        # Check if action type is sensitive
        action_type = action.get('type', '').lower()
        if action_type in sensitive_types:
            return True

        # Check if action description contains sensitive keywords
        description = action.get('description', '').lower()
        for keyword in sensitive_keywords:
            if keyword in description:
                return True

        # Check if action has any fields indicating it affects external systems
        external_indicators = ['recipient', 'destination', 'target', 'external']
        for indicator in external_indicators:
            if indicator in action:
                return True

        return False

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
                markdown_content += "- **SENSITIVE ACTION - APPROVAL REQUIRED**: This action requires human approval before execution\n"
            else:
                markdown_content += "- **SAFE ACTION**: This action can be executed without additional approval\n"

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

    def validate_plan_consistency(self, plan1: PlanMd, plan2: PlanMd) -> bool:
        """
        Validate that two plans are consistent (for deterministic behavior testing).

        Args:
            plan1: First plan to compare
            plan2: Second plan to compare

        Returns:
            True if plans are consistent, False otherwise
        """
        # Compare all relevant fields to ensure deterministic behavior
        return (
            plan1.objective == plan2.objective and
            plan1.actions == plan2.actions and
            plan1.required_approvals == plan2.required_approvals and
            plan1.expected_outcome == plan2.expected_outcome
        )

    def refine_plan_annotations(self, plan: PlanMd) -> PlanMd:
        """
        Refine the plan annotations to ensure all sensitive actions are properly marked.

        Args:
            plan: The plan to refine

        Returns:
            Refined PlanMd object
        """
        refined_actions = []
        refined_required_approvals = []

        for action in plan.actions:
            action_id = action.get('id')

            # Check if the action is sensitive using our annotation method
            if self.annotates_as_sensitive(action):
                if action_id not in refined_required_approvals:
                    refined_required_approvals.append(action_id)
            else:
                # Remove from required approvals if it was mistakenly added
                if action_id in refined_required_approvals:
                    refined_required_approvals.remove(action_id)

            refined_actions.append(action)

        # Update the plan with refined annotations
        plan.actions = refined_actions
        plan.required_approvals = refined_required_approvals

        return plan