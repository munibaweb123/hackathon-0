import { NextRequest, NextResponse } from "next/server";
import { writeFile, readFile, rename, readdir } from "fs/promises";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const VAULT = path.join(PROJECT_ROOT, "obsidian-vault");

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  const { decision, filename } = body as { decision: string; filename?: string };

  if (!["approve", "reject", "modify"].includes(decision)) {
    return NextResponse.json({ error: "Invalid decision" }, { status: 400 });
  }

  // Silver Tier: file-based approval workflow (APPROVAL_REQUIRED_*.md files)
  if (filename && filename.startsWith("APPROVAL_REQUIRED_")) {
    return handleSilverApproval(id, decision, filename);
  }

  // Bronze Tier: JSON-based approval workflow
  return handleBronzeApproval(id, decision);
}

async function handleSilverApproval(
  id: string,
  decision: string,
  filename: string
) {
  const sourcePath = path.join(VAULT, "pending-approval", filename);

  try {
    // Verify file exists
    await readFile(sourcePath, "utf-8");

    // Determine destination folder based on decision
    const destFolder = decision === "approve" ? "Approved" : "Rejected";
    const destPath = path.join(VAULT, destFolder, filename);

    // Move file to the appropriate folder (triggers approval watcher)
    await rename(sourcePath, destPath);

    return NextResponse.json({
      status: "ok",
      decision,
      moved_to: destFolder,
      filename,
    });
  } catch {
    // Try to find the file by ID if exact filename didn't match
    try {
      const files = await readdir(path.join(VAULT, "pending-approval"));
      const match = files.find(
        (f) => f.startsWith("APPROVAL_REQUIRED_") && f.includes(id.slice(0, 8))
      );

      if (match) {
        const matchSource = path.join(VAULT, "pending-approval", match);
        const destFolder = decision === "approve" ? "Approved" : "Rejected";
        const destPath = path.join(VAULT, destFolder, match);

        await rename(matchSource, destPath);

        return NextResponse.json({
          status: "ok",
          decision,
          moved_to: destFolder,
          filename: match,
        });
      }
    } catch {
      // Fall through to 404
    }

    return NextResponse.json(
      { error: "Approval file not found" },
      { status: 404 }
    );
  }
}

async function handleBronzeApproval(id: string, decision: string) {
  const approvalFile = path.join(
    VAULT,
    "pending-approval",
    `approval_request_${id}.json`
  );

  try {
    const content = await readFile(approvalFile, "utf-8");
    const approval = JSON.parse(content);

    const decisionRecord = {
      ...approval,
      decision,
      decided_at: new Date().toISOString(),
      decided_by: "human-dashboard",
    };

    const outPath = path.join(
      VAULT,
      "completed",
      `approval_decision_${id}.json`
    );
    await writeFile(outPath, JSON.stringify(decisionRecord, null, 2));

    return NextResponse.json({ status: "ok", decision });
  } catch {
    return NextResponse.json({ error: "Approval not found" }, { status: 404 });
  }
}
