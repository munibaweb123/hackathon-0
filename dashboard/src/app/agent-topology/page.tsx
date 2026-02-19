import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { readdir, readFile } from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const VAULT_ROOT = path.join(PROJECT_ROOT, "obsidian-vault");
const AGENT_SIGNALS_PATH = path.join(VAULT_ROOT, "Signals", "agents");
const TOPOLOGY_PATH = path.join(VAULT_ROOT, "topology.yaml");

interface AgentInfo {
  agent_id: string;
  agent_type: string;
  location: string;
  status: string;
  capabilities: string[];
  last_heartbeat: string;
  uptime_seconds?: number;
  version?: string;
  pid?: string;
  host?: string;
  error_message?: string;
  filename: string;
}

interface TopologyNode {
  id: string;
  type: string;
  location: string;
  connects_to: string[];
  description?: string;
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

function parseYamlList(content: string, key: string): string[] {
  // Match a YAML key followed by list items (- item)
  const regex = new RegExp(`^${key}:\\s*\\n((?:\\s+-\\s+.+\\n?)*)`, "m");
  const match = content.match(regex);
  if (!match) {
    // Try inline array format: key: [item1, item2]
    const inlineMatch = content.match(
      new RegExp(`^${key}:\\s*\\[([^\\]]+)\\]`, "m")
    );
    if (inlineMatch) {
      return inlineMatch[1]
        .split(",")
        .map((s) => s.trim().replace(/^['"]|['"]$/g, ""));
    }
    return [];
  }

  return match[1]
    .split("\n")
    .filter((line) => line.trim().startsWith("-"))
    .map((line) =>
      line
        .trim()
        .replace(/^-\s*/, "")
        .replace(/^['"]|['"]$/g, "")
    );
}

async function getAgents(): Promise<AgentInfo[]> {
  const files = await safeReaddir(AGENT_SIGNALS_PATH);
  const agents: AgentInfo[] = [];

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
        agents.push({
          agent_id: data.agent_id || data.id || file.replace(/\.json$/, ""),
          agent_type: data.agent_type || data.type || "unknown",
          location: data.location || "unknown",
          status: data.status || "unknown",
          capabilities: Array.isArray(data.capabilities)
            ? data.capabilities
            : [],
          last_heartbeat: data.last_heartbeat || data.timestamp || "",
          uptime_seconds: data.uptime_seconds || data.uptime || undefined,
          version: data.version || undefined,
          pid: data.pid ? String(data.pid) : undefined,
          host: data.host || data.hostname || undefined,
          error_message: data.error_message || data.error || undefined,
          filename: file,
        });
      } else {
        // YAML or Markdown with frontmatter
        const fm = parseYamlFrontmatter(content);
        const capabilities = parseYamlList(
          content.startsWith("---")
            ? content.split("---")[1] || ""
            : content,
          "capabilities"
        );

        agents.push({
          agent_id:
            fm.agent_id || fm.id || file.replace(/\.(md|yaml)$/, ""),
          agent_type: fm.agent_type || fm.type || "unknown",
          location: fm.location || "unknown",
          status: fm.status || "unknown",
          capabilities,
          last_heartbeat: fm.last_heartbeat || fm.timestamp || "",
          uptime_seconds: fm.uptime_seconds
            ? parseInt(fm.uptime_seconds, 10)
            : undefined,
          version: fm.version || undefined,
          pid: fm.pid || undefined,
          host: fm.host || fm.hostname || undefined,
          error_message: fm.error_message || fm.error || undefined,
          filename: file,
        });
      }
    } catch {
      // Skip malformed files
    }
  }

  return agents;
}

async function getTopology(): Promise<TopologyNode[]> {
  try {
    const content = await readFile(TOPOLOGY_PATH, "utf-8");
    const nodes: TopologyNode[] = [];

    // Parse simple YAML topology file
    // Expected format: list of nodes with id, type, location, connects_to
    const nodeBlocks = content.split(/^-\s/m).filter(Boolean);

    for (const block of nodeBlocks) {
      const lines = block.split("\n");
      const node: Record<string, string> = {};
      const connectsTo: string[] = [];
      let inConnectsTo = false;

      for (const line of lines) {
        if (line.trim().startsWith("connects_to:")) {
          inConnectsTo = true;
          // Check for inline array
          const inlineMatch = line.match(/connects_to:\s*\[([^\]]*)\]/);
          if (inlineMatch) {
            connectsTo.push(
              ...inlineMatch[1]
                .split(",")
                .map((s) => s.trim().replace(/^['"]|['"]$/g, ""))
                .filter(Boolean)
            );
            inConnectsTo = false;
          }
          continue;
        }

        if (inConnectsTo && line.trim().startsWith("-")) {
          connectsTo.push(
            line
              .trim()
              .replace(/^-\s*/, "")
              .replace(/^['"]|['"]$/g, "")
          );
          continue;
        }

        if (inConnectsTo && !line.trim().startsWith("-")) {
          inConnectsTo = false;
        }

        const kvMatch = line.match(/^\s*(\w[\w_-]*):\s*(.+)$/);
        if (kvMatch) {
          node[kvMatch[1]] = kvMatch[2].trim().replace(/^['"]|['"]$/g, "");
        }
      }

      if (node.id || node.type) {
        nodes.push({
          id: node.id || "unknown",
          type: node.type || "unknown",
          location: node.location || "unknown",
          connects_to: connectsTo,
          description: node.description || undefined,
        });
      }
    }

    return nodes;
  } catch {
    return [];
  }
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

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours < 24) return `${hours}h ${mins}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

function heartbeatHealth(lastHeartbeat: string): string {
  if (!lastHeartbeat) return "unknown";
  const diff = Date.now() - new Date(lastHeartbeat).getTime();
  if (diff < 120000) return "healthy";
  if (diff < 300000) return "stale";
  return "dead";
}

export default async function AgentTopologyPage() {
  const [agents, topology] = await Promise.all([
    getAgents(),
    getTopology(),
  ]);

  const healthColors: Record<string, string> = {
    healthy: "bg-green-100 text-green-800",
    stale: "bg-yellow-100 text-yellow-800",
    dead: "bg-red-100 text-red-800",
    unknown: "bg-gray-100 text-gray-800",
  };

  const locationColors: Record<string, string> = {
    cloud: "bg-sky-100 text-sky-800",
    local: "bg-indigo-100 text-indigo-800",
    unknown: "bg-gray-100 text-gray-800",
  };

  const statusVariant = (status: string) =>
    status === "running" || status === "active" || status === "healthy"
      ? "default"
      : status === "error" || status === "crashed"
      ? "destructive"
      : ("outline" as const);

  // Group agents by location
  const cloudAgents = agents.filter(
    (a) => a.location === "cloud" || a.location === "remote"
  );
  const localAgents = agents.filter(
    (a) => a.location === "local" || a.location === "on-premise"
  );
  const otherAgents = agents.filter(
    (a) =>
      a.location !== "cloud" &&
      a.location !== "remote" &&
      a.location !== "local" &&
      a.location !== "on-premise"
  );

  const healthyCount = agents.filter(
    (a) => heartbeatHealth(a.last_heartbeat) === "healthy"
  ).length;
  const staleCount = agents.filter(
    (a) => heartbeatHealth(a.last_heartbeat) === "stale"
  ).length;
  const deadCount = agents.filter(
    (a) => heartbeatHealth(a.last_heartbeat) === "dead"
  ).length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Agent Topology</h2>
        <p className="text-muted-foreground">
          Cloud and local agent status, capabilities, and connections
        </p>
      </div>

      {/* Health Summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-muted-foreground">
              Total Agents
            </p>
            <p className="text-2xl font-bold">{agents.length}</p>
            <p className="text-xs text-muted-foreground">
              {cloudAgents.length} cloud, {localAgents.length} local
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-muted-foreground">Healthy</p>
            <p className="text-2xl font-bold text-green-600">{healthyCount}</p>
            <p className="text-xs text-muted-foreground">
              heartbeat within 2 minutes
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-muted-foreground">Stale</p>
            <p className="text-2xl font-bold text-yellow-600">{staleCount}</p>
            <p className="text-xs text-muted-foreground">
              heartbeat 2-5 minutes ago
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-muted-foreground">Dead</p>
            <p
              className={`text-2xl font-bold ${
                deadCount > 0 ? "text-red-600" : "text-green-600"
              }`}
            >
              {deadCount}
            </p>
            <p className="text-xs text-muted-foreground">
              no heartbeat for 5+ minutes
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Topology Map */}
      {topology.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Topology Map</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {topology.map((node) => (
                <div
                  key={node.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        locationColors[node.location] ||
                        locationColors.unknown
                      }`}
                    >
                      {node.location}
                    </span>
                    <div>
                      <p className="font-medium">{node.id}</p>
                      <p className="text-xs text-muted-foreground">
                        {node.type}
                        {node.description ? ` - ${node.description}` : ""}
                      </p>
                    </div>
                  </div>
                  {node.connects_to.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {node.connects_to.map((target) => (
                        <Badge key={target} variant="outline">
                          {target}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Cloud Agents */}
      {cloudAgents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Cloud Agents ({cloudAgents.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {cloudAgents.map((agent) => (
              <AgentCard
                key={agent.filename}
                agent={agent}
                healthColors={healthColors}
                statusVariant={statusVariant}
              />
            ))}
          </CardContent>
        </Card>
      )}

      {/* Local Agents */}
      {localAgents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Local Agents ({localAgents.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {localAgents.map((agent) => (
              <AgentCard
                key={agent.filename}
                agent={agent}
                healthColors={healthColors}
                statusVariant={statusVariant}
              />
            ))}
          </CardContent>
        </Card>
      )}

      {/* Other / Unclassified Agents */}
      {otherAgents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              Other Agents ({otherAgents.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {otherAgents.map((agent) => (
              <AgentCard
                key={agent.filename}
                agent={agent}
                healthColors={healthColors}
                statusVariant={statusVariant}
              />
            ))}
          </CardContent>
        </Card>
      )}

      {/* No agents state */}
      {agents.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No agents detected. Agent heartbeats are read from
            Signals/agents/ YAML files and topology from topology.yaml.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function AgentCard({
  agent,
  healthColors,
  statusVariant,
}: {
  agent: AgentInfo;
  healthColors: Record<string, string>;
  statusVariant: (status: string) => "default" | "destructive" | "outline";
}) {
  const health = heartbeatHealth(agent.last_heartbeat);

  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <p className="font-medium">{agent.agent_id}</p>
            <p className="text-xs text-muted-foreground">{agent.agent_type}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant(agent.status)}>{agent.status}</Badge>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${healthColors[health]}`}
          >
            {health}
          </span>
        </div>
      </div>

      {/* Capabilities */}
      {agent.capabilities.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-muted-foreground mb-1">
            Capabilities
          </p>
          <div className="flex flex-wrap gap-1">
            {agent.capabilities.map((cap) => (
              <Badge key={cap} variant="outline" className="text-xs">
                {cap}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Metadata row */}
      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span>Heartbeat: {timeAgo(agent.last_heartbeat)}</span>
        {agent.uptime_seconds !== undefined && (
          <span>Uptime: {formatUptime(agent.uptime_seconds)}</span>
        )}
        {agent.version && <span>v{agent.version}</span>}
        {agent.host && <span>Host: {agent.host}</span>}
        {agent.pid && <span>PID: {agent.pid}</span>}
      </div>

      {/* Error message */}
      {agent.error_message && (
        <div className="mt-2 rounded bg-red-50 p-2 text-xs text-red-700 dark:bg-red-950 dark:text-red-300">
          {agent.error_message}
        </div>
      )}
    </div>
  );
}
