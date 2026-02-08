"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface BriefingPreview {
  id: string;
  week_start: string;
  generated_at: string;
  status: "generating" | "complete" | "partial" | "failed";
}

export function CEOBriefingCard() {
  const [latest, setLatest] = useState<BriefingPreview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchLatest() {
      try {
        const res = await fetch("/api/briefings?action=latest");
        if (res.ok) {
          const data = await res.json();
          if (data.briefing) {
            setLatest(data.briefing);
          }
        }
      } catch {
        // No briefings available
      } finally {
        setLoading(false);
      }
    }
    fetchLatest();
  }, []);

  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">CEO Briefing</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  const statusVariant =
    latest?.status === "complete"
      ? "default"
      : latest?.status === "partial"
      ? "secondary"
      : "outline";

  const statusLabel =
    latest?.status === "complete"
      ? "Complete"
      : latest?.status === "partial"
      ? "Partial"
      : latest?.status === "generating"
      ? "Generating"
      : latest?.status === "failed"
      ? "Failed"
      : "None";

  return (
    <Link href="/briefings">
      <Card className="transition-colors hover:bg-muted">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">CEO Briefing</CardTitle>
            {latest && <Badge variant={statusVariant}>{statusLabel}</Badge>}
          </div>
        </CardHeader>
        <CardContent>
          {latest ? (
            <div className="space-y-1">
              <p className="text-sm font-medium">Week of {latest.week_start}</p>
              <p className="text-xs text-muted-foreground">
                Generated: {new Date(latest.generated_at).toLocaleDateString()}
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No briefings generated yet. Configure Xero to enable CEO briefings.
            </p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
