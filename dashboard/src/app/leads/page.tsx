import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { readdir, readFile } from "fs/promises";
import path from "path";
import { LeadActions } from "./lead-actions";

export const dynamic = "force-dynamic";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const LEADS_PATH = path.join(
  PROJECT_ROOT,
  "obsidian-vault",
  "Needs_Action",
  "cloud",
  "leads"
);

type LeadStatus = "new" | "reviewed" | "contacted" | "qualified" | "closed";
type LeadPriority = "low" | "medium" | "high" | "urgent";

interface Lead {
  id: string;
  company: string;
  contact_name: string;
  contact_email?: string;
  request_type: string;
  priority: LeadPriority;
  status: LeadStatus;
  source?: string;
  created: string;
  notes?: string;
  filename: string;
}

const STATUS_ORDER: LeadStatus[] = [
  "new",
  "reviewed",
  "contacted",
  "qualified",
  "closed",
];

const NEXT_STATUS: Record<LeadStatus, LeadStatus | null> = {
  new: "reviewed",
  reviewed: "contacted",
  contacted: "qualified",
  qualified: "closed",
  closed: null,
};

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

async function getLeads(): Promise<Lead[]> {
  const files = await safeReaddir(LEADS_PATH);
  const leads: Lead[] = [];

  for (const file of files.filter((f) => f.endsWith(".md") || f.endsWith(".yaml"))) {
    try {
      const content = await readFile(path.join(LEADS_PATH, file), "utf-8");
      const fm = parseYamlFrontmatter(content);

      // Extract notes from body
      const bodyParts = content.split("---");
      const body =
        bodyParts.length >= 3 ? bodyParts.slice(2).join("---").trim() : "";
      const notesPreview = body.slice(0, 200) || undefined;

      leads.push({
        id: fm.id || file.replace(/\.(md|yaml)$/, ""),
        company: fm.company || "Unknown",
        contact_name: fm.contact_name || fm.contact || fm.name || "Unknown",
        contact_email: fm.contact_email || fm.email || undefined,
        request_type: fm.request_type || fm.type || "general",
        priority: (fm.priority as LeadPriority) || "medium",
        status: (fm.status as LeadStatus) || "new",
        source: fm.source || undefined,
        created: fm.created || fm.created_at || "",
        notes: notesPreview,
        filename: file,
      });
    } catch {
      // Skip malformed files
    }
  }

  // Sort by priority (urgent first), then by date
  const priorityWeight: Record<string, number> = {
    urgent: 0,
    high: 1,
    medium: 2,
    low: 3,
  };

  return leads.sort((a, b) => {
    const pw = (priorityWeight[a.priority] ?? 2) - (priorityWeight[b.priority] ?? 2);
    if (pw !== 0) return pw;
    return new Date(b.created).getTime() - new Date(a.created).getTime();
  });
}

export default async function LeadsPage() {
  const leads = await getLeads();

  const priorityVariant = (priority: string) =>
    priority === "urgent" || priority === "high"
      ? "destructive"
      : priority === "medium"
      ? "default"
      : ("secondary" as const);

  const statusColors: Record<LeadStatus, string> = {
    new: "bg-blue-100 text-blue-800",
    reviewed: "bg-yellow-100 text-yellow-800",
    contacted: "bg-purple-100 text-purple-800",
    qualified: "bg-green-100 text-green-800",
    closed: "bg-gray-100 text-gray-800",
  };

  // Group by status
  const grouped = STATUS_ORDER.reduce(
    (acc, status) => {
      acc[status] = leads.filter((l) => l.status === status);
      return acc;
    },
    {} as Record<LeadStatus, Lead[]>
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Leads</h2>
        <p className="text-muted-foreground">
          Track and manage incoming leads ({leads.length})
        </p>
      </div>

      {/* Status pipeline summary */}
      <div className="flex flex-wrap gap-2">
        {STATUS_ORDER.map((status) => (
          <span
            key={status}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${statusColors[status]}`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
            <span className="ml-1 rounded-full bg-white/60 px-1.5 py-0.5 text-xs">
              {grouped[status]?.length || 0}
            </span>
          </span>
        ))}
      </div>

      {leads.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No leads found. Leads appear when the AI detects potential
            opportunities from incoming communications.
          </CardContent>
        </Card>
      ) : (
        STATUS_ORDER.map((status) => {
          const statusLeads = grouped[status];
          if (!statusLeads || statusLeads.length === 0) return null;

          return (
            <div key={status} className="space-y-4">
              <h3 className="text-lg font-semibold capitalize">
                {status} ({statusLeads.length})
              </h3>
              {statusLeads.map((lead) => (
                <Card key={lead.filename}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{lead.company}</CardTitle>
                      <div className="flex gap-2">
                        <Badge variant={priorityVariant(lead.priority)}>
                          {lead.priority}
                        </Badge>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[lead.status]}`}
                        >
                          {lead.status}
                        </span>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          Contact
                        </p>
                        <p className="text-sm">{lead.contact_name}</p>
                        {lead.contact_email && (
                          <p className="text-xs text-muted-foreground">
                            {lead.contact_email}
                          </p>
                        )}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          Request Type
                        </p>
                        <Badge variant="outline">{lead.request_type}</Badge>
                      </div>
                    </div>

                    {lead.source && (
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          Source
                        </p>
                        <p className="text-sm">{lead.source}</p>
                      </div>
                    )}

                    {lead.notes && (
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          Notes
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {lead.notes}...
                        </p>
                      </div>
                    )}

                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        ID:{" "}
                        {lead.id.length > 8 ? lead.id.slice(0, 8) : lead.id}
                      </span>
                      <span>
                        Created:{" "}
                        {lead.created
                          ? new Date(lead.created).toLocaleString()
                          : "Unknown"}
                      </span>
                    </div>

                    {NEXT_STATUS[lead.status] && (
                      <LeadActions
                        leadId={lead.id}
                        filename={lead.filename}
                        currentStatus={lead.status}
                        nextStatus={NEXT_STATUS[lead.status]!}
                      />
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          );
        })
      )}
    </div>
  );
}
