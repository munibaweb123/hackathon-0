/**
 * Approval Handler — HITL (Human-in-the-Loop) file-based approval for social posts.
 *
 * Creates approval request files in pending-approval/ with YAML frontmatter.
 * Humans approve by moving the file to Approved/, or reject by moving to Rejected/.
 * Matches the pattern from agent-skills/core/approval_generator.py.
 */

import fs from "fs";
import path from "path";
import crypto from "crypto";

export class ApprovalHandler {
  /**
   * @param {object} options
   * @param {string} [options.vaultPath] — Path to the Obsidian vault
   */
  constructor({ vaultPath } = {}) {
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";

    this.pendingDir = path.join(this.vaultPath, "pending-approval");
    this.approvedDir = path.join(this.vaultPath, "Approved");
    this.rejectedDir = path.join(this.vaultPath, "Rejected");

    // Ensure directories exist
    for (const dir of [this.pendingDir, this.approvedDir, this.rejectedDir]) {
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    }
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Create an approval request file for a social media post.
   *
   * @param {object} data
   * @param {string} data.platform      — "facebook" | "instagram" | "twitter"
   * @param {string} data.action        — "post" | "tweet" etc.
   * @param {string} data.content       — The post text / caption / tweet
   * @param {string} [data.imageFile]   — Attachment filename from vault
   * @param {string} [data.link]        — URL to include (Facebook)
   * @param {object} [data.metadata]    — Extra metadata to embed
   * @returns {{ approvalId: string, filename: string, filePath: string }}
   */
  createApprovalRequest(data) {
    const approvalId = this._generateId();
    const platformSlug = data.platform.toLowerCase().replace(/[^a-z0-9]/g, "_");
    const filename = `APPROVAL_REQUIRED_${platformSlug}_${approvalId}.md`;
    const filePath = path.join(this.pendingDir, filename);

    const markdown = this._buildMarkdown({ ...data, id: approvalId });
    fs.writeFileSync(filePath, markdown, "utf-8");

    return { approvalId, filename, filePath };
  }

  /**
   * Check if an approval request has been approved, rejected, or is still pending.
   *
   * @param {string} approvalId — The 8-char approval ID
   * @returns {{ status: "pending"|"approved"|"rejected"|"not_found", filePath?: string, metadata?: object }}
   */
  checkApproval(approvalId) {
    // Search Approved/ folder
    const approvedFile = this._findFileById(this.approvedDir, approvalId);
    if (approvedFile) {
      return {
        status: "approved",
        filePath: approvedFile,
        metadata: this._parseMetadata(approvedFile),
      };
    }

    // Search Rejected/ folder
    const rejectedFile = this._findFileById(this.rejectedDir, approvalId);
    if (rejectedFile) {
      return {
        status: "rejected",
        filePath: rejectedFile,
        metadata: this._parseMetadata(rejectedFile),
      };
    }

    // Search pending-approval/ folder
    const pendingFile = this._findFileById(this.pendingDir, approvalId);
    if (pendingFile) {
      return {
        status: "pending",
        filePath: pendingFile,
        metadata: this._parseMetadata(pendingFile),
      };
    }

    return { status: "not_found" };
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  _generateId() {
    return crypto.randomBytes(4).toString("hex");
  }

  _findFileById(dir, approvalId) {
    if (!fs.existsSync(dir)) return null;
    const files = fs.readdirSync(dir);
    const match = files.find(
      (f) => f.includes(approvalId) && f.startsWith("APPROVAL_REQUIRED_")
    );
    return match ? path.join(dir, match) : null;
  }

  _parseMetadata(filePath) {
    try {
      const content = fs.readFileSync(filePath, "utf-8");
      const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);
      if (!fmMatch) return {};

      const metadata = {};
      for (const line of fmMatch[1].split("\n")) {
        const colonIdx = line.indexOf(":");
        if (colonIdx > 0) {
          const key = line.slice(0, colonIdx).trim();
          const value = line.slice(colonIdx + 1).trim();
          metadata[key] = value;
        }
      }
      return metadata;
    } catch {
      return {};
    }
  }

  _buildMarkdown(data) {
    const now = new Date();
    const expires = new Date(now.getTime() + 24 * 60 * 60 * 1000);

    const platformName = {
      facebook: "Facebook",
      instagram: "Instagram",
      twitter: "Twitter/X",
    }[data.platform] || data.platform;

    const charLimits = {
      facebook: 63206,
      instagram: 2200,
      twitter: 280,
    };

    const contentLength = (data.content || "").length;
    const limit = charLimits[data.platform] || 0;
    const withinLimit = limit === 0 || contentLength <= limit;

    let md = "";
    md += "---\n";
    md += `id: ${data.id}\n`;
    md += `type: approval_request\n`;
    md += `action_type: social_post\n`;
    md += `platform: ${data.platform}\n`;
    md += `action: ${data.action || "post"}\n`;
    md += `created: ${now.toISOString()}\n`;
    md += `expires: ${expires.toISOString()}\n`;
    md += `risk_level: medium\n`;
    md += `status: pending\n`;
    md += "---\n\n";

    md += `# Approval Required: ${platformName} Post\n\n`;
    md += `**Platform:** ${platformName}\n`;
    md += `**Action:** Create post\n`;
    md += `**Created:** ${now.toISOString()}\n`;
    md += `**Expires:** ${expires.toISOString()} (24 hours)\n`;
    md += `**Risk Level:** 🟡 Medium\n\n`;

    md += `## Proposed Content\n\n`;
    md += "```\n";
    md += `${data.content || "(empty)"}\n`;
    md += "```\n\n";

    md += `**Character count:** ${contentLength}`;
    if (limit > 0) {
      md += ` / ${limit} ${withinLimit ? "✅" : "❌ OVER LIMIT"}`;
    }
    md += "\n\n";

    if (data.link) {
      md += `**Link:** ${data.link}\n\n`;
    }

    if (data.imageFile) {
      md += `**Image:** ${data.imageFile}\n\n`;
    }

    if (data.metadata && Object.keys(data.metadata).length > 0) {
      md += `## Metadata\n\n`;
      for (const [key, value] of Object.entries(data.metadata)) {
        md += `- **${key}:** ${value}\n`;
      }
      md += "\n";
    }

    md += `## Decision\n\n`;
    md += `To **approve** this post:\n`;
    md += `→ Move this file to the \`Approved/\` folder\n\n`;
    md += `To **reject** this post:\n`;
    md += `→ Move this file to the \`Rejected/\` folder\n`;

    return md;
  }
}
