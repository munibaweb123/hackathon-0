import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getApprovalRequests } from "@/lib/vault";

export const dynamic = "force-dynamic";

export default async function ApprovalsPage() {
  const requests = await getApprovalRequests();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Approvals</h2>
        <p className="text-muted-foreground">
          Pending human approval requests ({requests.length})
        </p>
      </div>

      {requests.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No pending approval requests
          </CardContent>
        </Card>
      ) : (
        requests.map((req) => (
          <Card key={req.request_id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{req.description}</CardTitle>
                <div className="flex gap-2">
                  <Badge
                    variant={
                      req.risk_level === "high"
                        ? "destructive"
                        : req.risk_level === "medium"
                        ? "default"
                        : "secondary"
                    }
                  >
                    {req.risk_level} risk
                  </Badge>
                  <Badge variant="outline">{req.urgency}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Justification</p>
                <p className="text-sm">{req.justification}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">File Context</p>
                <p className="font-mono text-sm">{req.file_context}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Type</p>
                <Badge variant="outline">{req.request_type}</Badge>
              </div>
              <div>
                <p className="mb-2 text-sm font-medium text-muted-foreground">Options</p>
                <div className="flex gap-2">
                  {req.options.map((opt) => (
                    <Badge key={opt.option_id} variant="outline">
                      {opt.option_id}: {opt.description}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>ID: {req.request_id}</span>
                <span>Created by: {req.created_by}</span>
                <span>{new Date(req.timestamp).toLocaleString()}</span>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
