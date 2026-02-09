"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface WatcherStatus {
  name: string;
  href: string;
  description: string;
  connected: boolean;
  mock_mode: boolean;
  last_check?: string;
  error?: string;
}

export function WatcherStatusGrid() {
  const [watchers, setWatchers] = useState<WatcherStatus[]>([
    { name: "Gmail", href: "/gmail", description: "Email monitoring", connected: false, mock_mode: true },
    { name: "LinkedIn", href: "/linkedin", description: "LinkedIn activity", connected: false, mock_mode: true },
    { name: "WhatsApp", href: "/whatsapp", description: "WhatsApp messages", connected: false, mock_mode: true },
    { name: "Facebook", href: "/social", description: "Facebook pages", connected: false, mock_mode: true },
    { name: "Instagram", href: "/social", description: "Instagram feed", connected: false, mock_mode: true },
    { name: "Twitter", href: "/social", description: "Twitter/X mentions", connected: false, mock_mode: true },
  ]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStatuses() {
      try {
        const [gmailRes, linkedinRes, whatsappRes, socialRes] = await Promise.all([
          fetch("/api/gmail/status").catch(() => null),
          fetch("/api/linkedin/status").catch(() => null),
          fetch("/api/whatsapp/status").catch(() => null),
          fetch("/api/social/status").catch(() => null),
        ]);

        const newWatchers = [...watchers];

        if (gmailRes?.ok) {
          const data = await gmailRes.json();
          newWatchers[0] = {
            ...newWatchers[0],
            connected: data.connected ?? false,
            mock_mode: data.mock_mode ?? true,
            last_check: data.last_check,
          };
        }

        if (linkedinRes?.ok) {
          const data = await linkedinRes.json();
          newWatchers[1] = {
            ...newWatchers[1],
            connected: data.connected ?? false,
            mock_mode: data.mock_mode ?? true,
            last_check: data.last_check,
          };
        }

        if (whatsappRes?.ok) {
          const data = await whatsappRes.json();
          newWatchers[2] = {
            ...newWatchers[2],
            connected: data.connected ?? false,
            mock_mode: data.mock_mode ?? true,
            last_check: data.last_check,
          };
        }

        if (socialRes?.ok) {
          const data = await socialRes.json();
          const platforms = data.platforms ?? {};
          if (platforms.facebook) {
            newWatchers[3] = { ...newWatchers[3], connected: platforms.facebook.connected ?? false, mock_mode: platforms.facebook.mock_mode ?? true, last_check: platforms.facebook.last_check };
          }
          if (platforms.instagram) {
            newWatchers[4] = { ...newWatchers[4], connected: platforms.instagram.connected ?? false, mock_mode: platforms.instagram.mock_mode ?? true, last_check: platforms.instagram.last_check };
          }
          if (platforms.twitter) {
            newWatchers[5] = { ...newWatchers[5], connected: platforms.twitter.connected ?? false, mock_mode: platforms.twitter.mock_mode ?? true, last_check: platforms.twitter.last_check };
          }
        }

        setWatchers(newWatchers);
      } catch (error) {
        console.error("Error fetching watcher statuses:", error);
      } finally {
        setLoading(false);
      }
    }

    fetchStatuses();
    // Refresh every 30 seconds
    const interval = setInterval(fetchStatuses, 30000);
    return () => clearInterval(interval);
  }, []);

  function getStatusBadge(watcher: WatcherStatus) {
    if (watcher.connected) {
      return <Badge className="bg-green-500 hover:bg-green-600">Connected</Badge>;
    }
    if (watcher.mock_mode) {
      return <Badge variant="secondary">Mock Mode</Badge>;
    }
    return <Badge variant="destructive">Disconnected</Badge>;
  }

  function getStatusDot(watcher: WatcherStatus) {
    if (watcher.connected) {
      return "bg-green-500";
    }
    if (watcher.mock_mode) {
      return "bg-yellow-500";
    }
    return "bg-red-500";
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Watcher Status
          {loading && (
            <span className="text-xs font-normal text-muted-foreground">
              Loading...
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {watchers.map((watcher) => (
            <a
              key={watcher.name}
              href={watcher.href}
              className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted"
            >
              <div className="flex items-center gap-3">
                <div
                  className={`h-2.5 w-2.5 rounded-full ${getStatusDot(watcher)}`}
                />
                <div>
                  <p className="font-medium">{watcher.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {watcher.description}
                  </p>
                </div>
              </div>
              {getStatusBadge(watcher)}
            </a>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
