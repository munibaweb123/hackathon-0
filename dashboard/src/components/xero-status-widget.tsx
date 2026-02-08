"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface XeroStatus {
  connected: boolean;
  tenantId?: string;
  tenantName?: string;
  tokenExpiry?: string;
  status: "active" | "expired" | "auth_required" | "error";
}

export function XeroStatusWidget() {
  const [status, setStatus] = useState<XeroStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStatus() {
      try {
        const res = await fetch("/api/xero?action=status");
        if (res.ok) {
          setStatus(await res.json());
        } else {
          setStatus({ connected: false, status: "auth_required" });
        }
      } catch {
        setStatus({ connected: false, status: "error" });
      } finally {
        setLoading(false);
      }
    }
    fetchStatus();
  }, []);

  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Xero Accounting</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  const statusVariant =
    status?.status === "active"
      ? "default"
      : status?.status === "expired"
      ? "secondary"
      : "outline";

  const statusLabel =
    status?.status === "active"
      ? "Connected"
      : status?.status === "expired"
      ? "Token Expired"
      : status?.status === "error"
      ? "Error"
      : "Setup Required";

  return (
    <Link href="/xero">
      <Card className="transition-colors hover:bg-muted">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Xero Accounting</CardTitle>
            <Badge variant={statusVariant}>{statusLabel}</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {status?.connected ? (
            <div className="space-y-1">
              <p className="text-sm font-medium">{status.tenantName}</p>
              {status.tokenExpiry && (
                <p className="text-xs text-muted-foreground">
                  Token expires: {new Date(status.tokenExpiry).toLocaleDateString()}
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Connect your Xero account to enable financial operations
            </p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
