import { NextRequest, NextResponse } from "next/server";
import { exchangeCodeForToken, saveTokens } from "@/lib/linkedin";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const error = request.nextUrl.searchParams.get("error");

  if (error) {
    return NextResponse.json(
      { error: `LinkedIn OAuth error: ${error}` },
      { status: 400 }
    );
  }

  if (!code) {
    return NextResponse.json(
      { error: "No authorization code" },
      { status: 400 }
    );
  }

  try {
    const tokens = await exchangeCodeForToken(code);
    await saveTokens(tokens);
    return NextResponse.redirect(new URL("/linkedin", request.url));
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Token exchange failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
