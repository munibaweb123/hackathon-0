import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getVaultStats, getAuditLogs } from "@/lib/vault";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [stats, logs] = await Promise.all([
    getVaultStats(),
    getAuditLogs(10),
  ]);

  const statCards = [
    { label: "Inbox", value: stats.inbox, color: "text-blue-600" },
    { label: "Processing", value: stats.processing, color: "text-yellow-600" },
    { label: "Pending Approval", value: stats.pendingApproval, color: "text-orange-600" },
    { label: "Completed", value: stats.completed, color: "text-green-600" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <p className="text-muted-foreground">AI Employee system overview</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((s) => (
          <Card key={s.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {s.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${s.color}`}>{s.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {logs.length === 0 ? (
            <p className="text-muted-foreground">No recent activity</p>
          ) : (
            <div className="space-y-3">
              {logs.map((log, i) => (
                <div
                  key={i}
                  className="flex items-start justify-between border-b pb-2 last:border-0"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{log.event_type}</Badge>
                      {log.component && (
                        <span className="text-xs text-muted-foreground">
                          {log.component}
                        </span>
                      )}
                    </div>
                    <p className="text-sm">{log.message}</p>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {new Date(log.timestamp).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>System Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Tier</p>
              <p className="font-semibold">Bronze + Silver</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Mode</p>
              <p className="font-semibold">File-Based + Gmail API</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Human Oversight</p>
              <Badge variant="default">Active</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Security</p>
              <Badge variant="default">Enforced</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
