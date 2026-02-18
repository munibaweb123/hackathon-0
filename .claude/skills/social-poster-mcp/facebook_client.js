/**
 * Facebook Client — Meta Graph API wrapper for Facebook Page posting.
 *
 * Uses native fetch() (Node 18+) with the Graph API v19.0.
 * Supports text posts, link posts, and image posts.
 */

import fs from "fs";
import path from "path";

const GRAPH_API_BASE = "https://graph.facebook.com/v19.0";
const CHAR_LIMIT = 63206;

export class FacebookClient {
  /**
   * @param {object} options
   * @param {string} options.pageId       — Facebook Page ID
   * @param {string} options.accessToken  — Page Access Token (long-lived)
   * @param {string} [options.vaultPath]  — Path to the Obsidian vault
   */
  constructor({ pageId, accessToken, vaultPath } = {}) {
    this.pageId = pageId || process.env.FACEBOOK_PAGE_ID || "";
    this.accessToken = accessToken || process.env.FACEBOOK_ACCESS_TOKEN || "";
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";

    if (!this.pageId) throw new Error("FACEBOOK_PAGE_ID is required");
    if (!this.accessToken) throw new Error("FACEBOOK_ACCESS_TOKEN is required");
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Create a post on the Facebook Page.
   *
   * @param {object} params
   * @param {string} params.message    — Post text
   * @param {string} [params.link]     — URL to share
   * @param {string} [params.imageFile] — Image filename from vault Attachments/
   * @returns {{ postId: string, postUrl: string }}
   */
  async createPost({ message, link, imageFile }) {
    if (message && message.length > CHAR_LIMIT) {
      throw new Error(
        `Message exceeds Facebook character limit: ${message.length}/${CHAR_LIMIT}`
      );
    }

    // Image post — use /photos endpoint with multipart upload
    if (imageFile) {
      return await this._createImagePost(message, imageFile);
    }

    // Text/link post — use /feed endpoint
    const body = { message, access_token: this.accessToken };
    if (link) body.link = link;

    const result = await this._retry(async () => {
      const res = await fetch(`${GRAPH_API_BASE}/${this.pageId}/feed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.error?.message || `Facebook API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    const postId = result.id;
    const postUrl = `https://www.facebook.com/${postId.replace("_", "/posts/")}`;

    await this._logAction("facebook_post", { postId, postUrl, message, link });

    return { postId, postUrl };
  }

  /**
   * Get engagement metrics for a Facebook post.
   *
   * @param {string} postId — Facebook post ID (e.g. "pageId_postId")
   * @returns {{ likes: number, comments: number, shares: number }}
   */
  async getPostInsights(postId) {
    const fields = "likes.summary(true),comments.summary(true),shares";

    const result = await this._retry(async () => {
      const url = new URL(`${GRAPH_API_BASE}/${postId}`);
      url.searchParams.set("fields", fields);
      url.searchParams.set("access_token", this.accessToken);

      const res = await fetch(url.toString());
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.error?.message || `Facebook API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    return {
      likes: result.likes?.summary?.total_count || 0,
      comments: result.comments?.summary?.total_count || 0,
      shares: result.shares?.count || 0,
    };
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  async _createImagePost(message, imageFile) {
    const filePath = path.join(this.vaultPath, "Attachments", imageFile);
    if (!fs.existsSync(filePath)) {
      throw new Error(`Image not found: ${filePath}`);
    }

    const imageBuffer = fs.readFileSync(filePath);
    const boundary = `boundary_${Date.now()}_${Math.random().toString(36).slice(2)}`;

    // Build multipart form data manually
    let body = "";
    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="message"\r\n\r\n`;
    body += `${message || ""}\r\n`;

    body += `--${boundary}\r\n`;
    body += `Content-Disposition: form-data; name="access_token"\r\n\r\n`;
    body += `${this.accessToken}\r\n`;

    // Image part — use Buffer for binary
    const headerPart = Buffer.from(
      `--${boundary}\r\n` +
        `Content-Disposition: form-data; name="source"; filename="${imageFile}"\r\n` +
        `Content-Type: ${this._getImageMimeType(imageFile)}\r\n\r\n`
    );
    const textPart = Buffer.from(body);
    const footerPart = Buffer.from(`\r\n--${boundary}--\r\n`);

    const fullBody = Buffer.concat([textPart, headerPart, imageBuffer, footerPart]);

    const result = await this._retry(async () => {
      const res = await fetch(`${GRAPH_API_BASE}/${this.pageId}/photos`, {
        method: "POST",
        headers: {
          "Content-Type": `multipart/form-data; boundary=${boundary}`,
        },
        body: fullBody,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.error?.message || `Facebook API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    const postId = result.post_id || result.id;
    const postUrl = `https://www.facebook.com/${this.pageId}/photos/${result.id}`;

    await this._logAction("facebook_image_post", {
      postId,
      postUrl,
      message,
      imageFile,
    });

    return { postId, postUrl };
  }

  _getImageMimeType(filename) {
    const ext = path.extname(filename).toLowerCase();
    const types = {
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".gif": "image/gif",
      ".webp": "image/webp",
    };
    return types[ext] || "application/octet-stream";
  }

  async _retry(fn, maxRetries = 3, baseDelay = 1000) {
    let lastError;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err;
        const status = err.status || 0;

        if (status === 429 || status >= 500) {
          const delay =
            baseDelay * Math.pow(2, attempt) + Math.random() * 500;
          console.error(
            `[facebook] Retry ${attempt + 1}/${maxRetries} (${status}), waiting ${Math.round(delay)}ms`
          );
          await new Promise((r) => setTimeout(r, delay));
        } else {
          throw err;
        }
      }
    }
    throw lastError;
  }

  async _logAction(action, details) {
    const logsDir = path.join(this.vaultPath, "Logs");
    if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });

    const logFile = path.join(logsDir, "social_media.json");

    const entry = {
      timestamp: new Date().toISOString(),
      platform: "facebook",
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
