import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { readdir, readFile } from "fs/promises";
import path from "path";
import { DraftActions } from "./draft-actions";

export const dynamic = "force-dynamic";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const DRAFTS_PATH = path.join(PROJECT_ROOT, "obsidian-vault", "Drafts");

type DraftType = "email" | "social" | "payment" | "briefing";

interface Draft {
  id: string;
  title: string;
  type: DraftType;
  priority: string;
  status: string;
  created: string;
  expires: string;
  recipient?: string;
  summary?: string;
  filename: string;
  subdir: string;
}

const DRAFT_SUBDIRS: { dir: string; type: DraftType }[] = [
  { dir: "email", type: "email" },
  { dir: "social", type: "social" },
  { dir: "payment", type: "payment" },
  { dir: "briefing", type: "briefing" },
];

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

async function getDrafts(): Promise<Draft[]> {
  const drafts: Draft[] = [];

  for (const { dir, type } of DRAFT_SUBDIRS) {
    const dirPath = path.join(DRAFTS_PATH, dir);
    const files = await safeReaddir(dirPath);

    for (const file of files.filter((f) => f.endsWith(".md"))) {
      try {
        const content = await readFile(path.join(dirPath, file), "utf-8");
        const fm = parseYamlFrontmatter(content);

        // Extract summary from body
        const bodyParts = content.split("---");
        const body = bodyParts.length >= 3 ? bodyParts.slice(2).join("---").trim() : "";
        const summaryMatch = body.match(/^(.{0,200})/s);

        drafts.push({
          id: fm.id || file.replace(/\.md$/, ""),
          title: fm.title || file.replace(/\.md$/, "").replace(/[-_]/g, " "),
          type,
          priority: fm.priority || "medium",
          status: fm.status || "pending",
          created: fm.created || fm.created_at || "",
          expires: fm.expires || fm.expires_at || "",
          recipient: fm.recipient || fm.to || undefined,
          summary: summaryMatch ? summaryMatch[1].slice(0, 150) : undefined,
          filename: file,
          subdir: dir,
        });
      } catch {
        // Skip malformed files
      }
    }
  }

  return drafts.sort(
    (a, b) => new Date(b.created).getTime() - new Date(a.created).getTime()
  );
}

const typeColors: Record<DraftType, string> = {
  email: "bg-blue-100 text-blue-800",
  social: "bg-purple-100 text-purple-800",
  payment: "bg-green-100 text-green-800",
  briefing: "bg-amber-100 text-amber-800",
};

export default async function DraftsPage() {
  const drafts = await getDrafts();

  const priorityVariant = (priority: string) =>
    priority === "urgent" || priority === "high"
      ? "destructive"
      : priority === "medium"
      ? "default"
      : ("secondary" as const);

  // Group by type
  const grouped = DRAFT_SUBDIRS.reduce(
    (acc, { type }) => {
      acc[type] = drafts.filter((d) => d.type === type);
      return acc;
    },
    {} as Record<DraftType, Draft[]>
  );

  const totalCount = drafts.length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Pending Drafts</h2>
        <p className="text-muted-foreground">
          Review and approve AI-generated drafts ({totalCount})
        </p>
      </div>

      {/* Type summary badges */}
      <div className="flex flex-wrap gap-2">
        {DRAFT_SUBDIRS.map(({ type }) => (
          <span
            key={type}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${typeColors[type]}`}
          >
            {type.charAt(0).toUpperCase() + type.slice(1)}
            <span className="ml-1 rounded-full bg-white/60 px-1.5 py-0.5 text-xs">
              {grouped[type]?.length || 0}
            </span>
          </span>
        ))}
      </div>

      {totalCount === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No pending drafts. Drafts are created when the AI generates emails,
            social posts, payment requests, or briefings for review.
          </CardContent>
        </Card>
      ) : (
        DRAFT_SUBDIRS.map(({ type }) => {
          const typeDrafts = grouped[type];
          if (!typeDrafts || typeDrafts.length === 0) return null;

          return (
            <div key={type} className="space-y-4">
              <h3 className="text-lg font-semibold capitalize">{type} Drafts</h3>
              {typeDrafts.map((draft) => (
                <Card key={`${draft.subdir}-${draft.filename}`}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{draft.title}</CardTitle>
                      <div className="flex gap-2">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${typeColors[draft.type]}`}
                        >
                          {draft.type}
                        </span>
                        <Badge variant={priorityVariant(draft.priority)}>
                          {draft.priority}
                        </Badge>
                        <Badge variant="outline">{draft.status}</Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {draft.recipient && (
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          Recipient
                        </p>
                        <p className="text-sm">{draft.recipient}</p>
                      </div>
                    )}
                    {draft.summary && (
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          Preview
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {draft.summary}...
                        </p>
                      </div>
                    )}
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        ID: {draft.id.length > 8 ? draft.id.slice(0, 8) : draft.id}
                      </span>
                      <span>
                        Created:{" "}
                        {draft.created
                          ? new Date(draft.created).toLocaleString()
                          : "Unknown"}
                      </span>
                      {draft.expires && (
                        <span>
                          Expires: {new Date(draft.expires).toLocaleString()}
                        </span>
                      )}
                    </div>

                    <DraftActions
                      draftId={draft.id}
                      draftType={draft.type}
                      filename={draft.filename}
                      subdir={draft.subdir}
                    />
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
