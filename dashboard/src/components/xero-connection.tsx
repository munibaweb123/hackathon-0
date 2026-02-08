"use client";

import { useState, useEffect } from "react";

interface XeroStatus {
  connected: boolean;
  tenantId?: string;
  tenantName?: string;
  tokenExpiry?: string;
  status: "active" | "expired" | "auth_required" | "error";
}

export function XeroConnection() {
  const [status, setStatus] = useState<XeroStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    fetchStatus();
  }, []);

  async function fetchStatus() {
    try {
      const res = await fetch("/api/xero?action=status");
      if (res.ok) {
        setStatus(await res.json());
      }
    } catch {
      setStatus({ connected: false, status: "error" });
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect() {
    setConnecting(true);
    try {
      const res = await fetch("/api/xero?action=connect", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        if (data.authUrl) {
          window.open(data.authUrl, "_blank", "width=600,height=700");
        }
      }
    } catch {
      // Connection failed
    } finally {
      setConnecting(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-lg font-semibold mb-2">Xero Connection</h3>
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    active: "bg-green-100 text-green-800",
    expired: "bg-yellow-100 text-yellow-800",
    auth_required: "bg-blue-100 text-blue-800",
    error: "bg-red-100 text-red-800",
  };

  const statusLabels: Record<string, string> = {
    active: "Connected",
    expired: "Token Expired",
    auth_required: "Setup Required",
    error: "Error",
  };

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Xero Connection</h3>
        <span
          className={`px-2 py-1 rounded-full text-xs font-medium ${
            statusColors[status?.status || "auth_required"]
          }`}
        >
          {statusLabels[status?.status || "auth_required"]}
        </span>
      </div>

      {status?.connected ? (
        <div className="space-y-2">
          <p className="text-sm">
            <span className="text-muted-foreground">Organization:</span>{" "}
            {status.tenantName || "Unknown"}
          </p>
          {status.tokenExpiry && (
            <p className="text-sm">
              <span className="text-muted-foreground">Token expires:</span>{" "}
              {new Date(status.tokenExpiry).toLocaleDateString()}
            </p>
          )}
          <button
            onClick={fetchStatus}
            className="mt-2 px-3 py-1.5 text-sm border rounded-md hover:bg-accent"
          >
            Refresh Status
          </button>
        </div>
      ) : (
        <div>
          <p className="text-sm text-muted-foreground mb-3">
            Connect your Xero account to enable invoice management and financial
            reporting.
          </p>
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
          >
            {connecting ? "Connecting..." : "Connect Xero"}
          </button>
        </div>
      )}
    </div>
  );
}
