import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const CONTACTS_DIR = path.join(
  PROJECT_ROOT,
  "obsidian-vault",
  "contacts",
  "unified"
);

export async function GET(request: NextRequest) {
  const search = request.nextUrl.searchParams.get("search") || "";

  try {
    await fs.mkdir(CONTACTS_DIR, { recursive: true });
    const files = await fs.readdir(CONTACTS_DIR);
    const yamlFiles = files.filter(
      (f) => f.endsWith(".yaml") || f.endsWith(".yml")
    );

    const contacts = [];
    for (const file of yamlFiles) {
      try {
        const content = await fs.readFile(
          path.join(CONTACTS_DIR, file),
          "utf-8"
        );
        // Simple YAML parsing for contact files
        const lines = content.split("\n");
        const contact: Record<string, unknown> = {};
        const identities: Record<string, unknown>[] = [];
        let inIdentities = false;
        let currentIdentity: Record<string, unknown> | null = null;

        for (const line of lines) {
          if (line.startsWith("id:")) contact.id = line.split(": ")[1]?.trim();
          if (line.startsWith("primary_email:"))
            contact.primary_email = line.split(": ")[1]?.trim();
          if (line.startsWith("display_name:"))
            contact.display_name = line.split(": ")[1]?.trim() || null;
          if (line.startsWith("company:"))
            contact.company = line.split(": ")[1]?.trim() || null;
          if (line.startsWith("created_at:"))
            contact.created_at = line.split(": ").slice(1).join(": ").trim();
          if (line.startsWith("identities:")) {
            inIdentities = true;
            continue;
          }
          if (inIdentities) {
            if (line.startsWith("- ") || line.startsWith("  - ")) {
              if (currentIdentity) identities.push(currentIdentity);
              currentIdentity = {};
            }
            if (currentIdentity) {
              const trimmed = line.replace(/^[\s-]+/, "");
              const colonIdx = trimmed.indexOf(":");
              if (colonIdx > 0) {
                const key = trimmed.substring(0, colonIdx).trim();
                const val = trimmed.substring(colonIdx + 1).trim();
                currentIdentity[key] = val === "null" ? null : val;
              }
            }
          }
        }
        if (currentIdentity) identities.push(currentIdentity);
        contact.identities = identities;

        if (contact.primary_email) {
          if (
            !search ||
            String(contact.primary_email).toLowerCase().includes(search.toLowerCase()) ||
            String(contact.display_name || "").toLowerCase().includes(search.toLowerCase()) ||
            String(contact.company || "").toLowerCase().includes(search.toLowerCase())
          ) {
            contacts.push(contact);
          }
        }
      } catch {
        // Skip malformed files
      }
    }

    return NextResponse.json(contacts);
  } catch {
    return NextResponse.json([]);
  }
}
