import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { readFile } from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

async function getConfig(): Promise<string> {
  try {
    const configPath = path.resolve(process.cwd(), "..", "config.yaml");
    return await readFile(configPath, "utf-8");
  } catch {
    return "No config.yaml found";
  }
}

export default async function SettingsPage() {
  const configContent = await getConfig();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Settings</h2>
        <p className="text-muted-foreground">System configuration (read-only)</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Tier Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">Bronze Tier</span>
              <Badge variant="default">Active</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Silver Tier (Gmail)</span>
              <Badge variant="default">Active</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Gold Tier</span>
              <Badge variant="secondary">Not Available</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Security Constraints</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">Human Oversight</span>
              <Badge variant="default">Required</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">File Boundary Enforcement</span>
              <Badge variant="default">Enforced</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Audit Logging</span>
              <Badge variant="default">Enabled</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Network Access (Bronze)</span>
              <Badge variant="destructive">Blocked</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Gmail API (Silver)</span>
              <Badge variant="default">Read-only</Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configuration File</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-auto rounded-md bg-muted p-4 text-sm">
            {configContent}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
