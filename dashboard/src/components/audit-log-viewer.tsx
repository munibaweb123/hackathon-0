"use client";

import { useState, useEffect } from "react";

interface AuditEntry {
  id: string;
  timestamp: string;
  action_type: string;
  actor: string;
  server_id: string;
  result: string;
  approval_ref?: string;
  error_message?: string;
  latency_ms?: number;
}

interface AuditStats {
  active_log_files: number;
  archive_files: number;
  entries_today: number;
  retention_days: number;
}

export function AuditLogViewer() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [chainValid, setChainValid] = useState<boolean | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    try {
      const [entriesRes, statsRes] = await Promise.all([
        fetch("/api/audit?action=export&days=7").catch(() => null),
        fetch("/api/audit?action=stats").catch(() => null),
      ]);

      if (entriesRes?.ok) {
        const data = await entriesRes.json();
        setEntries(Array.isArray(data) ? data : data.entries || []);
      }
      if (statsRes?.ok) {
        setStats(await statsRes.json());
      }
    } catch {
      // API unavailable
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyChain() {
    try {
      const res = await fetch("/api/audit?action=verify");
      if (res.ok) {
        const data = await res.json();
        setChainValid(data.valid);
      }
    } catch {
      setChainValid(false);
    }
  }

  async function handleExport() {
    try {
      const res = await fetch("/api/audit?action=export&days=30&format=jsonl");
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob(
          [data.map((e: AuditEntry) => JSON.stringify(e)).join("\n")],
          { type: "application/jsonl" }
        );
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit-export-${new Date().toISOString().split("T")[0]}.jsonl`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch {
      // Export failed
    }
  }

  const filtered = filter
    ? entries.filter(
        (e) =>
          e.action_type.toLowerCase().includes(filter.toLowerCase()) ||
          e.actor.toLowerCase().includes(filter.toLowerCase()) ||
          e.server_id.toLowerCase().includes(filter.toLowerCase())
      )
    : entries;

  const resultColors: Record<string, string> = {
    success: "bg-green-100 text-green-800",
    failure: "bg-red-100 text-red-800",
    pending: "bg-yellow-100 text-yellow-800",
  };

  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <p className="text-sm text-muted-foreground">Loading audit logs...</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <div className="rounded-lg border bg-card p-4 text-center">
            <p className="text-2xl font-bold">{stats.entries_today}</p>
            <p className="text-xs text-muted-foreground">Entries Today</p>
          </div>
          <div className="rounded-lg border bg-card p-4 text-center">
            <p className="text-2xl font-bold">{stats.active_log_files}</p>
            <p className="text-xs text-muted-foreground">Active Log Files</p>
          </div>
          <div className="rounded-lg border bg-card p-4 text-center">
            <p className="text-2xl font-bold">{stats.archive_files}</p>
            <p className="text-xs text-muted-foreground">Archived Files</p>
          </div>
          <div className="rounded-lg border bg-card p-4 text-center">
            <p className="text-2xl font-bold">{stats.retention_days}d</p>
            <p className="text-xs text-muted-foreground">Retention</p>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Filter by action, actor, server..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 rounded-md border px-3 py-2 text-sm"
        />
        <button
          onClick={handleVerifyChain}
          className="px-3 py-2 text-sm border rounded-md hover:bg-accent"
        >
          Verify Chain
        </button>
        <button
          onClick={handleExport}
          className="px-3 py-2 text-sm border rounded-md hover:bg-accent"
        >
          Export JSONL
        </button>
        {chainValid !== null && (
          <span
            className={`px-2 py-1 rounded-full text-xs font-medium ${
              chainValid
                ? "bg-green-100 text-green-800"
                : "bg-red-100 text-red-800"
            }`}
          >
            {chainValid ? "Chain Valid" : "Chain Broken"}
          </span>
        )}
      </div>

      {/* Entries table */}
      <div className="rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-2 text-left font-medium">Timestamp</th>
              <th className="px-4 py-2 text-left font-medium">Action</th>
              <th className="px-4 py-2 text-left font-medium">Actor</th>
              <th className="px-4 py-2 text-left font-medium">Server</th>
              <th className="px-4 py-2 text-left font-medium">Result</th>
              <th className="px-4 py-2 text-left font-medium">Latency</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  No audit entries found
                </td>
              </tr>
            ) : (
              filtered.slice(0, 100).map((entry, i) => (
                <tr key={entry.id || i} className="border-b">
                  <td className="px-4 py-2 whitespace-nowrap text-xs">
                    {new Date(entry.timestamp).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {entry.action_type}
                  </td>
                  <td className="px-4 py-2 text-xs">{entry.actor}</td>
                  <td className="px-4 py-2 text-xs">{entry.server_id}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        resultColors[entry.result] || ""
                      }`}
                    >
                      {entry.result}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {entry.latency_ms ? `${entry.latency_ms}ms` : "-"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
