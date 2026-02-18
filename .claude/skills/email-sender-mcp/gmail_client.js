/**
 * Gmail Client — wrapper around the Gmail API for sending emails.
 *
 * Handles OAuth2 authentication, MIME message construction,
 * attachments, drafts, replies, retry logic, and action logging.
 */

import { google } from "googleapis";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Gmail Client
// ---------------------------------------------------------------------------

export class GmailClient {
  /**
   * @param {object} options
   * @param {string} [options.vaultPath] — Path to the Obsidian vault
   */
  constructor({ vaultPath } = {}) {
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";
    this.clientId = process.env.GMAIL_CLIENT_ID || "";
    this.clientSecret = process.env.GMAIL_CLIENT_SECRET || "";

    this.tokenPath = this._findTokenFile();
    this.auth = null;
    this.gmail = null;

    this._authenticate();
  }

  // -----------------------------------------------------------------------
  // Authentication
  // -----------------------------------------------------------------------

  _findTokenFile() {
    const projectRoot = this._findProjectRoot();
    const candidates = [
      path.join(projectRoot, "dashboard", "gmail-token.json"),
      path.join(projectRoot, "gmail-token.json"),
      path.join(projectRoot, "token.json"),
    ];
    for (const p of candidates) {
      if (fs.existsSync(p)) return p;
    }
    return path.join(projectRoot, "gmail-token.json");
  }

  _findProjectRoot() {
    let dir = __dirname;
    for (let i = 0; i < 6; i++) {
      if (
        fs.existsSync(path.join(dir, "obsidian-vault")) ||
        fs.existsSync(path.join(dir, ".env"))
      ) {
        return dir;
      }
      dir = path.dirname(dir);
    }
    return __dirname;
  }

  _authenticate() {
    this.auth = new google.auth.OAuth2(
      this.clientId,
      this.clientSecret,
      "http://localhost:3000/api/auth/callback/google"
    );

    if (!fs.existsSync(this.tokenPath)) {
      throw new Error(
        `Gmail token not found at ${this.tokenPath}. ` +
          "Complete the OAuth flow via the dashboard first."
      );
    }

    const tokenData = JSON.parse(fs.readFileSync(this.tokenPath, "utf-8"));
    this.auth.setCredentials({
      access_token: tokenData.access_token || tokenData.token,
      refresh_token: tokenData.refresh_token,
      expiry_date: tokenData.expiry
        ? new Date(tokenData.expiry).getTime()
        : undefined,
    });

    // Auto-refresh and persist
    this.auth.on("tokens", (tokens) => {
      const existing = JSON.parse(fs.readFileSync(this.tokenPath, "utf-8"));
      if (tokens.access_token) existing.access_token = tokens.access_token;
      if (tokens.refresh_token) existing.refresh_token = tokens.refresh_token;
      if (tokens.expiry_date)
        existing.expiry = new Date(tokens.expiry_date).toISOString();
      fs.writeFileSync(this.tokenPath, JSON.stringify(existing, null, 2));
    });

    this.gmail = google.gmail({ version: "v1", auth: this.auth });
  }

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  /**
   * Send an email.
   * @returns {{ messageId: string, threadId: string }}
   */
  async sendEmail({ to, cc, bcc, subject, body, isHtml = false, attachments = [] }) {
    const raw = await this._buildMimeMessage({
      to, cc, bcc, subject, body, isHtml, attachments,
    });

    const result = await this._retry(async () => {
      const res = await this.gmail.users.messages.send({
        userId: "me",
        requestBody: { raw },
      });
      return res.data;
    });

    await this._logAction("send_email", {
      to, cc, bcc, subject,
      messageId: result.id,
      threadId: result.threadId,
    });

    return { messageId: result.id, threadId: result.threadId };
  }

  /**
   * Create a draft (does not send).
   * @returns {{ draftId: string, messageId: string }}
   */
  async createDraft({ to, subject, body, isHtml = false }) {
    const raw = await this._buildMimeMessage({
      to, subject, body, isHtml,
    });

    const result = await this._retry(async () => {
      const res = await this.gmail.users.drafts.create({
        userId: "me",
        requestBody: { message: { raw } },
      });
      return res.data;
    });

    await this._logAction("draft_email", {
      to, subject,
      draftId: result.id,
      messageId: result.message?.id,
    });

    return { draftId: result.id, messageId: result.message?.id };
  }

  /**
   * Reply to an existing email.
   * @returns {{ messageId: string, threadId: string }}
   */
  async replyToEmail({ messageId, body, isHtml = false, replyAll = false }) {
    // Fetch original message for threading headers
    const original = await this._retry(async () => {
      const res = await this.gmail.users.messages.get({
        userId: "me",
        id: messageId,
        format: "metadata",
        metadataHeaders: ["Subject", "From", "To", "Cc", "Message-ID", "References"],
      });
      return res.data;
    });

    const headers = {};
    for (const h of original.payload?.headers || []) {
      headers[h.name] = h.value;
    }

    const origSubject = headers["Subject"] || "";
    const subject = origSubject.startsWith("Re:") ? origSubject : `Re: ${origSubject}`;
    const to = replyAll
      ? [headers["From"], headers["To"], headers["Cc"]].filter(Boolean).join(", ")
      : headers["From"];
    const inReplyTo = headers["Message-ID"] || "";
    const references = [headers["References"], inReplyTo].filter(Boolean).join(" ");

    const raw = await this._buildMimeMessage({
      to,
      subject,
      body,
      isHtml,
      inReplyTo,
      references,
      threadId: original.threadId,
    });

    const result = await this._retry(async () => {
      const res = await this.gmail.users.messages.send({
        userId: "me",
        requestBody: { raw, threadId: original.threadId },
      });
      return res.data;
    });

    await this._logAction("reply_to_email", {
      originalMessageId: messageId,
      messageId: result.id,
      threadId: result.threadId,
      replyAll,
    });

    return { messageId: result.id, threadId: result.threadId };
  }

  // -----------------------------------------------------------------------
  // MIME message construction
  // -----------------------------------------------------------------------

  async _buildMimeMessage({
    to, cc, bcc, subject = "", body = "", isHtml = false,
    attachments = [], inReplyTo, references, threadId,
  }) {
    const boundary = `boundary_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const hasAttachments = attachments && attachments.length > 0;

    let mime = "";
    mime += `To: ${to}\r\n`;
    if (cc) mime += `Cc: ${cc}\r\n`;
    if (bcc) mime += `Bcc: ${bcc}\r\n`;
    mime += `Subject: ${subject}\r\n`;
    mime += `MIME-Version: 1.0\r\n`;

    if (inReplyTo) mime += `In-Reply-To: ${inReplyTo}\r\n`;
    if (references) mime += `References: ${references}\r\n`;

    if (hasAttachments) {
      mime += `Content-Type: multipart/mixed; boundary="${boundary}"\r\n`;
      mime += `\r\n`;
      mime += `--${boundary}\r\n`;
      mime += `Content-Type: ${isHtml ? "text/html" : "text/plain"}; charset="UTF-8"\r\n`;
      mime += `\r\n`;
      mime += `${body}\r\n`;

      for (const filename of attachments) {
        const attachment = this._loadAttachment(filename);
        mime += `\r\n--${boundary}\r\n`;
        mime += `Content-Type: ${attachment.mimeType}; name="${attachment.filename}"\r\n`;
        mime += `Content-Disposition: attachment; filename="${attachment.filename}"\r\n`;
        mime += `Content-Transfer-Encoding: base64\r\n`;
        mime += `\r\n`;
        mime += `${attachment.content}\r\n`;
      }

      mime += `\r\n--${boundary}--\r\n`;
    } else {
      mime += `Content-Type: ${isHtml ? "text/html" : "text/plain"}; charset="UTF-8"\r\n`;
      mime += `\r\n`;
      mime += `${body}\r\n`;
    }

    // Gmail API requires URL-safe base64
    return Buffer.from(mime)
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  }

  _loadAttachment(filename) {
    const filePath = path.join(this.vaultPath, "Attachments", filename);
    if (!fs.existsSync(filePath)) {
      throw new Error(`Attachment not found: ${filePath}`);
    }

    const content = fs.readFileSync(filePath).toString("base64");
    const ext = path.extname(filename).toLowerCase();

    const mimeTypes = {
      ".pdf": "application/pdf",
      ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".gif": "image/gif",
      ".txt": "text/plain",
      ".csv": "text/csv",
      ".zip": "application/zip",
    };

    return {
      content,
      mimeType: mimeTypes[ext] || "application/octet-stream",
      filename: path.basename(filename),
    };
  }

  // -----------------------------------------------------------------------
  // Retry logic
  // -----------------------------------------------------------------------

  async _retry(fn, maxRetries = 3, baseDelay = 1000) {
    let lastError;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err;
        const status = err?.response?.status || err?.code;

        // Retry on transient errors only
        if (status === 429 || status === 500 || status === 503 || status === "ECONNRESET") {
          const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 500;
          console.error(
            `[retry] Attempt ${attempt + 1}/${maxRetries} failed (${status}), waiting ${Math.round(delay)}ms`
          );
          await new Promise((r) => setTimeout(r, delay));
        } else {
          throw err;
        }
      }
    }
    throw lastError;
  }

  // -----------------------------------------------------------------------
  // Action logging
  // -----------------------------------------------------------------------

  async _logAction(action, details) {
    const logsDir = path.join(this.vaultPath, "Logs");
    if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });

    const logFile = path.join(logsDir, "email_actions.json");

    const entry = {
      timestamp: new Date().toISOString(),
      action,
      ...details,
    };

    let logs = [];
    if (fs.existsSync(logFile)) {
      try {
        logs = JSON.parse(fs.readFileSync(logFile, "utf-8"));
      } catch {
        logs = [];
      }
    }

    logs.push(entry);
    fs.writeFileSync(logFile, JSON.stringify(logs, null, 2));
  }
}
