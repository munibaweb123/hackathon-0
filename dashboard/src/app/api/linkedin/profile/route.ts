import { NextResponse } from "next/server";
import { fetchProfile, isAuthenticated } from "@/lib/linkedin";

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
    const profile = await fetchProfile();
    return NextResponse.json({ profile });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to fetch profile";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
