"""
Twitter (X) Skill

Extends BaseSkill for Twitter-specific operations:
tweet creation, DM replies, mention monitoring, and engagement tracking.
Includes rate limit handling (300 tweets/3 hours).
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


class TwitterSkill(BaseSkill):
    """Twitter operations via Social MCP server."""

    def __init__(self, vault_interface=None, logger=None):
        super().__init__(name="Twitter", vault_interface=vault_interface, logger=logger)
        self._social_mcp_url = os.environ.get("SOCIAL_MCP_URL", "http://localhost:8002")
        self._calls = deque()
        self._max_calls = 300
        self._period = 10800  # 300 tweets/3 hours

    @property
    def id(self) -> str:
        return "twitter"

    @property
    def description(self) -> str:
        return "Twitter account management: tweets, DMs, mentions, and engagement tracking"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["get_mentions", "get_dms", "get_tweets", "create_tweet", "reply_dm", "get_insights"],
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
            return SkillResult(success=False, error="Twitter rate limit reached (300/3hr)")

        self._record_call()

        handlers = {
            "get_mentions": self._get_mentions,
            "get_dms": self._get_dms,
            "get_tweets": self._get_tweets,
            "create_tweet": self._create_tweet,
            "reply_dm": self._reply_dm,
            "get_insights": self._get_insights,
        }

        handler = handlers.get(operation)
        if not handler:
            return SkillResult(success=False, error=f"Unknown operation: {operation}")

        try:
            return await handler(input_data)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _get_mentions(self, input_data: Dict[str, Any]) -> SkillResult:
        if not httpx:
            return self._mock_mentions()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {}
                if input_data.get("since"):
                    params["since"] = input_data["since"]
                resp = await client.get(f"{self._social_mcp_url}/twitter/mentions", params=params)
                if resp.status_code == 200:
                    return SkillResult(success=True, data={"mentions": resp.json()})
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception:
            return self._mock_mentions()

    async def _get_dms(self, input_data: Dict[str, Any]) -> SkillResult:
        if not httpx:
            return self._mock_dms()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {}
                if input_data.get("since"):
                    params["since"] = input_data["since"]
                resp = await client.get(f"{self._social_mcp_url}/twitter/dms", params=params)
                if resp.status_code == 200:
                    return SkillResult(success=True, data={"dms": resp.json()})
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception:
            return self._mock_dms()

    async def _get_tweets(self, input_data: Dict[str, Any]) -> SkillResult:
        if not httpx:
            return self._mock_tweets()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self._social_mcp_url}/twitter/tweets")
                if resp.status_code == 200:
                    return SkillResult(success=True, data={"tweets": resp.json()})
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception:
            return self._mock_tweets()

    async def _create_tweet(self, input_data: Dict[str, Any]) -> SkillResult:
        approval_ref = input_data.get("approval_ref")
        text = input_data.get("text", "")
        if not approval_ref:
            return SkillResult(success=False, error="approval_ref required for tweet creation")
        if not text:
            return SkillResult(success=False, error="text required")
        if len(text) > 280:
            return SkillResult(success=False, error=f"Tweet too long ({len(text)}/280 chars)")

        if not httpx:
            return SkillResult(success=True, data={"mock": True, "message": "[MOCK] Tweet would be posted"})
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                body = {"approvalRef": approval_ref, "text": text}
                if input_data.get("reply_to_id"):
                    body["replyToId"] = input_data["reply_to_id"]
                resp = await client.post(f"{self._social_mcp_url}/twitter/tweets/create", json=body)
                if resp.status_code == 200:
                    return SkillResult(success=True, data=resp.json())
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _reply_dm(self, input_data: Dict[str, Any]) -> SkillResult:
        approval_ref = input_data.get("approval_ref")
        if not approval_ref:
            return SkillResult(success=False, error="approval_ref required")

        if not httpx:
            return SkillResult(success=True, data={"mock": True, "message": "[MOCK] DM reply would be sent"})
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._social_mcp_url}/twitter/dms/reply",
                    json={
                        "approvalRef": approval_ref,
                        "conversationId": input_data.get("conversation_id", ""),
                        "text": input_data.get("text", ""),
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
                resp = await client.get(f"{self._social_mcp_url}/twitter/insights", params=params)
                if resp.status_code == 200:
                    return SkillResult(success=True, data=resp.json())
                return SkillResult(success=False, error=f"API error: {resp.status_code}")
        except Exception:
            return self._mock_insights()

    def _mock_mentions(self) -> SkillResult:
        return SkillResult(success=True, data={"mentions": [
            {"id": "mock_tw_1", "text": "@business Great service!", "authorUsername": "user123", "createdAt": "2026-02-08T09:00:00Z", "isMention": True, "engagement": {"likes": 5, "retweets": 1, "replies": 0, "impressions": 200}},
        ], "mock": True})

    def _mock_dms(self) -> SkillResult:
        return SkillResult(success=True, data={"dms": [
            {"id": "mock_dm_1", "senderUsername": "customer1", "text": "Can you help with my order?", "createdAt": "2026-02-08T08:30:00Z"},
        ], "mock": True})

    def _mock_tweets(self) -> SkillResult:
        return SkillResult(success=True, data={"tweets": [
            {"id": "mock_tweet_1", "text": "Excited to announce...", "createdAt": "2026-02-07T15:00:00Z", "engagement": {"likes": 42, "retweets": 8, "replies": 3, "impressions": 5000}},
        ], "mock": True})

    def _mock_insights(self) -> SkillResult:
        return SkillResult(success=True, data={"tweetsCount": 12, "totalImpressions": 25000, "engagementRate": 2.8, "followerDelta": 45, "mentionsCount": 18, "mock": True})
