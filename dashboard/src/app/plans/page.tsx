import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { readdir, readFile } from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const PLANS_PATH = path.join(PROJECT_ROOT, "obsidian-vault", "plans");

interface PlanSummary {
  id: string;
  title: string;
  status: string;
  risk_level: string;
  created_at: string;
  source_events: string[];
  filename: string;
}

async function getPlans(): Promise<PlanSummary[]> {
  try {
    const files = await readdir(PLANS_PATH);
    const plans: PlanSummary[] = [];

    for (const file of files.filter((f) => f.endsWith(".md"))) {
      try {
        const content = await readFile(path.join(PLANS_PATH, file), "utf-8");

        if (!content.startsWith("---")) continue;
        const parts = content.split("---");
        if (parts.length < 3) continue;

        const yaml = parts[1];
        const get = (key: string): string => {
          const match = yaml.match(new RegExp(`^${key}:\\s*(.+)$`, "m"));
          return match ? match[1].trim().replace(/^['"]|['"]$/g, "") : "";
        };

        plans.push({
          id: get("id"),
          title: get("title") || file,
          status: get("status") || "draft",
          risk_level: get("risk_level") || "medium",
          created_at: get("created_at"),
          source_events: [],
          filename: file,
        });
      } catch {
        // Skip malformed files
      }
    }

    return plans.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  } catch {
    return [];
  }
}

export default async function PlansPage() {
  const plans = await getPlans();

  const riskVariant = (risk: string) =>
    risk === "high"
      ? "destructive"
      : risk === "medium"
      ? "default"
      : ("secondary" as const);

  const statusVariant = (status: string) =>
    status === "executed"
      ? "default"
      : status === "approved"
      ? "default"
      : ("outline" as const);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Plans</h2>
        <p className="text-muted-foreground">
          AI-generated action plans ({plans.length})
        </p>
      </div>

      {plans.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No plans generated yet. Plans are created when the reasoning loop
            processes inbox events.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {plans.map((plan) => (
            <Card key={plan.id || plan.filename}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{plan.title}</CardTitle>
                  <div className="flex gap-2">
                    <Badge variant={riskVariant(plan.risk_level)}>
                      {plan.risk_level} risk
                    </Badge>
                    <Badge variant={statusVariant(plan.status)}>
                      {plan.status}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>ID: {plan.id?.slice(0, 8) || "N/A"}</span>
                  <span>
                    {plan.created_at
                      ? new Date(plan.created_at).toLocaleString()
                      : "Unknown"}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
