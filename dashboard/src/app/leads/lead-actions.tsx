"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface LeadActionsProps {
  leadId: string;
  filename: string;
  currentStatus: string;
  nextStatus: string;
}

export function LeadActions({
  leadId,
  filename,
  currentStatus,
  nextStatus,
}: LeadActionsProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function handleTransition() {
    setLoading(true);
    setResult(null);

    try {
      const res = await fetch(`/api/leads/${leadId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "transition",
          filename,
          from: currentStatus,
          to: nextStatus,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setResult(`Moved to ${nextStatus}`);
      } else {
        setResult(`Error: ${data.error}`);
      }
    } catch {
      setResult("Network error processing transition");
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <p
        className={`text-sm font-medium ${
          result.startsWith("Error") ? "text-destructive" : "text-green-600"
        }`}
      >
        {result}
      </p>
    );
  }

  return (
    <div className="flex gap-3 pt-2">
      <Button onClick={handleTransition} disabled={loading} size="sm">
        {loading
          ? "Processing..."
          : `Move to ${nextStatus.charAt(0).toUpperCase() + nextStatus.slice(1)}`}
      </Button>
    </div>
  );
}
