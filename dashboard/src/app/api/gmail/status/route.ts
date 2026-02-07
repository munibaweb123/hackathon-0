import { NextResponse } from "next/server";
import { isAuthenticated } from "@/lib/gmail";

export const dynamic = "force-dynamic";

export async function GET() {
  const authed = await isAuthenticated();
  return NextResponse.json({
    authenticated: authed,
    email: process.env.GMAIL_USER_EMAIL ?? "unknown",
  });
}
