"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ServerHealth {
  status: string;
  lastCheck?: string;
  errorCount: number;
}

interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  servers: Record<string, ServerHealth>;
  timestamp: string;
}

export function MCPHealthGrid() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  async function fetchHealth() {
    try {
      const res = await fetch("/api/metrics?action=health");
      if (res.ok) {
        setHealth(await res.json());
      }
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>MCP Server Health</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  const servers = [
    { id: "coordinator", label: "Coordinator", port: 8000, icon: "🎯" },
    { id: "financial", label: "Financial", port: 8001, icon: "💰" },
    { id: "social", label: "Social", port: 8002, icon: "📱" },
    { id: "communication", label: "Communication", port: 8003, icon: "📧" },
  ];

  const statusColors: Record<string, string> = {
    healthy: "bg-green-100 text-green-800",
    unhealthy: "bg-red-100 text-red-800",
    starting: "bg-blue-100 text-blue-800",
    stopped: "bg-gray-100 text-gray-800",
    unknown: "bg-yellow-100 text-yellow-800",
  };

  const overallStatusColors: Record<string, string> = {
    healthy: "text-green-600",
    degraded: "text-yellow-600",
    unhealthy: "text-red-600",
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>MCP Server Health</CardTitle>
          {health && (
            <Badge className={statusColors[health.status] || "bg-gray-100"}>
              {health.status.toUpperCase()}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {!health ? (
          <p className="text-sm text-muted-foreground">
            Unable to reach coordinator. Ensure MCP servers are running.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {servers.map((server) => {
              const serverHealth = health.servers[server.id];
              const status = serverHealth?.status || "unknown";
              const errorCount = serverHealth?.errorCount || 0;
              const lastCheck = serverHealth?.lastCheck;

              return (
                <div
                  key={server.id}
                  className="p-3 border rounded-lg"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span>{server.icon}</span>
                    <span className="font-medium text-sm">{server.label}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <Badge
                      variant="outline"
                      className={statusColors[status] || "bg-gray-100"}
                    >
                      {status}
                    </Badge>
                    {errorCount > 0 && (
                      <span className="text-xs text-red-500">
                        {errorCount} errors
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Port {server.port}
                    {lastCheck && (
                      <> • Last check: {new Date(lastCheck).toLocaleTimeString()}</>
                    )}
                  </p>
                </div>
              );
            })}
          </div>
        )}

        {health && (
          <p className="text-xs text-muted-foreground mt-3 text-right">
            Updated: {new Date(health.timestamp).toLocaleTimeString()}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
