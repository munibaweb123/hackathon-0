import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getApprovalRequests, getSilverApprovals } from "@/lib/vault";
import { ApprovalActions } from "./approval-actions";

export const dynamic = "force-dynamic";

export default async function ApprovalsPage() {
  const [requests, silverApprovals] = await Promise.all([
    getApprovalRequests(),
    getSilverApprovals(),
  ]);

  const totalCount = requests.length + silverApprovals.length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Approvals</h2>
        <p className="text-muted-foreground">
          Pending human approval requests ({totalCount})
        </p>
      </div>

      {/* Silver Tier: APPROVAL_REQUIRED files */}
      {silverApprovals.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Action Approvals</h3>
          {silverApprovals.map((approval) => (
            <Card key={approval.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">
                    {approval.action_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  </CardTitle>
                  <div className="flex gap-2">
                    <Badge
                      variant={
                        approval.risk_level === "high"
                          ? "destructive"
                          : approval.risk_level === "medium"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {approval.risk_level} risk
                    </Badge>
                    <Badge variant="outline">{approval.status}</Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {approval.description && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Description</p>
                    <p className="text-sm">{approval.description}</p>
                  </div>
                )}
                {approval.context && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Context</p>
                    <p className="text-sm">{approval.context}</p>
                  </div>
                )}
                {approval.proposed_content && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Proposed Content</p>
                    <pre className="whitespace-pre-wrap rounded bg-muted p-3 text-sm">
                      {approval.proposed_content}
                    </pre>
                  </div>
                )}
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>ID: {approval.id.slice(0, 8)}</span>
                  {approval.plan_id && approval.plan_id !== "null" && (
                    <span>Plan: {approval.plan_id.slice(0, 8)}</span>
                  )}
                  <span>Expires: {new Date(approval.expires_at).toLocaleString()}</span>
                </div>

                <ApprovalActions
                  approvalId={approval.id}
                  filename={approval.file_path?.split("/").pop() ?? ""}
                />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Bronze Tier: JSON approval requests */}
      {requests.length > 0 && (
        <div className="space-y-4">
          {silverApprovals.length > 0 && (
            <h3 className="text-lg font-semibold">Legacy Requests</h3>
          )}
          {requests.map((req) => (
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
          ))}
        </div>
      )}

      {totalCount === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No pending approval requests
          </CardContent>
        </Card>
      )}
    </div>
  );
}
