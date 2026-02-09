"""
Social MCP Server

Handles Meta (Facebook/Instagram) and Twitter integrations for Gold Tier.
Provides OAuth flows, data retrieval, and write operations with approval.

Supports Gold Tier requirements:
- FR-006 to FR-011: Meta/Twitter integration
- FR-016: Domain-separated MCP server for social platforms
"""

import os
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

try:
    from core.credential_manager import CredentialManager
    from core.audit_logger import AuditLogger
    from core.metrics_collector import get_metrics
    from models.audit_entry import ActorType, ActionResult
    from models.social_account import SocialAccount, SocialPlatform, SocialAccountStatus
except ImportError:
    CredentialManager = None
    AuditLogger = None


# Pydantic models
class SocialAccountStatus(BaseModel):
    """Social account connection status."""
    connected: bool
    platform: str
    accountId: Optional[str] = None
    pageName: Optional[str] = None
    followerCount: Optional[int] = None
    tokenExpiry: Optional[str] = None
    status: str


class SocialMessage(BaseModel):
    """Social media message."""
    messageId: str
    platform: str
    senderId: str
    senderName: str
    content: str
    receivedAt: str
    isRead: bool = False


class SocialPost(BaseModel):
    """Social media post."""
    postId: str
    platform: str
    content: str
    publishedAt: str
    likes: int = 0
    comments: int = 0
    shares: int = 0
    reach: int = 0


class CreatePostRequest(BaseModel):
    """Post creation request."""
    approvalRef: str
    content: str
    platforms: List[str]
    mediaUrls: Optional[List[str]] = None
    scheduledFor: Optional[str] = None


class ReplyMessageRequest(BaseModel):
    """Message reply request."""
    approvalRef: str
    messageId: str
    content: str


class SocialInsights(BaseModel):
    """Social media insights/analytics."""
    platform: str
    followerCount: int = 0
    followerDelta: int = 0
    postsCount: int = 0
    totalReach: int = 0
    totalEngagement: int = 0
    engagementRate: float = 0.0


# Create FastAPI app
app = FastAPI(
    title="Gold Tier Social MCP Server",
    version="1.0.0",
    description="Social domain MCP server handling Meta and Twitter integration",
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
_credential_manager: Optional[CredentialManager] = None
_audit_logger: Optional[AuditLogger] = None
_oauth_states: Dict[str, dict] = {}


def get_credential_manager():
    global _credential_manager
    if _credential_manager is None and CredentialManager:
        _credential_manager = CredentialManager()
    return _credential_manager


def get_audit_logger():
    global _audit_logger
    if _audit_logger is None and AuditLogger:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_social_account(platform: str) -> Optional[SocialAccount]:
    """Load social account from vault."""
    cm = get_credential_manager()
    if cm and cm.has_credentials(f"social_{platform}"):
        try:
            creds = cm.load_credentials(f"social_{platform}")
            return SocialAccount.from_dict(creds)
        except Exception:
            pass
    return None


def save_social_account(account: SocialAccount) -> None:
    """Save social account to vault."""
    cm = get_credential_manager()
    if cm:
        cm.save_credentials(f"social_{account.platform.value}", account.to_dict())


@app.on_event("startup")
async def startup():
    global _credential_manager, _audit_logger
    if CredentialManager:
        _credential_manager = CredentialManager()
    if AuditLogger:
        _audit_logger = AuditLogger()


@app.get("/health")
async def health_check():
    """Health check endpoint for coordinator."""
    fb_account = get_social_account("facebook")
    ig_account = get_social_account("instagram")
    tw_account = get_social_account("twitter")

    return {
        "status": "healthy",
        "domain": "social",
        "platforms": {
            "facebook": fb_account.status.value if fb_account else "auth_required",
            "instagram": ig_account.status.value if ig_account else "auth_required",
            "twitter": tw_account.status.value if tw_account else "auth_required",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


# ===== Meta OAuth Endpoints =====

@app.post("/meta/connect")
async def meta_connect():
    """Initiate Meta OAuth connection for Facebook/Instagram."""
    client_id = os.environ.get("META_APP_ID")
    redirect_uri = os.environ.get("META_REDIRECT_URI", "http://localhost:8002/meta/callback")

    if not client_id:
        raise HTTPException(status_code=500, detail="META_APP_ID not configured")

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {"platform": "meta", "created": datetime.utcnow().isoformat()}

    scopes = "pages_show_list,pages_read_engagement,pages_manage_posts,pages_messaging,instagram_basic,instagram_content_publish"
    auth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes}"
        f"&state={state}"
    )

    return {"authUrl": auth_url, "state": state}


@app.get("/meta/callback")
async def meta_callback(code: str, state: str):
    """Handle Meta OAuth callback."""
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    del _oauth_states[state]

    # Mock successful connection for development
    fb_account = SocialAccount(
        platform=SocialPlatform.FACEBOOK,
        account_id="mock-fb-account",
        page_id="mock-page-id",
    )
    fb_account.mark_active()
    save_social_account(fb_account)

    logger = get_audit_logger()
    if logger:
        logger.append(
            action_type="meta.oauth.connect",
            actor=ActorType.USER,
            server_id="social",
            details={"platform": "meta"},
            result=ActionResult.SUCCESS,
        )

    return SocialAccountStatus(
        connected=True,
        platform="facebook",
        accountId=fb_account.account_id,
        pageName="Demo Page",
        status="active",
    )


@app.get("/meta/status")
async def meta_status(platform: str = Query("facebook")):
    """Get Meta account status."""
    account = get_social_account(platform)

    if not account:
        return SocialAccountStatus(connected=False, platform=platform, status="auth_required")

    return SocialAccountStatus(
        connected=account.is_active(),
        platform=platform,
        accountId=account.account_id,
        pageName="Demo Page",
        followerCount=account.follower_count,
        tokenExpiry=account.token_expiry,
        status=account.status.value,
    )


@app.get("/meta/messages", response_model=List[SocialMessage])
async def meta_messages(platform: str = Query("facebook"), since: Optional[str] = None):
    """Get messages from Facebook/Instagram."""
    account = get_social_account(platform)
    if not account or not account.is_active():
        raise HTTPException(status_code=503, detail=f"{platform} connection unavailable")

    # Mock messages for development
    messages = [
        SocialMessage(
            messageId="msg-001",
            platform=platform,
            senderId="user-123",
            senderName="John Customer",
            content="Hi, I have a question about your services.",
            receivedAt=datetime.utcnow().isoformat(),
            isRead=False,
        ),
    ]

    return messages


@app.get("/meta/posts", response_model=List[SocialPost])
async def meta_posts(platform: str = Query("facebook")):
    """Get recent posts from Facebook/Instagram."""
    account = get_social_account(platform)
    if not account or not account.is_active():
        raise HTTPException(status_code=503, detail=f"{platform} connection unavailable")

    posts = [
        SocialPost(
            postId="post-001",
            platform=platform,
            content="Check out our latest updates!",
            publishedAt="2026-02-07T10:00:00Z",
            likes=45,
            comments=12,
            shares=5,
            reach=1200,
        ),
    ]

    return posts


@app.get("/meta/insights", response_model=SocialInsights)
async def meta_insights(platform: str = Query("facebook")):
    """Get insights/analytics for Meta platforms."""
    account = get_social_account(platform)

    return SocialInsights(
        platform=platform,
        followerCount=account.follower_count if account else 0,
        followerDelta=12,
        postsCount=5,
        totalReach=5000,
        totalEngagement=350,
        engagementRate=7.0,
    )


@app.post("/meta/posts/create", response_model=SocialPost)
async def meta_create_post(request: CreatePostRequest):
    """Create a post on Meta platforms (requires approval)."""
    if not request.approvalRef:
        raise HTTPException(status_code=403, detail="Approval reference required")

    # Validate accounts
    for platform in request.platforms:
        if platform in ["facebook", "instagram"]:
            account = get_social_account(platform)
            if not account or not account.is_active():
                raise HTTPException(status_code=503, detail=f"{platform} connection unavailable")

    # Mock post creation
    import uuid
    new_post = SocialPost(
        postId=f"post-{uuid.uuid4().hex[:8]}",
        platform=request.platforms[0],
        content=request.content,
        publishedAt=datetime.utcnow().isoformat(),
        likes=0,
        comments=0,
        shares=0,
        reach=0,
    )

    logger = get_audit_logger()
    if logger:
        logger.append(
            action_type="meta.post.create",
            actor=ActorType.AI,
            server_id="social",
            details={"post_id": new_post.postId, "platforms": request.platforms},
            result=ActionResult.SUCCESS,
            approval_ref=request.approvalRef,
        )

    return new_post


@app.post("/meta/messages/reply")
async def meta_reply_message(request: ReplyMessageRequest):
    """Reply to a message (requires approval)."""
    if not request.approvalRef:
        raise HTTPException(status_code=403, detail="Approval reference required")

    logger = get_audit_logger()
    if logger:
        logger.append(
            action_type="meta.message.reply",
            actor=ActorType.AI,
            server_id="social",
            details={"message_id": request.messageId},
            result=ActionResult.SUCCESS,
            approval_ref=request.approvalRef,
        )

    return {"success": True, "messageId": request.messageId}


# ===== Twitter OAuth Endpoints =====

@app.post("/twitter/connect")
async def twitter_connect():
    """Initiate Twitter OAuth connection."""
    client_id = os.environ.get("TWITTER_CLIENT_ID")
    redirect_uri = os.environ.get("TWITTER_REDIRECT_URI", "http://localhost:8002/twitter/callback")

    if not client_id:
        raise HTTPException(status_code=500, detail="TWITTER_CLIENT_ID not configured")

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {"platform": "twitter", "created": datetime.utcnow().isoformat()}

    scopes = "tweet.read tweet.write users.read dm.read dm.write offline.access"
    auth_url = (
        f"https://twitter.com/i/oauth2/authorize"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes}"
        f"&state={state}"
        f"&code_challenge=challenge"
        f"&code_challenge_method=plain"
    )

    return {"authUrl": auth_url, "state": state}


@app.get("/twitter/callback")
async def twitter_callback(code: str, state: str):
    """Handle Twitter OAuth callback."""
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    del _oauth_states[state]

    tw_account = SocialAccount(
        platform=SocialPlatform.TWITTER,
        account_id="mock-twitter-account",
    )
    tw_account.mark_active()
    save_social_account(tw_account)

    logger = get_audit_logger()
    if logger:
        logger.append(
            action_type="twitter.oauth.connect",
            actor=ActorType.USER,
            server_id="social",
            details={"platform": "twitter"},
            result=ActionResult.SUCCESS,
        )

    return SocialAccountStatus(
        connected=True,
        platform="twitter",
        accountId=tw_account.account_id,
        status="active",
    )


@app.get("/twitter/status")
async def twitter_status():
    """Get Twitter account status."""
    account = get_social_account("twitter")

    if not account:
        return SocialAccountStatus(connected=False, platform="twitter", status="auth_required")

    return SocialAccountStatus(
        connected=account.is_active(),
        platform="twitter",
        accountId=account.account_id,
        followerCount=account.follower_count,
        tokenExpiry=account.token_expiry,
        status=account.status.value,
    )


@app.get("/twitter/mentions", response_model=List[SocialMessage])
async def twitter_mentions(since: Optional[str] = None):
    """Get Twitter mentions."""
    account = get_social_account("twitter")
    if not account or not account.is_active():
        raise HTTPException(status_code=503, detail="Twitter connection unavailable")

    mentions = [
        SocialMessage(
            messageId="mention-001",
            platform="twitter",
            senderId="user-456",
            senderName="@customerX",
            content="@yourbusiness Great product!",
            receivedAt=datetime.utcnow().isoformat(),
        ),
    ]

    return mentions


@app.get("/twitter/dms", response_model=List[SocialMessage])
async def twitter_dms(since: Optional[str] = None):
    """Get Twitter direct messages."""
    account = get_social_account("twitter")
    if not account or not account.is_active():
        raise HTTPException(status_code=503, detail="Twitter connection unavailable")

    dms = [
        SocialMessage(
            messageId="dm-001",
            platform="twitter",
            senderId="user-789",
            senderName="Interested Buyer",
            content="Can you tell me more about pricing?",
            receivedAt=datetime.utcnow().isoformat(),
        ),
    ]

    return dms


@app.get("/twitter/tweets", response_model=List[SocialPost])
async def twitter_tweets():
    """Get recent tweets."""
    account = get_social_account("twitter")
    if not account or not account.is_active():
        raise HTTPException(status_code=503, detail="Twitter connection unavailable")

    tweets = [
        SocialPost(
            postId="tweet-001",
            platform="twitter",
            content="Excited to announce our new feature!",
            publishedAt="2026-02-07T14:00:00Z",
            likes=89,
            comments=23,
            shares=15,
            reach=5000,
        ),
    ]

    return tweets


@app.get("/twitter/insights", response_model=SocialInsights)
async def twitter_insights():
    """Get Twitter analytics."""
    account = get_social_account("twitter")

    return SocialInsights(
        platform="twitter",
        followerCount=account.follower_count if account else 0,
        followerDelta=45,
        postsCount=12,
        totalReach=25000,
        totalEngagement=1200,
        engagementRate=4.8,
    )


@app.post("/twitter/tweets/create", response_model=SocialPost)
async def twitter_create_tweet(request: CreatePostRequest):
    """Create a tweet (requires approval)."""
    if not request.approvalRef:
        raise HTTPException(status_code=403, detail="Approval reference required")

    account = get_social_account("twitter")
    if not account or not account.is_active():
        raise HTTPException(status_code=503, detail="Twitter connection unavailable")

    # Check character limit
    if len(request.content) > 280:
        raise HTTPException(status_code=400, detail="Tweet exceeds 280 character limit")

    import uuid
    new_tweet = SocialPost(
        postId=f"tweet-{uuid.uuid4().hex[:8]}",
        platform="twitter",
        content=request.content,
        publishedAt=datetime.utcnow().isoformat(),
    )

    logger = get_audit_logger()
    if logger:
        logger.append(
            action_type="twitter.tweet.create",
            actor=ActorType.AI,
            server_id="social",
            details={"tweet_id": new_tweet.postId},
            result=ActionResult.SUCCESS,
            approval_ref=request.approvalRef,
        )

    return new_tweet


@app.post("/twitter/dms/reply")
async def twitter_reply_dm(request: ReplyMessageRequest):
    """Reply to a Twitter DM (requires approval)."""
    if not request.approvalRef:
        raise HTTPException(status_code=403, detail="Approval reference required")

    logger = get_audit_logger()
    if logger:
        logger.append(
            action_type="twitter.dm.reply",
            actor=ActorType.AI,
            server_id="social",
            details={"message_id": request.messageId},
            result=ActionResult.SUCCESS,
            approval_ref=request.approvalRef,
        )

    return {"success": True, "messageId": request.messageId}


@app.post("/action/execute")
async def action_execute(request: dict):
    """Execute an action routed from the coordinator. Integrates with RetryQueue (T071)."""
    action_type = request.get("actionType", "")
    approval_ref = request.get("approvalRef", "")
    payload = request.get("payload", {})

    try:
        if action_type.startswith("meta."):
            if action_type == "meta.post.create":
                req = CreatePostRequest(
                    approvalRef=approval_ref,
                    content=payload.get("content", ""),
                    platforms=payload.get("platforms", ["facebook"]),
                )
                result = await meta_create_post(req)
                return {"success": True, "result": result.dict()}

        elif action_type.startswith("twitter."):
            if action_type == "twitter.tweet.create":
                req = CreatePostRequest(
                    approvalRef=approval_ref,
                    content=payload.get("content", ""),
                    platforms=["twitter"],
                )
                result = await twitter_create_tweet(req)
                return {"success": True, "result": result.dict()}

        return {"success": False, "error": f"Unknown action type: {action_type}"}

    except Exception as e:
        # Queue for retry on failure (FR-020)
        try:
            from core.retry_queue import RetryQueue
            retry_queue = RetryQueue()
            retry_queue.add(
                action_type=action_type,
                action_payload=payload,
                failure_reason=str(e),
                approval_ref=approval_ref,
            )
        except ImportError:
            pass
        return {"success": False, "error": str(e), "queued_for_retry": True}


def run_social_server(host: str = "0.0.0.0", port: int = 8002):
    """Run the social MCP server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    port = int(os.environ.get("SOCIAL_MCP_PORT", 8002))
    run_social_server(port=port)
