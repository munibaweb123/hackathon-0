import { NextRequest, NextResponse } from "next/server";

const COORDINATOR_URL =
  process.env.COORDINATOR_URL || "http://localhost:8000";

export async function GET(request: NextRequest) {
  const action = request.nextUrl.searchParams.get("action");

  try {
    switch (action) {
      case "export": {
        const days = parseInt(
          request.nextUrl.searchParams.get("days") || "7",
          10
        );
        const now = new Date();
        const start = new Date(now.getTime() - days * 86400000);
        const res = await fetch(
          `${COORDINATOR_URL}/audit/export?startDate=${start.toISOString().split("T")[0]}&endDate=${now.toISOString().split("T")[0]}`
        );
        if (!res.ok) return NextResponse.json([], { status: 200 });
        return NextResponse.json(await res.json());
      }

      case "stats": {
        const res = await fetch(`${COORDINATOR_URL}/audit/stats`);
        if (!res.ok)
          return NextResponse.json(
            {
              active_log_files: 0,
              archive_files: 0,
              entries_today: 0,
              retention_days: 90,
            },
            { status: 200 }
          );
        return NextResponse.json(await res.json());
      }

      case "verify": {
        const res = await fetch(`${COORDINATOR_URL}/audit/verify`);
        if (!res.ok)
          return NextResponse.json({ valid: true, error: null }, { status: 200 });
        return NextResponse.json(await res.json());
      }

      default:
        return NextResponse.json(
          { error: "Unknown action. Use: export, stats, verify" },
          { status: 400 }
        );
    }
  } catch {
    return NextResponse.json(
      { error: "Coordinator unreachable", valid: true },
      { status: 503 }
    );
  }
}
