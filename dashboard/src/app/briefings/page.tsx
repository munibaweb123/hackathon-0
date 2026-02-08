"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Briefing {
  id: string;
  week_start: string;
  generated_at: string;
  status: "generating" | "complete" | "partial" | "failed";
  content?: string;
  file_path?: string;
}

export default function BriefingsPage() {
  const [briefings, setBriefings] = useState<Briefing[]>([]);
  const [selectedBriefing, setSelectedBriefing] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    fetchBriefings();
  }, []);

  async function fetchBriefings() {
    setLoading(true);
    try {
      const res = await fetch("/api/briefings?action=list");
      if (res.ok) {
        const data = await res.json();
        setBriefings(data.briefings || []);
      }
    } catch {
      setBriefings([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      const res = await fetch("/api/briefings?action=generate", { method: "POST" });
      if (res.ok) {
        await fetchBriefings();
      }
    } catch {
      // Generation failed
    } finally {
      setGenerating(false);
    }
  }

  async function handleSelectBriefing(briefing: Briefing) {
    try {
      const res = await fetch(`/api/briefings?action=get&id=${briefing.id}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedBriefing(data.briefing || briefing);
      }
    } catch {
      setSelectedBriefing(briefing);
    }
  }

  const statusColors: Record<string, string> = {
    complete: "bg-green-100 text-green-800",
    partial: "bg-yellow-100 text-yellow-800",
    generating: "bg-blue-100 text-blue-800",
    failed: "bg-red-100 text-red-800",
  };

  const statusLabels: Record<string, string> = {
    complete: "Complete",
    partial: "Partial",
    generating: "Generating",
    failed: "Failed",
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">CEO Briefings</h1>
          <p className="text-muted-foreground">
            Weekly business intelligence reports
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
        >
          {generating ? "Generating..." : "Generate New Briefing"}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Briefing History</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <p className="text-sm text-muted-foreground">Loading...</p>
              ) : briefings.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No briefings generated yet. Click &quot;Generate New Briefing&quot; to create
                  one.
                </p>
              ) : (
                <div className="space-y-2">
                  {briefings.map((briefing) => (
                    <button
                      key={briefing.id}
                      onClick={() => handleSelectBriefing(briefing)}
                      className={`w-full text-left p-3 rounded-md border transition-colors ${
                        selectedBriefing?.id === briefing.id
                          ? "bg-accent border-primary"
                          : "hover:bg-muted"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-sm">
                          Week of {briefing.week_start}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs ${
                            statusColors[briefing.status] || "bg-gray-100"
                          }`}
                        >
                          {statusLabels[briefing.status] || briefing.status}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {new Date(briefing.generated_at).toLocaleDateString()}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          <Card className="h-full">
            <CardHeader>
              <CardTitle className="text-lg">
                {selectedBriefing
                  ? `Briefing - Week of ${selectedBriefing.week_start}`
                  : "Select a Briefing"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedBriefing?.content ? (
                <div className="prose prose-sm max-w-none dark:prose-invert">
                  <pre className="whitespace-pre-wrap text-sm font-mono bg-muted p-4 rounded-md overflow-auto max-h-[60vh]">
                    {selectedBriefing.content}
                  </pre>
                </div>
              ) : selectedBriefing ? (
                <p className="text-sm text-muted-foreground">
                  Unable to load briefing content.
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Select a briefing from the list to view its contents.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
