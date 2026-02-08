"""
Instagram Skill

Extends BaseSkill for Instagram-specific operations:
post creation, message replies, and engagement tracking.
"""

import os
import time
from collections import deque
from typing import Any, Dict

from core.base_skill import BaseSkill, SkillResult

try:
    import httpx
except ImportError:
    httpx = None


class InstagramSkill(BaseSkill):
    """Instagram operations via Social MCP server."""

    def __init__(self, vault_interface=None, logger=None):
        super().__init__(name="Instagram", vault_interface=vault_interface, logger=logger)
        self._social_mcp_url = os.environ.get("SOCIAL_MCP_URL", "http://localhost:8002")
        self._calls = deque()
        self._max_calls = 200
        self._period = 3600

    @property
    def id(self) -> str:
        return "instagram"

    @property
    def description(self) -> str:
        return "Instagram account management: posts, messages, and engagement tracking"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["get_messages", "get_posts", "create_post", "reply_message", "get_insights"],
                },
            },
            "required": ["operation"],
        }

    def _check_rate_limit(self) -> bool:
        now = time.time()
        while self._calls and self._calls[0] < now - self._period:
            self._calls.popleft()
        return len(self._calls) < self._max_calls

    def _record_call(self):
        self._calls.append(time.time())

    async def execute_async(self, input_data: Dict[str, Any]) -> SkillResult:
        operation = input_data.get("operation", "")

        if not self._check_rate_limit():
            return SkillResult(success=False, error="Meta rate limit reached (200/hour)")

        self._record_call()

        try:
            if operation == "get_messages":
                return await self._get_messages(input_data)
            elif operation == "get_posts":
                return await self._get_posts(input_data)
            elif operation == "create_post":
                return await self._create_post(input_data)
            elif operation == "reply_message":
                return await self._reply_message(input_data)
            elif operation == "get_insights":
                return await self._get_insights(input_data)
            else:
                return SkillResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _get_messages(self, input_data: Dict[str, Any]) -> SkillResult:
        if not httpx:
            return self._mock_messages()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {"platform": "instagram"}
                if input_data.get("since"):
                    params["since"] = input_data["since"]
                resp = await client.get(f"{self._social_mcp_url}/meta/messages", params=params)
                if resp.status_code == 200:
                    return SkillResult(success=True, data={"messages": resp.json()})
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception:
            return self._mock_messages()

    async def _get_posts(self, input_data: Dict[str, Any]) -> SkillResult:
        if not httpx:
            return self._mock_posts()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self._social_mcp_url}/meta/posts", params={"platform": "instagram"})
                if resp.status_code == 200:
                    return SkillResult(success=True, data={"posts": resp.json()})
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception:
            return self._mock_posts()

    async def _create_post(self, input_data: Dict[str, Any]) -> SkillResult:
        approval_ref = input_data.get("approval_ref")
        content = input_data.get("content", "")
        if not approval_ref:
            return SkillResult(success=False, error="approval_ref required for post creation")

        if not httpx:
            return SkillResult(success=True, data={"mock": True, "message": "[MOCK] IG post would be created"})
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._social_mcp_url}/meta/posts/create",
                    json={"approvalRef": approval_ref, "content": content, "platforms": ["instagram"]},
                )
                if resp.status_code == 200:
                    return SkillResult(success=True, data=resp.json())
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _reply_message(self, input_data: Dict[str, Any]) -> SkillResult:
        approval_ref = input_data.get("approval_ref")
        if not approval_ref:
            return SkillResult(success=False, error="approval_ref required")

        if not httpx:
            return SkillResult(success=True, data={"mock": True, "message": "[MOCK] IG reply would be sent"})
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._social_mcp_url}/meta/messages/reply",
                    json={
                        "approvalRef": approval_ref,
                        "messageId": input_data.get("message_id", ""),
                        "content": input_data.get("content", ""),
                    },
                )
                if resp.status_code == 200:
                    return SkillResult(success=True, data=resp.json())
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _get_insights(self, input_data: Dict[str, Any]) -> SkillResult:
        if not httpx:
            return self._mock_insights()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {}
                if input_data.get("period_start"):
                    params["periodStart"] = input_data["period_start"]
                if input_data.get("period_end"):
                    params["periodEnd"] = input_data["period_end"]
                resp = await client.get(f"{self._social_mcp_url}/meta/insights", params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    return SkillResult(success=True, data=data.get("instagram", data))
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception:
            return self._mock_insights()

    def _mock_messages(self) -> SkillResult:
        return SkillResult(success=True, data={"messages": [
            {"id": "mock_ig_msg_1", "platform": "instagram", "senderName": "Follower", "content": "Great content!", "timestamp": "2026-02-08T11:00:00Z", "read": False},
        ], "mock": True})

    def _mock_posts(self) -> SkillResult:
        return SkillResult(success=True, data={"posts": [
            {"id": "mock_ig_post_1", "platform": "instagram", "content": "Sample IG post", "publishedAt": "2026-02-07T14:00:00Z", "engagement": {"likes": 85, "comments": 12, "shares": 0, "reach": 1200}},
        ], "mock": True})

    def _mock_insights(self) -> SkillResult:
        return SkillResult(success=True, data={"instagram": {"postsCount": 8, "totalReach": 8500, "engagementRate": 4.1}, "mock": True})
