import { NextResponse } from "next/server";
import { readdir, readFile } from "fs/promises";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");

interface WhatsAppEvent {
  id: string;
  chat_name: string;
  sender: string;
  content: string;
  timestamp: string;
  priority: string;
}

export async function GET() {
  try {
    const inboxPath = path.join(PROJECT_ROOT, "obsidian-vault", "inbox");

    let files: string[];
    try {
      files = await readdir(inboxPath);
    } catch {
      return NextResponse.json([]);
    }

    // Filter for WhatsApp event files
    const waFiles = files.filter((f) => f.startsWith("WHATSAPP_") && f.endsWith(".md"));

    const events: WhatsAppEvent[] = [];

    for (const file of waFiles.slice(0, 20)) {
      try {
        const content = await readFile(path.join(inboxPath, file), "utf-8");

        // Parse YAML frontmatter
        if (content.startsWith("---")) {
          const parts = content.split("---");
          if (parts.length >= 3) {
            // Simple YAML parsing for key fields
            const yaml = parts[1];
            const getId = (key: string) => {
              const match = yaml.match(new RegExp(`${key}:\\s*(.+)`));
              return match ? match[1].trim() : "";
            };

            const rawDataMatch = yaml.match(/raw_data:[\s\S]*?chat_name:\s*(.+)/);
            const chatName = rawDataMatch ? rawDataMatch[1].trim() : "Unknown";

            const senderMatch = yaml.match(/raw_data:[\s\S]*?sender:\s*(.+)/);
            const sender = senderMatch ? senderMatch[1].trim() : chatName;

            const contentMatch = yaml.match(/raw_data:[\s\S]*?content:\s*(.+)/);
            const msgContent = contentMatch ? contentMatch[1].trim() : "";

            events.push({
              id: getId("id"),
              chat_name: chatName,
              sender,
              content: msgContent,
              timestamp: getId("timestamp"),
              priority: getId("priority") || "medium",
            });
          }
        }
      } catch {
        // Skip malformed files
      }
    }

    // Sort by timestamp descending
    events.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );

    return NextResponse.json(events);
  } catch {
    return NextResponse.json([]);
  }
}
