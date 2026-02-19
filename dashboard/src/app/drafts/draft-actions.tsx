"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface DraftActionsProps {
  draftId: string;
  draftType: string;
  filename: string;
  subdir: string;
}

export function DraftActions({ draftId, draftType, filename, subdir }: DraftActionsProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function handleDecision(decision: "approve" | "reject") {
    setLoading(true);
    setResult(null);

    try {
      const res = await fetch(`/api/drafts/${draftId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, filename, subdir, draftType }),
      });

      const data = await res.json();

      if (res.ok) {
        setResult(
          decision === "approve"
            ? "Approved -- draft will be sent"
            : "Rejected -- draft discarded"
        );
      } else {
        setResult(`Error: ${data.error}`);
      }
    } catch {
      setResult("Network error processing decision");
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
      <Button
        onClick={() => handleDecision("approve")}
        disabled={loading}
        className="bg-green-600 hover:bg-green-700"
      >
        {loading ? "Processing..." : "Approve"}
      </Button>
      <Button
        variant="destructive"
        onClick={() => handleDecision("reject")}
        disabled={loading}
      >
        {loading ? "Processing..." : "Reject"}
      </Button>
    </div>
  );
}
