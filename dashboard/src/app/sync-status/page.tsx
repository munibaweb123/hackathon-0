import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { readdir, readFile, stat } from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const VAULT_ROOT = path.join(PROJECT_ROOT, "obsidian-vault");
const SYNC_LOGS_PATH = path.join(VAULT_ROOT, "Logs", "sync");
const SYNC_SIGNALS_PATH = path.join(VAULT_ROOT, "Signals", "sync");
const AGENT_SIGNALS_PATH = path.join(VAULT_ROOT, "Signals", "agents");

interface SyncLogEntry {
  filename: string;
  agent: string;
  timestamp: string;
  status: string;
  files_synced: number;
  conflicts: number;
  duration_ms?: number;
}

interface SyncConflict {
  filename: string;
  file_path: string;
  type: string;
  status: string;
  detected_at: string;
  local_version?: string;
  cloud_version?: string;
}

interface AgentHeartbeat {
  agent_id: string;
  agent_type: string;
  status: string;
  last_heartbeat: string;
  uptime_seconds?: number;
  filename: string;
}

interface DirectoryCount {
  name: string;
  path: string;
  count: number;
}

async function safeReaddir(dir: string): Promise<string[]> {
  try {
    return await readdir(dir);
  } catch {
    return [];
  }
}

function parseYamlFrontmatter(content: string): Record<string, string> {
  if (!content.startsWith("---")) return {};
  const parts = content.split("---");
  if (parts.length < 3) return {};

  const yaml = parts[1];
  const result: Record<string, string> = {};

  for (const line of yaml.split("\n")) {
    const match = line.match(/^(\w[\w_-]*):\s*(.+)$/);
    if (match) {
      result[match[1]] = match[2].trim().replace(/^['"]|['"]$/g, "");
    }
  }
  return result;
}

async function getSyncLogs(): Promise<SyncLogEntry[]> {
  const files = await safeReaddir(SYNC_LOGS_PATH);
  const logs: SyncLogEntry[] = [];

  for (const file of files.filter(
    (f) => f.endsWith(".md") || f.endsWith(".yaml") || f.endsWith(".json")
  )) {
    try {
      const content = await readFile(path.join(SYNC_LOGS_PATH, file), "utf-8");

      if (file.endsWith(".json")) {
        const data = JSON.parse(content);
        logs.push({
          filename: file,
          agent: data.agent || data.agent_id || "unknown",
          timestamp: data.timestamp || data.synced_at || "",
          status: data.status || "unknown",
          files_synced: data.files_synced || data.file_count || 0,
          conflicts: data.conflicts || 0,
          duration_ms: data.duration_ms || data.duration || undefined,
        });
      } else {
        const fm = parseYamlFrontmatter(content);
        logs.push({
          filename: file,
          agent: fm.agent || fm.agent_id || "unknown",
          timestamp: fm.timestamp || fm.synced_at || "",
          status: fm.status || "unknown",
          files_synced: parseInt(fm.files_synced || fm.file_count || "0", 10),
          conflicts: parseInt(fm.conflicts || "0", 10),
          duration_ms: fm.duration_ms
            ? parseInt(fm.duration_ms, 10)
            : undefined,
        });
      }
    } catch {
      // Skip malformed files
    }
  }

  return logs.sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
}

async function getSyncConflicts(): Promise<SyncConflict[]> {
  const files = await safeReaddir(SYNC_SIGNALS_PATH);
  const conflicts: SyncConflict[] = [];

  for (const file of files.filter(
    (f) => f.endsWith(".md") || f.endsWith(".yaml") || f.endsWith(".json")
  )) {
    try {
      const content = await readFile(
        path.join(SYNC_SIGNALS_PATH, file),
        "utf-8"
      );

      if (file.endsWith(".json")) {
        const data = JSON.parse(content);
        conflicts.push({
          filename: file,
          file_path: data.file_path || data.path || file,
          type: data.type || data.conflict_type || "unknown",
          status: data.status || "active",
          detected_at: data.detected_at || data.timestamp || "",
          local_version: data.local_version || undefined,
          cloud_version: data.cloud_version || undefined,
        });
      } else {
        const fm = parseYamlFrontmatter(content);
        conflicts.push({
          filename: file,
          file_path: fm.file_path || fm.path || file,
          type: fm.type || fm.conflict_type || "unknown",
          status: fm.status || "active",
          detected_at: fm.detected_at || fm.timestamp || "",
          local_version: fm.local_version || undefined,
          cloud_version: fm.cloud_version || undefined,
        });
      }
    } catch {
      // Skip malformed files
    }
  }

  return conflicts.sort(
    (a, b) =>
      new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime()
  );
}

async function getAgentHeartbeats(): Promise<AgentHeartbeat[]> {
  const files = await safeReaddir(AGENT_SIGNALS_PATH);
  const heartbeats: AgentHeartbeat[] = [];

  for (const file of files.filter(
    (f) => f.endsWith(".md") || f.endsWith(".yaml") || f.endsWith(".json")
  )) {
    try {
      const content = await readFile(
        path.join(AGENT_SIGNALS_PATH, file),
        "utf-8"
      );

      if (file.endsWith(".json")) {
        const data = JSON.parse(content);
        heartbeats.push({
          agent_id: data.agent_id || data.id || file.replace(/\.json$/, ""),
          agent_type: data.agent_type || data.type || "unknown",
          status: data.status || "unknown",
          last_heartbeat: data.last_heartbeat || data.timestamp || "",
          uptime_seconds: data.uptime_seconds || data.uptime || undefined,
          filename: file,
        });
      } else {
        const fm = parseYamlFrontmatter(content);
        heartbeats.push({
          agent_id: fm.agent_id || fm.id || file.replace(/\.(md|yaml)$/, ""),
          agent_type: fm.agent_type || fm.type || "unknown",
          status: fm.status || "unknown",
          last_heartbeat: fm.last_heartbeat || fm.timestamp || "",
          uptime_seconds: fm.uptime_seconds
            ? parseInt(fm.uptime_seconds, 10)
            : undefined,
          filename: file,
        });
      }
    } catch {
      // Skip malformed files
    }
  }

  return heartbeats;
}

async function getDirectoryCounts(): Promise<DirectoryCount[]> {
  const dirs = [
    { name: "Inbox", path: "inbox" },
    { name: "Processing", path: "processing" },
    { name: "Pending Approval", path: "pending-approval" },
    { name: "Completed", path: "completed" },
    { name: "Approved", path: "Approved" },
    { name: "Rejected", path: "Rejected" },
    { name: "Plans", path: "plans" },
    { name: "Posts", path: "posts" },
    { name: "Drafts", path: "Drafts" },
    { name: "Needs Action", path: "Needs_Action" },
    { name: "Logs", path: "Logs" },
    { name: "Signals", path: "Signals" },
  ];

  const counts: DirectoryCount[] = [];

  for (const dir of dirs) {
    const fullPath = path.join(VAULT_ROOT, dir.path);
    const files = await safeReaddir(fullPath);
    counts.push({
      name: dir.name,
      path: dir.path,
      count: files.length,
    });
  }

  return counts;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

function timeAgo(dateStr: string): string {
  if (!dateStr) return "never";
  const diff = Date.now() - new Date(dateStr).getTime();
  if (diff < 0) return "just now";
  if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}

export default async function SyncStatusPage() {
  const [syncLogs, conflicts, heartbeats, dirCounts] = await Promise.all([
    getSyncLogs(),
    getSyncConflicts(),
    getAgentHeartbeats(),
    getDirectoryCounts(),
  ]);

  const activeConflicts = conflicts.filter((c) => c.status === "active");
  const latestSync = syncLogs.length > 0 ? syncLogs[0] : null;

  const statusVariant = (status: string) =>
    status === "success" || status === "healthy"
      ? "default"
      : status === "active" || status === "warning"
      ? "destructive"
      : ("outline" as const);

  const heartbeatHealth = (hb: AgentHeartbeat) => {
    if (!hb.last_heartbeat) return "unknown";
    const diff = Date.now() - new Date(hb.last_heartbeat).getTime();
    if (diff < 120000) return "healthy";
    if (diff < 300000) return "stale";
    return "dead";
  };

  const healthColors: Record<string, string> = {
    healthy: "bg-green-100 text-green-800",
    stale: "bg-yellow-100 text-yellow-800",
    dead: "bg-red-100 text-red-800",
    unknown: "bg-gray-100 text-gray-800",
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Sync Status</h2>
        <p className="text-muted-foreground">
          Vault synchronization health and agent heartbeats
        </p>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-muted-foreground">
              Last Sync
            </p>
            <p className="text-2xl font-bold">
              {latestSync ? timeAgo(latestSync.timestamp) : "Never"}
            </p>
            {latestSync && (
              <p className="text-xs text-muted-foreground">
                {latestSync.agent} - {latestSync.status}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-muted-foreground">
              Active Conflicts
            </p>
            <p
              className={`text-2xl font-bold ${
                activeConflicts.length > 0 ? "text-red-600" : "text-green-600"
              }`}
            >
              {activeConflicts.length}
            </p>
            <p className="text-xs text-muted-foreground">
              {conflicts.length} total detected
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-muted-foreground">
              Active Agents
            </p>
            <p className="text-2xl font-bold">
              {heartbeats.filter((h) => heartbeatHealth(h) === "healthy").length}
            </p>
            <p className="text-xs text-muted-foreground">
              {heartbeats.length} total registered
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-muted-foreground">
              Sync Logs
            </p>
            <p className="text-2xl font-bold">{syncLogs.length}</p>
            <p className="text-xs text-muted-foreground">recorded sync events</p>
          </CardContent>
        </Card>
      </div>

      {/* File Counts per Directory */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Vault Directory Counts</CardTitle>
        </CardHeader>
        <CardContent>
          {dirCounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No vault directories found.
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {dirCounts.map((dir) => (
                <div
                  key={dir.path}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <span className="text-sm font-medium">{dir.name}</span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-sm font-bold">
                    {dir.count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Agent Heartbeats */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            Agent Heartbeats ({heartbeats.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {heartbeats.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No agent heartbeats found. Agents report their status to
              Signals/agents/.
            </p>
          ) : (
            <div className="space-y-3">
              {heartbeats.map((hb) => {
                const health = heartbeatHealth(hb);
                return (
                  <div
                    key={hb.filename}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div>
                      <p className="font-medium">{hb.agent_id}</p>
                      <p className="text-xs text-muted-foreground">
                        {hb.agent_type}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      {hb.uptime_seconds !== undefined && (
                        <span className="text-xs text-muted-foreground">
                          Uptime: {formatUptime(hb.uptime_seconds)}
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground">
                        {timeAgo(hb.last_heartbeat)}
                      </span>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${healthColors[health]}`}
                      >
                        {health}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Active Conflicts */}
      {activeConflicts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Active Conflicts ({activeConflicts.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeConflicts.map((conflict) => (
              <div
                key={conflict.filename}
                className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950"
              >
                <div className="flex items-center justify-between">
                  <p className="font-medium">{conflict.file_path}</p>
                  <Badge variant="destructive">{conflict.type}</Badge>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Detected: {timeAgo(conflict.detected_at)}</span>
                  {conflict.local_version && (
                    <span>Local: {conflict.local_version}</span>
                  )}
                  {conflict.cloud_version && (
                    <span>Cloud: {conflict.cloud_version}</span>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Recent Sync Logs */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Sync Logs</CardTitle>
        </CardHeader>
        <CardContent>
          {syncLogs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No sync logs found. Sync events are recorded in Logs/sync/.
            </p>
          ) : (
            <div className="space-y-2">
              {syncLogs.slice(0, 20).map((log) => (
                <div
                  key={log.filename}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant={statusVariant(log.status)}>
                      {log.status}
                    </Badge>
                    <span className="text-sm font-medium">{log.agent}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>{log.files_synced} files</span>
                    {log.conflicts > 0 && (
                      <span className="text-red-600">
                        {log.conflicts} conflicts
                      </span>
                    )}
                    {log.duration_ms !== undefined && (
                      <span>{formatDuration(log.duration_ms)}</span>
                    )}
                    <span>{timeAgo(log.timestamp)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
