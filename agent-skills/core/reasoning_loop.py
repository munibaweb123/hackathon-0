"""
Reasoning Loop Orchestrator

Connects the Perception → Reasoning → Action pipeline.
Reads events from the inbox, runs them through Claude reasoning,
generates Plan.md files, and creates approval requests for sensitive actions.

Tasks T052, T053, T056: Reasoning loop orchestrator + event grouping + inbox connection
"""

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.vault_interface import VaultInterface
from core.logger import Logger
from core.approval_generator import ApprovalGenerator


class ReasoningLoop:
    """
    Orchestrates the Perception → Reasoning → Action pipeline.
    Reads inbox events, generates plans via Claude, and creates approval requests.
    """

    def __init__(
        self,
        vault_interface: VaultInterface,
        logger: Logger,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        dry_run: bool = False,
    ):
        self.vault = vault_interface
        self.logger = logger
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.dry_run = dry_run
        self.approval_generator = ApprovalGenerator(vault_interface, logger)
        self._client = None

    def _get_client(self):
        """Lazy-initialize AI client — Gemini preferred, Anthropic fallback."""
        if self._client is None:
            # Try Gemini first (free tier)
            if self.gemini_key and self.gemini_key != "your_gemini_api_key_here":
                try:
                    from google import genai
                    self._client = genai.Client(api_key=self.gemini_key)
                    self._client_type = "gemini"
                    return self._client
                except Exception:
                    pass
            # Fallback to Anthropic
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
                self._client_type = "anthropic"
            except ImportError:
                self.logger.log_system_event(
                    event_type="reasoning_error",
                    component="reasoning_loop",
                    message="No AI client available (install google-generativeai or anthropic)",
                )
                return None
            except Exception as e:
                self.logger.log_system_event(
                    event_type="reasoning_error",
                    component="reasoning_loop",
                    message=f"Failed to initialize AI client: {e}",
                )
                return None
        return self._client

    def _call_ai(self, prompt: str) -> str:
        """Call AI with prompt, returning response text."""
        client = self._get_client()
        if client is None:
            return ""
        if getattr(self, "_client_type", "anthropic") == "gemini":
            response = client.models.generate_content(
                model="models/gemini-flash-latest", contents=prompt
            )
            return response.text.strip()
        else:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()

    def get_unprocessed_events(self) -> List[Dict[str, Any]]:
        """Get all unprocessed events from the inbox."""
        events = []
        for file_path in self.vault.get_files_in_folder("inbox"):
            try:
                data = self.vault.read_event_file(file_path)
                metadata = data.get("metadata", {})

                if metadata.get("processing_status") == "new":
                    events.append({
                        "file_path": str(file_path),
                        "metadata": metadata,
                        "content": data.get("content", ""),
                    })
            except Exception:
                pass

        return events

    def group_related_events(self, events: List[Dict]) -> List[List[Dict]]:
        """
        Group related events together (e.g., same thread, same sender).

        Args:
            events: List of event dicts

        Returns:
            List of event groups (each group is a list of related events)
        """
        groups = {}

        for event in events:
            metadata = event.get("metadata", {})
            raw_data = metadata.get("raw_data", {})
            normalized = metadata.get("normalized_data", {})

            # Group by thread_id if available
            thread_id = raw_data.get("thread_id") or normalized.get("metadata", {}).get("thread_id")
            if thread_id:
                key = f"thread:{thread_id}"
            else:
                # Group by source + sender
                source = metadata.get("source_type", "unknown")
                sender = raw_data.get("sender", normalized.get("sender", {}).get("name", "unknown"))
                key = f"{source}:{sender}"

            if key not in groups:
                groups[key] = []
            groups[key].append(event)

        return list(groups.values())

    def generate_plan(self, event_group: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        Generate a Plan.md for an event group using Claude reasoning.

        Args:
            event_group: List of related events to reason about

        Returns:
            Plan data dict or None
        """
        client = self._get_client()

        # Build context from events
        event_summaries = []
        for event in event_group:
            metadata = event.get("metadata", {})
            normalized = metadata.get("normalized_data", {})
            summary = normalized.get("summary", "")
            source = metadata.get("source_type", "unknown")
            priority = metadata.get("priority", "medium")
            event_summaries.append(
                f"- [{source.upper()}] (Priority: {priority}) {summary}"
            )

        # Add cross-domain contact context (T082)
        for event in event_group:
            contact_ctx = self._get_contact_context(event)
            if contact_ctx:
                event_summaries.append(contact_ctx)

        events_context = "\n".join(event_summaries)

        prompt = f"""You are an AI Employee assistant analyzing incoming events.
Based on the following events, generate a structured plan with recommended actions.

## Events
{events_context}

## Instructions
1. Analyze the events and determine what actions are needed
2. For each action, indicate if it requires human approval
3. Actions that send external communications ALWAYS require approval
4. Classify risk as low/medium/high

Respond with JSON in this format:
{{
  "title": "Brief plan title",
  "context": "Analysis of what happened",
  "analysis": "Why these actions are recommended",
  "actions": [
    {{
      "action_type": "email_reply|linkedin_post|whatsapp_reply|escalate|archive",
      "description": "What to do",
      "risk_level": "low|medium|high",
      "requires_approval": true,
      "proposed_content": "Draft content if applicable"
    }}
  ],
  "expected_outcome": "What should happen after execution"
}}"""

        if self.dry_run or not client:
            # Generate a mock plan in dry_run or no-client mode
            return self._generate_mock_plan(event_group)

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse Claude's response
            response_text = response.content[0].text

            # Extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                plan_data = json.loads(response_text[json_start:json_end])
                return plan_data

            return None

        except Exception as e:
            self.logger.log_system_event(
                event_type="reasoning_error",
                component="reasoning_loop",
                message=f"Claude reasoning failed: {e}",
            )
            return self._generate_mock_plan(event_group)

    def _generate_mock_plan(self, event_group: List[Dict]) -> Dict[str, Any]:
        """Generate a basic plan without Claude (fallback)."""
        source = event_group[0].get("metadata", {}).get("source_type", "unknown")
        return {
            "title": f"Process {source} event(s)",
            "context": f"Received {len(event_group)} {source} event(s) requiring attention",
            "analysis": "Events detected by watcher and need human review",
            "actions": [
                {
                    "action_type": "escalate",
                    "description": f"Review {source} event(s) and determine appropriate response",
                    "risk_level": "low",
                    "requires_approval": False,
                }
            ],
            "expected_outcome": "Events reviewed and appropriate action taken",
        }

    def write_plan(self, plan_data: Dict[str, Any], source_events: List[str]) -> str:
        """
        Write a Plan.md file to the plans folder.

        Returns:
            Path to the created plan file
        """
        import uuid

        plan_id = str(uuid.uuid4())
        now = datetime.utcnow()
        filename = f"PLAN_{now.strftime('%Y-%m-%d_%H%M%S')}_{plan_id[:8]}.md"

        metadata = {
            "id": plan_id,
            "title": plan_data.get("title", "Untitled Plan"),
            "created_at": now.isoformat() + "Z",
            "source_events": source_events,
            "status": "draft",
            "risk_level": self._overall_risk(plan_data.get("actions", [])),
        }

        # Build markdown content
        actions_md = []
        for i, action in enumerate(plan_data.get("actions", [])):
            approval_mark = " [REQUIRES APPROVAL]" if action.get("requires_approval") else ""
            actions_md.append(
                f"- [ ] **{action.get('action_type', 'unknown')}**: "
                f"{action.get('description', '')}{approval_mark} "
                f"(Risk: {action.get('risk_level', 'medium')})"
            )

        content = f"""# {plan_data.get('title', 'Plan')}

## Context
{plan_data.get('context', '')}

## Analysis
{plan_data.get('analysis', '')}

## Recommended Actions
{chr(10).join(actions_md)}

## Expected Outcome
{plan_data.get('expected_outcome', '')}
"""

        file_path = self.vault.write_event_file(
            filename=filename,
            metadata=metadata,
            content=content,
            destination_folder="plans",
        )

        self.logger.log_system_event(
            event_type="plan_created",
            component="reasoning_loop",
            message=f"Plan created: {plan_data.get('title')}",
            details={"plan_id": plan_id, "file_path": str(file_path)},
        )

        return plan_id

    def create_approvals_for_plan(self, plan_id: str, plan_data: Dict[str, Any]):
        """Create approval requests for actions that require approval."""
        for action in plan_data.get("actions", []):
            if action.get("requires_approval"):
                self.approval_generator.create_approval_request(
                    action_type=action.get("action_type", "unknown"),
                    description=action.get("description", ""),
                    context=plan_data.get("context", ""),
                    plan_id=plan_id,
                    proposed_content=action.get("proposed_content", ""),
                    risk_level=action.get("risk_level", "medium"),
                )

    def _get_contact_context(self, event: Dict) -> str:
        """
        Fetch cross-domain context for an event's sender.

        Per T082: Looks up the sender across all platforms via ContactMatcher.
        """
        try:
            from core.contact_matcher import ContactMatcher
            matcher = ContactMatcher()

            metadata = event.get("metadata", {})
            raw_data = metadata.get("raw_data", {})
            normalized = metadata.get("normalized_data", {})

            sender_email = (
                raw_data.get("sender_email")
                or normalized.get("sender", {}).get("email")
            )
            if sender_email:
                context = matcher.get_contact_context(sender_email)
                if context:
                    return f"\n[CROSS-DOMAIN CONTEXT] {context}"

            sender_name = (
                raw_data.get("sender")
                or normalized.get("sender", {}).get("name")
            )
            if sender_name:
                contact = matcher.find_by_name(sender_name)
                if contact:
                    return (
                        f"\n[CROSS-DOMAIN CONTEXT] Contact: {contact.get('display_name', sender_name)}, "
                        f"Company: {contact.get('company', 'N/A')}"
                    )
        except (ImportError, Exception):
            pass

        return ""

    def process_inbox(self) -> Dict[str, Any]:
        """
        Main loop iteration: process all unprocessed inbox events.

        Returns:
            Summary of processing results
        """
        events = self.get_unprocessed_events()
        if not events:
            return {"processed": 0, "plans": 0, "approvals": 0}

        groups = self.group_related_events(events)
        plans_created = 0
        approvals_created = 0

        for group in groups:
            # Generate plan for this event group
            plan_data = self.generate_plan(group)
            if not plan_data:
                continue

            # Write the plan
            source_event_paths = [e["file_path"] for e in group]
            plan_id = self.write_plan(plan_data, source_event_paths)
            plans_created += 1

            # Create approval requests for sensitive actions
            self.create_approvals_for_plan(plan_id, plan_data)
            approvals_created += sum(
                1 for a in plan_data.get("actions", []) if a.get("requires_approval")
            )

            # Mark events as processed
            for event in group:
                try:
                    self.vault.move_file(event["file_path"], "processing")
                except Exception:
                    pass

        result = {
            "processed": len(events),
            "plans": plans_created,
            "approvals": approvals_created,
        }

        self.logger.log_system_event(
            event_type="reasoning_cycle_complete",
            component="reasoning_loop",
            message=f"Processed {len(events)} events into {plans_created} plans",
            details=result,
        )

        return result

    def _overall_risk(self, actions: List[Dict]) -> str:
        """Calculate overall risk from actions."""
        risks = [a.get("risk_level", "low") for a in actions]
        if "high" in risks:
            return "high"
        if "medium" in risks:
            return "medium"
        return "low"
