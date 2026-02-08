import { NextRequest, NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import yaml from "js-yaml";

const VAULT_PATH = process.env.VAULT_PATH || "../obsidian-vault";
const BRIEFINGS_PATH = path.join(VAULT_PATH, "briefings");

interface BriefingMeta {
  id: string;
  week_start: string;
  generated_at: string;
  status: string;
  file_path: string;
}

async function listBriefings(): Promise<BriefingMeta[]> {
  const briefings: BriefingMeta[] = [];

  try {
    const years = await fs.readdir(BRIEFINGS_PATH);

    for (const year of years.sort().reverse()) {
      const yearPath = path.join(BRIEFINGS_PATH, year);
      const stat = await fs.stat(yearPath);

      if (stat.isDirectory()) {
        const files = await fs.readdir(yearPath);

        for (const file of files.sort().reverse()) {
          if (file.startsWith("week-") && file.endsWith(".md")) {
            const filePath = path.join(yearPath, file);
            const content = await fs.readFile(filePath, "utf-8");

            // Parse front matter
            if (content.startsWith("---")) {
              const parts = content.split("---");
              if (parts.length >= 3) {
                const frontMatter = parts[1];
                const data = yaml.load(frontMatter) as Record<string, string>;

                briefings.push({
                  id: data.id || file.replace(".md", ""),
                  week_start: data.week_start || "",
                  generated_at: data.generated_at || "",
                  status: data.status || "unknown",
                  file_path: filePath,
                });
              }
            }
          }
        }
      }
    }
  } catch {
    // Directory doesn't exist or other error
  }

  return briefings;
}

async function getBriefing(id: string): Promise<BriefingMeta & { content: string } | null> {
  const briefings = await listBriefings();
  const briefing = briefings.find((b) => b.id === id);

  if (briefing) {
    try {
      const content = await fs.readFile(briefing.file_path, "utf-8");
      return { ...briefing, content };
    } catch {
      return null;
    }
  }

  return null;
}

async function getLatestBriefing(): Promise<BriefingMeta & { content: string } | null> {
  const briefings = await listBriefings();

  if (briefings.length > 0) {
    const latest = briefings[0];
    try {
      const content = await fs.readFile(latest.file_path, "utf-8");
      return { ...latest, content };
    } catch {
      return latest as BriefingMeta & { content: string };
    }
  }

  return null;
}

function getWeekMonday(): string {
  const today = new Date();
  const day = today.getDay();
  const diff = today.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(today.setDate(diff));
  return monday.toISOString().split("T")[0];
}

async function generateBriefing(weekStart?: string): Promise<BriefingMeta & { content: string }> {
  const week = weekStart || getWeekMonday();
  const id = `briefing-${Date.now()}`;
  const now = new Date().toISOString();

  // Determine week number and year
  const weekDate = new Date(week);
  const year = weekDate.getFullYear();
  const startOfYear = new Date(year, 0, 1);
  const days = Math.floor((weekDate.getTime() - startOfYear.getTime()) / (24 * 60 * 60 * 1000));
  const weekNum = Math.ceil((days + startOfYear.getDay() + 1) / 7);

  // Create directory if needed
  const yearDir = path.join(BRIEFINGS_PATH, String(year));
  await fs.mkdir(yearDir, { recursive: true });

  // Try to fetch financial data (mock for now if MCP unavailable)
  let financialData = null;
  let xeroStatus = "unavailable";

  try {
    const financialUrl = process.env.FINANCIAL_MCP_URL || "http://localhost:8001";
    const res = await fetch(`${financialUrl}/xero/summary?periodStart=${week}&periodEnd=${week}`);
    if (res.ok) {
      financialData = await res.json();
      xeroStatus = "available";
    }
  } catch {
    // Financial MCP not available
  }

  // Generate briefing content
  const status = xeroStatus === "available" ? "complete" : "partial";

  const content = `---
id: ${id}
type: ceo_briefing
week_start: ${week}
generated_at: ${now}
status: ${status}
---

# CEO Weekly Briefing - Week of ${week}

## Financial Summary
${
  financialData
    ? `- **Revenue**: $${(financialData.revenue || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
- **Expenses**: $${(financialData.expenses || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
- **Cash Flow**: $${(financialData.cashFlow || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}`
    : "[DATA UNAVAILABLE] Xero connection not active"
}

## Social Media Metrics
[DATA UNAVAILABLE] Social integrations pending (Phase 5)

## Pending Actions
Review the approvals dashboard for items requiring human approval.

## AI Insights
${
  financialData
    ? "Financial data has been collected for this period. Review the variance alerts section for any significant changes."
    : "Unable to generate insights due to unavailable data sources. Connect Xero to enable financial analysis."
}

## Data Sources
- **Xero**: ${xeroStatus}
- **Social**: unavailable
- **Approvals**: available

---
*Generated on ${new Date().toLocaleString()}*
`;

  // Save to file
  const fileName = `week-${String(weekNum).padStart(2, "0")}.md`;
  const filePath = path.join(yearDir, fileName);
  await fs.writeFile(filePath, content);

  return {
    id,
    week_start: week,
    generated_at: now,
    status,
    file_path: filePath,
    content,
  };
}

export async function GET(request: NextRequest) {
  const action = request.nextUrl.searchParams.get("action");

  try {
    switch (action) {
      case "list": {
        const briefings = await listBriefings();
        return NextResponse.json({ briefings, count: briefings.length });
      }

      case "get": {
        const id = request.nextUrl.searchParams.get("id");
        if (!id) {
          return NextResponse.json({ error: "id required" }, { status: 400 });
        }
        const briefing = await getBriefing(id);
        if (briefing) {
          return NextResponse.json({ briefing });
        }
        return NextResponse.json({ error: "Briefing not found" }, { status: 404 });
      }

      case "latest": {
        const latest = await getLatestBriefing();
        if (latest) {
          return NextResponse.json({ briefing: latest });
        }
        return NextResponse.json({ briefing: null });
      }

      default:
        return NextResponse.json(
          { error: "Unknown action. Use: list, get, latest" },
          { status: 400 }
        );
    }
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to process request", details: String(err) },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  const action = request.nextUrl.searchParams.get("action");

  try {
    switch (action) {
      case "generate": {
        const body = await request.json().catch(() => ({}));
        const weekStart = body.week_start;
        const briefing = await generateBriefing(weekStart);
        return NextResponse.json({ success: true, briefing });
      }

      default:
        return NextResponse.json(
          { error: "Unknown action. Use: generate" },
          { status: 400 }
        );
    }
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to generate briefing", details: String(err) },
      { status: 500 }
    );
  }
}
