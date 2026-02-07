import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { getAuditLogs } from "@/lib/vault";

export const dynamic = "force-dynamic";

const logTypeColors: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  system_event: "default",
  watcher_event: "secondary",
  security_event: "destructive",
  approval_event: "outline",
};

export default async function AuditPage() {
  const logs = await getAuditLogs(200);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Audit Logs</h2>
        <p className="text-muted-foreground">
          Activity and security audit trail ({logs.length} entries)
        </p>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Timestamp</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Event</TableHead>
            <TableHead>Component</TableHead>
            <TableHead>Message</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground">
                No audit logs found
              </TableCell>
            </TableRow>
          ) : (
            logs.map((log, i) => (
              <TableRow key={i}>
                <TableCell className="whitespace-nowrap text-xs">
                  {new Date(log.timestamp).toLocaleString()}
                </TableCell>
                <TableCell>
                  <Badge variant={logTypeColors[log.log_type] ?? "outline"}>
                    {log.log_type}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-sm">
                  {log.event_type}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {log.component ?? log.source ?? "-"}
                </TableCell>
                <TableCell className="max-w-md truncate text-sm">
                  {log.message ?? "-"}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
