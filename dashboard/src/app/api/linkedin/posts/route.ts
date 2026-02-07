import { NextRequest, NextResponse } from "next/server";
import { fetchPosts, createPost, isAuthenticated } from "@/lib/linkedin";

export const dynamic = "force-dynamic";

export async function GET() {
  const authed = await isAuthenticated();
  if (!authed) {
    return NextResponse.json(
      { error: "Not authenticated", authUrl: "/api/linkedin/auth" },
      { status: 401 }
    );
  }

  try {
    const posts = await fetchPosts();
    return NextResponse.json({ posts, count: posts.length });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to fetch posts";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  const authed = await isAuthenticated();
  if (!authed) {
    return NextResponse.json(
      { error: "Not authenticated" },
      { status: 401 }
    );
  }

  try {
    const { text } = await request.json();
    if (!text || typeof text !== "string" || text.trim().length === 0) {
      return NextResponse.json(
        { error: "Post text is required" },
        { status: 400 }
      );
    }

    const result = await createPost(text.trim());
    return NextResponse.json({ success: true, postId: result.id });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to create post";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
