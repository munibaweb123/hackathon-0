import { NextRequest, NextResponse } from "next/server";

const SOCIAL_MCP_URL = process.env.SOCIAL_MCP_URL || "http://localhost:8002";

export async function GET(request: NextRequest) {
  const action = request.nextUrl.searchParams.get("action");
  const platform = request.nextUrl.searchParams.get("platform") || "facebook";

  try {
    switch (action) {
      case "status": {
        // Fetch status for all platforms
        const [fbRes, igRes, twRes] = await Promise.allSettled([
          fetch(`${SOCIAL_MCP_URL}/meta/status?platform=facebook`),
          fetch(`${SOCIAL_MCP_URL}/meta/status?platform=instagram`),
          fetch(`${SOCIAL_MCP_URL}/twitter/status`),
        ]);

        const status: Record<string, unknown> = {};

        if (fbRes.status === "fulfilled" && fbRes.value.ok) {
          status.facebook = await fbRes.value.json();
        } else {
          status.facebook = { connected: false, platform: "facebook", status: "auth_required" };
        }

        if (igRes.status === "fulfilled" && igRes.value.ok) {
          status.instagram = await igRes.value.json();
        } else {
          status.instagram = { connected: false, platform: "instagram", status: "auth_required" };
        }

        if (twRes.status === "fulfilled" && twRes.value.ok) {
          status.twitter = await twRes.value.json();
        } else {
          status.twitter = { connected: false, platform: "twitter", status: "auth_required" };
        }

        return NextResponse.json(status);
      }

      case "messages": {
        const endpoint = platform === "twitter" ? "/twitter/dms" : `/meta/messages?platform=${platform}`;
        const res = await fetch(`${SOCIAL_MCP_URL}${endpoint}`);
        if (!res.ok) {
          return NextResponse.json({ error: "Failed to fetch messages" }, { status: res.status });
        }
        return NextResponse.json(await res.json());
      }

      case "posts": {
        const endpoint = platform === "twitter" ? "/twitter/tweets" : `/meta/posts?platform=${platform}`;
        const res = await fetch(`${SOCIAL_MCP_URL}${endpoint}`);
        if (!res.ok) {
          return NextResponse.json([], { status: 200 });
        }
        return NextResponse.json(await res.json());
      }

      case "insights": {
        const endpoint = platform === "twitter" ? "/twitter/insights" : `/meta/insights?platform=${platform}`;
        const res = await fetch(`${SOCIAL_MCP_URL}${endpoint}`);
        if (!res.ok) {
          return NextResponse.json({ platform, followerCount: 0, followerDelta: 0, postsCount: 0, totalReach: 0, totalEngagement: 0, engagementRate: 0 });
        }
        return NextResponse.json(await res.json());
      }

      default:
        return NextResponse.json(
          { error: "Unknown action. Use: status, messages, posts, insights" },
          { status: 400 }
        );
    }
  } catch {
    return NextResponse.json(
      { error: "Social MCP server unreachable" },
      { status: 503 }
    );
  }
}

export async function POST(request: NextRequest) {
  const action = request.nextUrl.searchParams.get("action");
  const platform = request.nextUrl.searchParams.get("platform") || "meta";

  try {
    switch (action) {
      case "connect": {
        const endpoint = platform === "twitter" ? "/twitter/connect" : "/meta/connect";
        const res = await fetch(`${SOCIAL_MCP_URL}${endpoint}`, { method: "POST" });
        if (!res.ok) {
          return NextResponse.json({ error: "Failed to initiate connection" }, { status: res.status });
        }
        return NextResponse.json(await res.json());
      }

      case "create-post": {
        const body = await request.json();
        const platforms = body.platforms || ["facebook"];
        const endpoint = platforms.includes("twitter") ? "/twitter/tweets/create" : "/meta/posts/create";
        const res = await fetch(`${SOCIAL_MCP_URL}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          return NextResponse.json({ error: "Failed to create post" }, { status: res.status });
        }
        return NextResponse.json(await res.json());
      }

      case "reply-message": {
        const body = await request.json();
        const msgPlatform = body.platform || "facebook";
        const endpoint = msgPlatform === "twitter" ? "/twitter/dms/reply" : "/meta/messages/reply";
        const res = await fetch(`${SOCIAL_MCP_URL}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          return NextResponse.json({ error: "Failed to send reply" }, { status: res.status });
        }
        return NextResponse.json(await res.json());
      }

      default:
        return NextResponse.json(
          { error: "Unknown action. Use: connect, create-post, reply-message" },
          { status: 400 }
        );
    }
  } catch {
    return NextResponse.json(
      { error: "Social MCP server unreachable" },
      { status: 503 }
    );
  }
}
