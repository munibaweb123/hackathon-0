/**
 * Payment Approval Validator — extends the base ApprovalHandler with
 * payment-specific security controls, fraud flag embedding, and 24h hard expiry.
 *
 * Uses composition (wraps ApprovalHandler) rather than inheritance.
 * Never stores payment credentials — only references method names.
 */

import fs from "fs";
import path from "path";
import crypto from "crypto";
import { ApprovalHandler } from "../social-poster-mcp/approval_handler.js";

const EXPIRY_HOURS = 24;

export class PaymentApprovalValidator {
  /**
   * @param {object} options
   * @param {string} [options.vaultPath]
   */
  constructor({ vaultPath } = {}) {
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";
    this.approvalHandler = new ApprovalHandler({ vaultPath: this.vaultPath });

    this.pendingDir = path.join(this.vaultPath, "pending-approval");
    this.approvedDir = path.join(this.vaultPath, "Approved");
    this.rejectedDir = path.join(this.vaultPath, "Rejected");
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Create a payment-specific approval request with fraud analysis embedded.
   *
   * @param {object} data
   * @param {string} data.recipient     — Payee name
   * @param {number} data.amount        — Payment amount
   * @param {string} data.method        — Payment method (bank_transfer|paypal|stripe)
   * @param {string} [data.reference]   — Invoice/reference number
   * @param {string} [data.category]    — Payment category
   * @param {string} [data.currency]    — Currency code
   * @param {string[]} [data.fraudFlags] — Flags from FraudDetector
   * @param {number} [data.riskScore]   — Risk score (0-100)
   * @param {object} [data.fraudDetails] — Detailed flag descriptions
   * @returns {{ approvalId, filename, filePath, riskLevel, fraudFlags }}
   */
  createPaymentApproval(data) {
    const approvalId = crypto.randomBytes(4).toString("hex");
    const filename = `APPROVAL_REQUIRED_payment_${approvalId}.md`;
    const filePath = path.join(this.pendingDir, filename);

    const riskLevel = this._determineRiskLevel(data);
    const markdown = this._buildPaymentMarkdown({ ...data, id: approvalId, riskLevel });

    // Ensure directory exists
    if (!fs.existsSync(this.pendingDir)) {
      fs.mkdirSync(this.pendingDir, { recursive: true });
    }

    fs.writeFileSync(filePath, markdown, "utf-8");

    return {
      approvalId,
      filename,
      filePath,
      riskLevel,
      fraudFlags: data.fraudFlags || [],
    };
  }

  /**
   * Check payment approval status with 24h hard expiry enforcement.
   *
   * @param {string} approvalId
   * @returns {{ status: "pending"|"approved"|"rejected"|"expired"|"not_found", metadata? }}
   */
  checkPaymentApproval(approvalId) {
    const baseResult = this.approvalHandler.checkApproval(approvalId);

    if (baseResult.status === "not_found") {
      return baseResult;
    }

    // Enforce 24h hard expiry for pending approvals
    if (baseResult.status === "pending" && baseResult.metadata?.created) {
      const created = new Date(baseResult.metadata.created).getTime();
      const expiresAt = created + EXPIRY_HOURS * 60 * 60 * 1000;

      if (Date.now() > expiresAt) {
        // Auto-expire: move to Rejected/
        this._expireApproval(approvalId, baseResult.filePath);
        return {
          status: "expired",
          metadata: baseResult.metadata,
          message: `Payment approval expired after ${EXPIRY_HOURS} hours`,
        };
      }

      // Add time remaining
      const remainingMs = expiresAt - Date.now();
      const remainingHours = Math.floor(remainingMs / (60 * 60 * 1000));
      const remainingMins = Math.floor(
        (remainingMs % (60 * 60 * 1000)) / (60 * 1000)
      );

      return {
        ...baseResult,
        expiresIn: `${remainingHours}h ${remainingMins}m`,
      };
    }

    return baseResult;
  }

  /**
   * Cancel a pending payment approval (moves to Rejected/).
   *
   * @param {string} approvalId
   * @returns {{ cancelled: boolean, message: string }}
   */
  cancelApproval(approvalId) {
    const file = this._findPendingFile(approvalId);

    if (!file) {
      // Check if it was already approved or rejected
      const status = this.approvalHandler.checkApproval(approvalId);
      if (status.status === "approved") {
        return {
          cancelled: false,
          message: "Cannot cancel — payment already approved",
        };
      }
      if (status.status === "rejected") {
        return {
          cancelled: false,
          message: "Payment was already rejected",
        };
      }
      return { cancelled: false, message: "Approval request not found" };
    }

    // Move to Rejected/ with cancellation annotation
    const destPath = path.join(this.rejectedDir, path.basename(file));

    if (!fs.existsSync(this.rejectedDir)) {
      fs.mkdirSync(this.rejectedDir, { recursive: true });
    }

    // Append cancellation note to the file
    let content = fs.readFileSync(file, "utf-8");
    content +=
      `\n\n---\n**Cancelled** by system at ${new Date().toISOString()}\n`;
    fs.writeFileSync(file, content, "utf-8");

    // Move file
    fs.renameSync(file, destPath);

    return {
      cancelled: true,
      message: "Payment approval cancelled and moved to Rejected/",
    };
  }

  /**
   * List all pending payment approvals.
   *
   * @returns {Array<{ approvalId, filename, recipient, amount, method, created, expiresIn }>}
   */
  listPendingPayments() {
    if (!fs.existsSync(this.pendingDir)) return [];

    const files = fs.readdirSync(this.pendingDir).filter(
      (f) => f.startsWith("APPROVAL_REQUIRED_payment_") && f.endsWith(".md")
    );

    return files.map((filename) => {
      const filePath = path.join(this.pendingDir, filename);
      const metadata = this._parseMetadata(filePath);

      // Extract approval ID from filename
      const idMatch = filename.match(/payment_([a-f0-9]+)\.md$/);
      const approvalId = idMatch ? idMatch[1] : "";

      // Calculate expiry
      let expiresIn = "unknown";
      if (metadata.created) {
        const created = new Date(metadata.created).getTime();
        const expiresAt = created + EXPIRY_HOURS * 60 * 60 * 1000;
        const remainingMs = expiresAt - Date.now();

        if (remainingMs <= 0) {
          expiresIn = "EXPIRED";
        } else {
          const h = Math.floor(remainingMs / (60 * 60 * 1000));
          const m = Math.floor(
            (remainingMs % (60 * 60 * 1000)) / (60 * 1000)
          );
          expiresIn = `${h}h ${m}m`;
        }
      }

      return {
        approvalId,
        filename,
        recipient: metadata.recipient || "unknown",
        amount: metadata.amount || "0",
        method: metadata.method || "unknown",
        created: metadata.created || "",
        riskLevel: metadata.risk_level || "high",
        expiresIn,
      };
    });
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  _determineRiskLevel(data) {
    // Any fraud flag → high risk
    if (data.fraudFlags && data.fraudFlags.length > 0) {
      return "high";
    }

    // Large amounts always high
    if (data.amount > 1000) {
      return "high";
    }

    // Default: high for payments (security-first)
    return "high";
  }

  _findPendingFile(approvalId) {
    if (!fs.existsSync(this.pendingDir)) return null;

    const files = fs.readdirSync(this.pendingDir);
    const match = files.find(
      (f) => f.includes(approvalId) && f.startsWith("APPROVAL_REQUIRED_payment_")
    );
    return match ? path.join(this.pendingDir, match) : null;
  }

  _expireApproval(approvalId, filePath) {
    if (!filePath || !fs.existsSync(filePath)) return;

    const destPath = path.join(this.rejectedDir, path.basename(filePath));

    if (!fs.existsSync(this.rejectedDir)) {
      fs.mkdirSync(this.rejectedDir, { recursive: true });
    }

    let content = fs.readFileSync(filePath, "utf-8");
    content +=
      `\n\n---\n**Expired** automatically at ${new Date().toISOString()} (exceeded ${EXPIRY_HOURS}h limit)\n`;
    fs.writeFileSync(filePath, content, "utf-8");

    fs.renameSync(filePath, destPath);
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

  _buildPaymentMarkdown(data) {
    const now = new Date();
    const expires = new Date(now.getTime() + EXPIRY_HOURS * 60 * 60 * 1000);

    const riskEmoji = { low: "🟢", medium: "🟡", high: "🔴" };
    const methodNames = {
      bank_transfer: "Bank Transfer",
      paypal: "PayPal",
      stripe: "Stripe",
    };

    let md = "";
    md += "---\n";
    md += `id: ${data.id}\n`;
    md += `type: payment_approval\n`;
    md += `action_type: payment\n`;
    md += `platform: payment\n`;
    md += `action: draft_payment\n`;
    md += `recipient: ${data.recipient}\n`;
    md += `amount: ${data.amount}\n`;
    md += `method: ${data.method}\n`;
    md += `currency: ${data.currency || "USD"}\n`;
    md += `reference: ${data.reference || "none"}\n`;
    md += `category: ${data.category || "general"}\n`;
    md += `created: ${now.toISOString()}\n`;
    md += `expires: ${expires.toISOString()}\n`;
    md += `risk_level: ${data.riskLevel}\n`;
    md += `risk_score: ${data.riskScore || 0}\n`;
    md += `fraud_flags: ${(data.fraudFlags || []).join(", ") || "none"}\n`;
    md += `status: pending\n`;
    md += "---\n\n";

    md += `# ${riskEmoji[data.riskLevel] || "🔴"} Payment Approval Required\n\n`;

    md += `## Transaction Details\n\n`;
    md += `| Field | Value |\n`;
    md += `|-------|-------|\n`;
    md += `| **Recipient** | ${data.recipient} |\n`;
    md += `| **Amount** | ${data.currency || "USD"} ${data.amount} |\n`;
    md += `| **Method** | ${methodNames[data.method] || data.method} |\n`;
    md += `| **Reference** | ${data.reference || "—"} |\n`;
    md += `| **Category** | ${data.category || "general"} |\n`;
    md += `| **Created** | ${now.toISOString()} |\n`;
    md += `| **Expires** | ${expires.toISOString()} (${EXPIRY_HOURS}h) |\n`;
    md += `| **Risk Level** | ${riskEmoji[data.riskLevel] || "🔴"} ${data.riskLevel.toUpperCase()} |\n`;
    md += `| **Risk Score** | ${data.riskScore || 0}/100 |\n\n`;

    // Fraud analysis section
    md += `## Security Analysis\n\n`;

    if (data.fraudFlags && data.fraudFlags.length > 0) {
      md += `**⚠️ ${data.fraudFlags.length} flag(s) detected:**\n\n`;

      for (const flag of data.fraudFlags) {
        const description =
          data.fraudDetails?.[flag] || flag.replace(/_/g, " ");
        md += `- **${flag}**: ${description}\n`;
      }
      md += "\n";
    } else {
      md += `**✅ No suspicious patterns detected.**\n\n`;
    }

    // Security reminder
    md += `## ⚠️ Security Checklist\n\n`;
    md += `- [ ] Recipient identity verified\n`;
    md += `- [ ] Amount matches expected value\n`;
    md += `- [ ] Payment method is correct\n`;
    md += `- [ ] Reference matches a known invoice/contract\n`;
    md += `- [ ] No credential data is stored in this file\n\n`;

    md += `## Decision\n\n`;
    md += `To **approve** this payment:\n`;
    md += `→ Move this file to the \`Approved/\` folder\n\n`;
    md += `To **reject** this payment:\n`;
    md += `→ Move this file to the \`Rejected/\` folder\n\n`;
    md += `> **Note:** This approval expires in ${EXPIRY_HOURS} hours. Expired approvals are automatically rejected.\n`;

    return md;
  }
}
