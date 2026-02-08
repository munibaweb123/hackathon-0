import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");

export async function GET() {
  try {
    // Check if WhatsApp session file exists (indicates Playwright session)
    const sessionPath = path.join(PROJECT_ROOT, "whatsapp_session.json");

    let sessionExists = false;
    try {
      await readFile(sessionPath, "utf-8");
      sessionExists = true;
    } catch {
      // No session file
    }

    // Check if orchestrator is running by looking for a status file
    const statusPath = path.join(
      PROJECT_ROOT,
      "obsidian-vault",
      "config",
      "whatsapp_status.json"
    );

    let connected = false;
    try {
      const statusContent = await readFile(statusPath, "utf-8");
      const status = JSON.parse(statusContent);
      connected = status.connected === true;
    } catch {
      // No status file means not connected
    }

    return NextResponse.json({
      connected,
      session_exists: sessionExists,
      mock_mode: !sessionExists,
    });
  } catch {
    return NextResponse.json({
      connected: false,
      session_exists: false,
      mock_mode: true,
    });
  }
}
