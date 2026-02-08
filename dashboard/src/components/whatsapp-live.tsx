"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface WhatsAppStatus {
  connected: boolean;
  session_exists: boolean;
  mock_mode: boolean;
}

interface WhatsAppEvent {
  id: string;
  chat_name: string;
  sender: string;
  content: string;
  timestamp: string;
  priority: string;
}

export function WhatsAppLive() {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [events, setEvents] = useState<WhatsAppEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
    fetchEvents();
  }, []);

  async function fetchStatus() {
    try {
      const res = await fetch("/api/whatsapp/status");
      if (res.ok) {
        setStatus(await res.json());
      }
    } catch {
      setStatus({ connected: false, session_exists: false, mock_mode: true });
    } finally {
      setLoading(false);
    }
  }

  async function fetchEvents() {
    try {
      const res = await fetch("/api/whatsapp/events");
      if (res.ok) {
        setEvents(await res.json());
      }
    } catch {
      setEvents([]);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          Loading WhatsApp status...
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>WhatsApp Connection</CardTitle>
            <Badge variant={status?.connected ? "default" : "destructive"}>
              {status?.connected ? "Connected" : "Disconnected"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {status?.connected ? (
            <p className="text-sm text-muted-foreground">
              WhatsApp Web session is active. Messages are being monitored.
            </p>
          ) : status?.mock_mode ? (
            <p className="text-sm text-muted-foreground">
              Running in mock mode. To connect WhatsApp, run the orchestrator
              and scan the QR code in the browser window.
            </p>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                WhatsApp is not connected. Start the orchestrator to begin
                the QR code authentication flow.
              </p>
              <code className="block rounded bg-muted p-2 text-xs">
                python agent-skills/orchestrator.py
              </code>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Messages */}
      <Card>
        <CardHeader>
          <CardTitle>Recent WhatsApp Events</CardTitle>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No WhatsApp events detected yet.
            </p>
          ) : (
            <div className="space-y-3">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-start justify-between rounded-lg border p-3"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{event.chat_name}</p>
                    <p className="text-sm text-muted-foreground">
                      {event.content.slice(0, 120)}
                      {event.content.length > 120 ? "..." : ""}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(event.timestamp).toLocaleString()}
                    </p>
                  </div>
                  <Badge
                    variant={
                      event.priority === "high"
                        ? "destructive"
                        : event.priority === "medium"
                        ? "default"
                        : "secondary"
                    }
                  >
                    {event.priority}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
