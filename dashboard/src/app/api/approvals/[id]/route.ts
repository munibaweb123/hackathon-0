import { NextRequest, NextResponse } from "next/server";
import { writeFile, readFile } from "fs/promises";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  const { decision } = body as { decision: string };

  if (!["approve", "reject", "modify"].includes(decision)) {
    return NextResponse.json({ error: "Invalid decision" }, { status: 400 });
  }

  const approvalFile = path.join(
    PROJECT_ROOT,
    "obsidian-vault",
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
      PROJECT_ROOT,
      "obsidian-vault",
      "completed",
      `approval_decision_${id}.json`
    );
    await writeFile(outPath, JSON.stringify(decisionRecord, null, 2));

    return NextResponse.json({ status: "ok", decision });
  } catch {
    return NextResponse.json({ error: "Approval not found" }, { status: 404 });
  }
}
