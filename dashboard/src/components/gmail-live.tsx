"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Email {
  id: string;
  threadId: string;
  subject: string;
  sender: string;
  recipient: string;
  date: string;
  snippet: string;
  bodyPreview: string;
  labels: string[];
  hasAttachments: boolean;
}

interface GmailStatus {
  authenticated: boolean;
  email: string;
}

export function GmailLive() {
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [checked, setChecked] = useState(false);

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/gmail/status");
      const data = await res.json();
      setStatus(data);
      return data.authenticated;
    } catch {
      setStatus({ authenticated: false, email: "" });
      return false;
    } finally {
      setChecked(true);
    }
  }, []);

  const fetchEmails = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/gmail/emails");
      if (res.status === 401) {
        setError("Not authenticated — click Connect Gmail to sign in");
        return;
      }
      if (!res.ok) {
        const data = await res.json();
        setError(data.error ?? "Failed to fetch emails");
        return;
      }
      const data = await res.json();
      setEmails(data.emails);
      setLastRefresh(new Date());
    } catch {
      setError("Network error fetching emails");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkStatus().then((authed) => {
      if (authed) fetchEmails();
      else setLoading(false);
    });
  }, [checkStatus, fetchEmails]);

  useEffect(() => {
    if (!status?.authenticated) return;
    const interval = setInterval(fetchEmails, 30000);
    return () => clearInterval(interval);
  }, [status?.authenticated, fetchEmails]);

  const isConnected = status?.authenticated === true;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CardTitle>Live Gmail</CardTitle>
              {isConnected ? (
                <Badge variant="default">Connected: {status.email}</Badge>
              ) : checked ? (
                <Badge variant="destructive">Not Connected</Badge>
              ) : (
                <Badge variant="secondary">Checking...</Badge>
              )}
              {lastRefresh && (
                <span className="text-xs text-muted-foreground">
                  Last refresh: {lastRefresh.toLocaleTimeString()}
                </span>
              )}
            </div>
            <div className="flex gap-2">
              {!isConnected && checked && (
                <Button asChild size="lg">
                  <a href="/api/gmail/auth">Connect Gmail</a>
                </Button>
              )}
              {isConnected && (
                <Button
                  variant="outline"
                  onClick={fetchEmails}
                  disabled={loading}
                >
                  {loading ? "Refreshing..." : "Refresh"}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {!isConnected && checked && (
            <p className="text-sm text-muted-foreground">
              Click <strong>Connect Gmail</strong> to authenticate with Google
              and view real-time emails for{" "}
              <strong>muniba.fte@gmail.com</strong>.
            </p>
          )}

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          {loading && isConnected && emails.length === 0 && (
            <p className="text-muted-foreground">Loading emails...</p>
          )}

          {!loading && emails.length === 0 && isConnected && !error && (
            <p className="text-muted-foreground">No emails found in inbox</p>
          )}
        </CardContent>
      </Card>

      {emails.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {emails.map((email) => (
            <Card key={email.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base leading-tight">
                    {email.subject || "(No subject)"}
                  </CardTitle>
                  {email.hasAttachments && (
                    <Badge variant="outline">Attachments</Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">From:</span>
                  <span className="truncate text-muted-foreground">
                    {email.sender}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">{email.snippet}</p>
                <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
                  <span>{email.date}</span>
                  <div className="flex gap-1">
                    {email.labels.slice(0, 3).map((label) => (
                      <Badge key={label} variant="outline" className="text-xs">
                        {label}
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
