import { NextRequest, NextResponse } from "next/server";
import { getOAuth2Client, saveTokens } from "@/lib/gmail";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");

  if (!code) {
    return NextResponse.json({ error: "No authorization code" }, { status: 400 });
  }

  try {
    const client = getOAuth2Client();
    const { tokens } = await client.getToken(code);
    await saveTokens(tokens as Record<string, unknown>);

    return NextResponse.redirect(new URL("/gmail", request.url));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Token exchange failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
