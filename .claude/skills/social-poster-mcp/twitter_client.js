/**
 * Twitter/X Client — Twitter API v2 wrapper for posting tweets.
 *
 * Uses OAuth 1.0a (HMAC-SHA1) for user-context authentication.
 * Media upload uses the v1.1 media/upload endpoint (required for v2 tweets with images).
 * Uses native fetch() (Node 18+) — no external SDK dependency.
 */

import fs from "fs";
import path from "path";
import crypto from "crypto";

const TWITTER_API_BASE = "https://api.twitter.com/2";
const UPLOAD_API_BASE = "https://upload.twitter.com/1.1";
const CHAR_LIMIT = 280;

export class TwitterClient {
  /**
   * @param {object} options
   * @param {string} options.apiKey            — Consumer API key
   * @param {string} options.apiSecret         — Consumer API secret
   * @param {string} options.accessToken       — User access token
   * @param {string} options.accessTokenSecret — User access token secret
   * @param {string} [options.bearerToken]     — App-only bearer token (for reads)
   * @param {string} [options.vaultPath]       — Path to the Obsidian vault
   */
  constructor({
    apiKey,
    apiSecret,
    accessToken,
    accessTokenSecret,
    bearerToken,
    vaultPath,
  } = {}) {
    this.apiKey = apiKey || process.env.TWITTER_API_KEY || "";
    this.apiSecret = apiSecret || process.env.TWITTER_API_SECRET || "";
    this.accessToken = accessToken || process.env.TWITTER_ACCESS_TOKEN || "";
    this.accessTokenSecret =
      accessTokenSecret || process.env.TWITTER_ACCESS_TOKEN_SECRET || "";
    this.bearerToken = bearerToken || process.env.TWITTER_BEARER_TOKEN || "";
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";

    if (!this.apiKey || !this.apiSecret) {
      throw new Error("TWITTER_API_KEY and TWITTER_API_SECRET are required");
    }
    if (!this.accessToken || !this.accessTokenSecret) {
      throw new Error(
        "TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_TOKEN_SECRET are required"
      );
    }
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Create a tweet.
   *
   * @param {object} params
   * @param {string} params.text       — Tweet text (max 280 chars)
   * @param {string} [params.imageFile] — Image filename from vault Attachments/
   * @returns {{ tweetId: string, tweetUrl: string }}
   */
  async createTweet({ text, imageFile }) {
    if (!text) throw new Error("Tweet text is required");
    if (text.length > CHAR_LIMIT) {
      throw new Error(
        `Tweet exceeds character limit: ${text.length}/${CHAR_LIMIT}`
      );
    }

    const body = { text };

    // Upload media if provided
    if (imageFile) {
      const mediaId = await this._uploadMedia(imageFile);
      body.media = { media_ids: [mediaId] };
    }

    const result = await this._retry(async () => {
      const url = `${TWITTER_API_BASE}/tweets`;
      const oauthHeader = this._buildOAuthHeader("POST", url);

      const res = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: oauthHeader,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.detail || err.title || `Twitter API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    const tweetId = result.data?.id;
    const tweetUrl = `https://twitter.com/i/web/status/${tweetId}`;

    await this._logAction("create_tweet", { tweetId, tweetUrl, text, imageFile });

    return { tweetId, tweetUrl };
  }

  /**
   * Get public metrics for a tweet.
   *
   * @param {string} tweetId — Tweet ID
   * @returns {{ likes: number, retweets: number, replies: number, impressions: number }}
   */
  async getTweetMetrics(tweetId) {
    const url = `${TWITTER_API_BASE}/tweets/${tweetId}?tweet.fields=public_metrics`;

    const result = await this._retry(async () => {
      const headers = {};

      // Prefer bearer token for read-only requests
      if (this.bearerToken) {
        headers.Authorization = `Bearer ${this.bearerToken}`;
      } else {
        headers.Authorization = this._buildOAuthHeader("GET", url.split("?")[0]);
      }

      const res = await fetch(url, { headers });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.detail || err.title || `Twitter API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    const metrics = result.data?.public_metrics || {};

    return {
      likes: metrics.like_count || 0,
      retweets: metrics.retweet_count || 0,
      replies: metrics.reply_count || 0,
      impressions: metrics.impression_count || 0,
    };
  }

  // -------------------------------------------------------------------------
  // Media upload (v1.1 endpoint — required for v2 tweets)
  // -------------------------------------------------------------------------

  async _uploadMedia(imageFile) {
    const filePath = path.join(this.vaultPath, "Attachments", imageFile);
    if (!fs.existsSync(filePath)) {
      throw new Error(`Image not found: ${filePath}`);
    }

    const imageBuffer = fs.readFileSync(filePath);
    const mediaType = this._getImageMimeType(imageFile);

    const boundary = `boundary_${Date.now()}_${Math.random().toString(36).slice(2)}`;

    // Build multipart form-data
    const parts = [];

    // media_data (base64 encoded)
    parts.push(
      `--${boundary}\r\n` +
        `Content-Disposition: form-data; name="media_data"\r\n\r\n` +
        `${imageBuffer.toString("base64")}\r\n`
    );

    // media_category
    parts.push(
      `--${boundary}\r\n` +
        `Content-Disposition: form-data; name="media_category"\r\n\r\n` +
        `tweet_image\r\n`
    );

    parts.push(`--${boundary}--\r\n`);

    const url = `${UPLOAD_API_BASE}/media/upload.json`;
    const oauthHeader = this._buildOAuthHeader("POST", url);

    const result = await this._retry(async () => {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: oauthHeader,
          "Content-Type": `multipart/form-data; boundary=${boundary}`,
        },
        body: parts.join(""),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.errors?.[0]?.message || `Media upload failed: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    return result.media_id_string;
  }

  // -------------------------------------------------------------------------
  // OAuth 1.0a signature
  // -------------------------------------------------------------------------

  _buildOAuthHeader(method, url, extraParams = {}) {
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const nonce = crypto.randomBytes(16).toString("hex");

    const oauthParams = {
      oauth_consumer_key: this.apiKey,
      oauth_nonce: nonce,
      oauth_signature_method: "HMAC-SHA1",
      oauth_timestamp: timestamp,
      oauth_token: this.accessToken,
      oauth_version: "1.0",
      ...extraParams,
    };

    // Build parameter string (sorted)
    const allParams = { ...oauthParams };
    const paramString = Object.keys(allParams)
      .sort()
      .map(
        (k) =>
          `${encodeURIComponent(k)}=${encodeURIComponent(allParams[k])}`
      )
      .join("&");

    // Build signature base string
    const signatureBase = [
      method.toUpperCase(),
      encodeURIComponent(url),
      encodeURIComponent(paramString),
    ].join("&");

    // Sign with HMAC-SHA1
    const signingKey = `${encodeURIComponent(this.apiSecret)}&${encodeURIComponent(this.accessTokenSecret)}`;
    const signature = crypto
      .createHmac("sha1", signingKey)
      .update(signatureBase)
      .digest("base64");

    oauthParams.oauth_signature = signature;

    // Build Authorization header
    const headerParts = Object.keys(oauthParams)
      .sort()
      .map(
        (k) =>
          `${encodeURIComponent(k)}="${encodeURIComponent(oauthParams[k])}"`
      )
      .join(", ");

    return `OAuth ${headerParts}`;
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

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
            `[twitter] Retry ${attempt + 1}/${maxRetries} (${status}), waiting ${Math.round(delay)}ms`
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
      platform: "twitter",
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
