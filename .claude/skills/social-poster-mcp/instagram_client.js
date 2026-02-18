/**
 * Instagram Client — Meta Graph API wrapper for Instagram Business posting.
 *
 * Uses the two-step Container Publishing flow:
 *   1) POST /{ig-user-id}/media  → create media container
 *   2) POST /{ig-user-id}/media_publish → publish container
 *
 * Note: Instagram API requires images — text-only posts are not supported.
 * Images must be accessible via a public URL (the API downloads them server-side).
 */

import fs from "fs";
import path from "path";

const GRAPH_API_BASE = "https://graph.facebook.com/v19.0";
const CAPTION_LIMIT = 2200;

export class InstagramClient {
  /**
   * @param {object} options
   * @param {string} options.igUserId     — Instagram Business Account ID
   * @param {string} options.accessToken  — Meta Page Access Token (with instagram_* permissions)
   * @param {string} [options.vaultPath]  — Path to the Obsidian vault
   */
  constructor({ igUserId, accessToken, vaultPath } = {}) {
    this.igUserId = igUserId || process.env.INSTAGRAM_USER_ID || "";
    this.accessToken = accessToken || process.env.INSTAGRAM_ACCESS_TOKEN || "";
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";

    if (!this.igUserId) throw new Error("INSTAGRAM_USER_ID is required");
    if (!this.accessToken) throw new Error("INSTAGRAM_ACCESS_TOKEN is required");
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Create an Instagram post (image + optional caption).
   *
   * @param {object} params
   * @param {string} [params.caption]    — Post caption (max 2,200 chars)
   * @param {string} params.imageUrl     — Public URL of the image to post
   * @param {string} [params.imageFile]  — Alternative: filename from vault (requires public hosting)
   * @returns {{ postId: string, permalink: string }}
   */
  async createPost({ caption, imageUrl, imageFile }) {
    if (caption && caption.length > CAPTION_LIMIT) {
      throw new Error(
        `Caption exceeds Instagram limit: ${caption.length}/${CAPTION_LIMIT}`
      );
    }

    // Resolve image URL
    const resolvedImageUrl = imageUrl || this._resolveImageUrl(imageFile);
    if (!resolvedImageUrl) {
      throw new Error(
        "Instagram requires an image. Provide imageUrl (public URL) or imageFile."
      );
    }

    // Step 1: Create media container
    const containerId = await this._createMediaContainer(caption, resolvedImageUrl);

    // Step 2: Publish the container
    const result = await this._publishContainer(containerId);

    // Fetch permalink
    const postDetails = await this._getPostDetails(result.id);

    await this._logAction("instagram_post", {
      postId: result.id,
      permalink: postDetails.permalink,
      caption,
      imageUrl: resolvedImageUrl,
    });

    return {
      postId: result.id,
      permalink: postDetails.permalink || `https://www.instagram.com/p/${result.id}`,
    };
  }

  /**
   * Get engagement metrics for an Instagram post.
   *
   * @param {string} postId — Instagram media ID
   * @returns {{ likes: number, comments: number, timestamp: string, permalink: string }}
   */
  async getPostInsights(postId) {
    const fields = "like_count,comments_count,timestamp,permalink";

    const result = await this._retry(async () => {
      const url = new URL(`${GRAPH_API_BASE}/${postId}`);
      url.searchParams.set("fields", fields);
      url.searchParams.set("access_token", this.accessToken);

      const res = await fetch(url.toString());
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.error?.message || `Instagram API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    return {
      likes: result.like_count || 0,
      comments: result.comments_count || 0,
      timestamp: result.timestamp || "",
      permalink: result.permalink || "",
    };
  }

  // -------------------------------------------------------------------------
  // Private — Container Publishing Flow
  // -------------------------------------------------------------------------

  async _createMediaContainer(caption, imageUrl) {
    const result = await this._retry(async () => {
      const url = new URL(`${GRAPH_API_BASE}/${this.igUserId}/media`);

      const body = {
        image_url: imageUrl,
        access_token: this.accessToken,
      };
      if (caption) body.caption = caption;

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.error?.message || `Instagram container creation failed: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    return result.id;
  }

  async _publishContainer(containerId) {
    return await this._retry(async () => {
      const url = new URL(`${GRAPH_API_BASE}/${this.igUserId}/media_publish`);

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          creation_id: containerId,
          access_token: this.accessToken,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.error?.message || `Instagram publish failed: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });
  }

  async _getPostDetails(postId) {
    try {
      const url = new URL(`${GRAPH_API_BASE}/${postId}`);
      url.searchParams.set("fields", "permalink,timestamp");
      url.searchParams.set("access_token", this.accessToken);

      const res = await fetch(url.toString());
      if (res.ok) return await res.json();
    } catch {
      // Non-critical — return empty
    }
    return {};
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  _resolveImageUrl(imageFile) {
    if (!imageFile) return null;

    // Check if the file exists in the vault — but IG needs a public URL
    const filePath = path.join(this.vaultPath, "Attachments", imageFile);
    if (!fs.existsSync(filePath)) {
      throw new Error(
        `Image file not found in vault: ${filePath}. ` +
          "Instagram requires images to be hosted at a public URL."
      );
    }

    // If MEDIA_HOST_URL is set, construct the URL
    const mediaHost = process.env.MEDIA_HOST_URL;
    if (mediaHost) {
      return `${mediaHost.replace(/\/$/, "")}/${imageFile}`;
    }

    throw new Error(
      `Image file "${imageFile}" exists in vault but Instagram requires a public URL. ` +
        "Set MEDIA_HOST_URL env var or provide imageUrl directly."
    );
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
            `[instagram] Retry ${attempt + 1}/${maxRetries} (${status}), waiting ${Math.round(delay)}ms`
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
      platform: "instagram",
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
