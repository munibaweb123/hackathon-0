import { NextResponse } from "next/server";
import { isAuthenticated, fetchProfile } from "@/lib/linkedin";

export const dynamic = "force-dynamic";

export async function GET() {
  const authed = await isAuthenticated();

  if (!authed) {
    return NextResponse.json({ authenticated: false, profile: null });
  }

  const profile = await fetchProfile();
  return NextResponse.json({ authenticated: true, profile });
}
