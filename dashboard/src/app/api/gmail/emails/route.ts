import { NextResponse } from "next/server";
import { fetchRecentEmails, isAuthenticated } from "@/lib/gmail";

export const dynamic = "force-dynamic";

export async function GET() {
  const authed = await isAuthenticated();
  if (!authed) {
    return NextResponse.json(
      { error: "Not authenticated", authUrl: "/api/gmail/auth" },
      { status: 401 }
    );
  }

  try {
    const emails = await fetchRecentEmails(20);
    return NextResponse.json({ emails, count: emails.length });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to fetch emails";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
