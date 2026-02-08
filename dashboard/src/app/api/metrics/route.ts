import { NextRequest, NextResponse } from "next/server";

const COORDINATOR_URL = process.env.COORDINATOR_MCP_URL || "http://localhost:8000";

export async function GET(request: NextRequest) {
  const action = request.nextUrl.searchParams.get("action");

  try {
    switch (action) {
      case "health": {
        const res = await fetch(`${COORDINATOR_URL}/health`);
        if (!res.ok) {
          return NextResponse.json(
            { status: "unhealthy", servers: {}, timestamp: new Date().toISOString() },
            { status: 200 }
          );
        }
        return NextResponse.json(await res.json());
      }

      case "servers": {
        const res = await fetch(`${COORDINATOR_URL}/servers`);
        if (!res.ok) {
          return NextResponse.json({ error: "Failed to fetch servers" }, { status: res.status });
        }
        return NextResponse.json(await res.json());
      }

      case "prometheus": {
        const res = await fetch(`${COORDINATOR_URL}/metrics`);
        if (!res.ok) {
          return NextResponse.json({ error: "Failed to fetch metrics" }, { status: res.status });
        }
        const text = await res.text();
        return new NextResponse(text, {
          headers: { "Content-Type": "text/plain" },
        });
      }

      default:
        return NextResponse.json(
          { error: "Unknown action. Use: health, servers, prometheus" },
          { status: 400 }
        );
    }
  } catch {
    // Coordinator not available - return mock healthy status for development
    return NextResponse.json({
      status: "degraded",
      servers: {
        financial: { status: "unknown", errorCount: 0 },
        social: { status: "unknown", errorCount: 0 },
        communication: { status: "unknown", errorCount: 0 },
      },
      timestamp: new Date().toISOString(),
    });
  }
}
