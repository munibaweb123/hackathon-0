import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { getGmailEvents } from "@/lib/vault";
import { GmailLive } from "@/components/gmail-live";

export const dynamic = "force-dynamic";

export default async function GmailPage() {
  const events = await getGmailEvents();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Gmail Events</h2>
        <p className="text-muted-foreground">
          Silver Tier — Real-time email monitoring
        </p>
      </div>

      {/* Real-time Gmail API section */}
      <GmailLive />

      <Separator />

      {/* Vault-stored events */}
      <div>
        <h3 className="mb-4 text-lg font-semibold">
          Vault Events ({events.length} captured)
        </h3>

        {events.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No vault Gmail events captured
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {events.map((event) => {
              const d = event.data.raw_data;
              return (
                <Card key={event.filename}>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-base">{d.subject}</CardTitle>
                      <Badge
                        variant={
                          d.priority === "high"
                            ? "destructive"
                            : d.priority === "medium"
                            ? "default"
                            : "secondary"
                        }
                      >
                        {d.priority}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-medium">From:</span>
                      <span className="text-muted-foreground">{d.sender}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-medium">To:</span>
                      <span className="text-muted-foreground">{d.recipient}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{d.body_preview}</p>
                    <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
                      <span>{new Date(event.timestamp).toLocaleString()}</span>
                      <div className="flex gap-2">
                        {d.has_attachments && (
                          <Badge variant="outline">Attachments</Badge>
                        )}
                        <Badge variant="outline">{event.data.event_type}</Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
