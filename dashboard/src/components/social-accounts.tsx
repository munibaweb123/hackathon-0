"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface PlatformStatus {
  connected: boolean;
  platform: string;
  accountId?: string;
  pageName?: string;
  followerCount?: number;
  status: string;
}

interface SocialStatus {
  facebook?: PlatformStatus;
  instagram?: PlatformStatus;
  twitter?: PlatformStatus;
}

export function SocialAccounts() {
  const [status, setStatus] = useState<SocialStatus>({});
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);

  useEffect(() => {
    fetchStatus();
  }, []);

  async function fetchStatus() {
    try {
      const res = await fetch("/api/social?action=status");
      if (res.ok) {
        setStatus(await res.json());
      }
    } catch {
      // Social MCP not available
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect(platform: string) {
    setConnecting(platform);
    try {
      const endpoint = platform === "twitter" ? "twitter" : "meta";
      const res = await fetch(`/api/social?action=connect&platform=${endpoint}`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.authUrl) {
          window.open(data.authUrl, "_blank", "width=600,height=700");
        }
      }
    } catch {
      // Connection failed
    } finally {
      setConnecting(null);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Social Media Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  const platforms = [
    { key: "facebook", label: "Facebook", icon: "📘" },
    { key: "instagram", label: "Instagram", icon: "📷" },
    { key: "twitter", label: "Twitter/X", icon: "🐦" },
  ];

  const statusColors: Record<string, string> = {
    active: "bg-green-100 text-green-800",
    expired: "bg-yellow-100 text-yellow-800",
    auth_required: "bg-blue-100 text-blue-800",
    rate_limited: "bg-orange-100 text-orange-800",
    error: "bg-red-100 text-red-800",
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Social Media Accounts</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {platforms.map((platform) => {
            const platformStatus = status[platform.key as keyof SocialStatus];
            const isConnected = platformStatus?.connected;
            const platformStatusValue = platformStatus?.status || "auth_required";

            return (
              <div
                key={platform.key}
                className="flex items-center justify-between p-3 border rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{platform.icon}</span>
                  <div>
                    <p className="font-medium">{platform.label}</p>
                    {isConnected && platformStatus?.pageName && (
                      <p className="text-xs text-muted-foreground">
                        {platformStatus.pageName}
                      </p>
                    )}
                    {isConnected && platformStatus?.followerCount && (
                      <p className="text-xs text-muted-foreground">
                        {platformStatus.followerCount.toLocaleString()} followers
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge
                    className={statusColors[platformStatusValue] || "bg-gray-100"}
                  >
                    {platformStatusValue === "active"
                      ? "Connected"
                      : platformStatusValue === "auth_required"
                      ? "Not Connected"
                      : platformStatusValue}
                  </Badge>

                  {!isConnected && (
                    <button
                      onClick={() => handleConnect(platform.key)}
                      disabled={connecting === platform.key}
                      className="px-3 py-1 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                    >
                      {connecting === platform.key ? "..." : "Connect"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
