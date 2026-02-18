/**
 * Odoo Client — JSON-RPC 2.0 wrapper for Odoo Community Edition (v19+).
 *
 * Connects to a local Odoo instance and exposes CRUD helpers, method calls,
 * and report download. Uses native fetch() (Node 18+).
 *
 * Odoo JSON-RPC protocol:
 *   POST /jsonrpc
 *   { "jsonrpc": "2.0", "method": "call",
 *     "params": { "service": "...", "method": "...", "args": [...] } }
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export class OdooClient {
  /**
   * @param {object} options
   * @param {string} [options.url]       — Odoo base URL (default: http://localhost:8069)
   * @param {string} [options.db]        — Database name
   * @param {string} [options.username]   — Odoo username
   * @param {string} [options.password]   — Odoo password
   * @param {string} [options.vaultPath] — Path to the Obsidian vault
   */
  constructor({ url, db, username, password, vaultPath } = {}) {
    const config = this._loadConfig();

    this.url = url || process.env.ODOO_URL || config.url || "http://localhost:8069";
    this.db = db || process.env.ODOO_DB || config.db || "";
    this.username = username || process.env.ODOO_USERNAME || config.username || "";
    this.password = password || process.env.ODOO_PASSWORD || config.password || "";
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";

    this.uid = null;
    this._requestId = 0;

    if (!this.db) throw new Error("ODOO_DB is required (database name)");
    if (!this.username) throw new Error("ODOO_USERNAME is required");
    if (!this.password) throw new Error("ODOO_PASSWORD is required");
  }

  // -------------------------------------------------------------------------
  // Authentication
  // -------------------------------------------------------------------------

  /**
   * Authenticate with Odoo and store the user ID.
   * Must be called before any CRUD operation.
   */
  async authenticate() {
    const result = await this._jsonRpc("common", "login", [
      this.db,
      this.username,
      this.password,
    ]);

    if (!result) {
      throw new Error(
        "Odoo authentication failed. Check database, username, and password."
      );
    }

    this.uid = result;
    return this.uid;
  }

  /**
   * Ensure authenticated — call authenticate() if uid is not set.
   */
  async _ensureAuth() {
    if (!this.uid) {
      await this.authenticate();
    }
  }

  // -------------------------------------------------------------------------
  // Generic ORM helpers
  // -------------------------------------------------------------------------

  /**
   * Call execute_kw on a model.
   * @param {string} model   — Odoo model (e.g., "account.move")
   * @param {string} method  — ORM method (e.g., "search_read", "create")
   * @param {Array} args     — Positional args
   * @param {object} [kwargs] — Keyword args
   */
  async execute_kw(model, method, args = [], kwargs = {}) {
    await this._ensureAuth();

    return await this._retry(async () => {
      return await this._jsonRpc("object", "execute_kw", [
        this.db,
        this.uid,
        this.password,
        model,
        method,
        args,
        kwargs,
      ]);
    });
  }

  /**
   * Search and read records.
   * @param {string} model    — Odoo model
   * @param {Array} domain    — Search domain (e.g., [["state","=","posted"]])
   * @param {Array} fields    — Fields to return
   * @param {object} [opts]   — Extra kwargs (limit, offset, order)
   */
  async searchRead(model, domain = [], fields = [], opts = {}) {
    return await this.execute_kw(model, "search_read", [domain], {
      fields,
      ...opts,
    });
  }

  /**
   * Create a record.
   * @param {string} model  — Odoo model
   * @param {object} values — Field values
   * @returns {number} — Created record ID
   */
  async create(model, values) {
    const result = await this.execute_kw(model, "create", [values]);
    return result;
  }

  /**
   * Update records.
   * @param {string} model  — Odoo model
   * @param {Array} ids     — Record IDs to update
   * @param {object} values — Field values to set
   */
  async write(model, ids, values) {
    return await this.execute_kw(model, "write", [ids, values]);
  }

  /**
   * Call a named method on records (e.g., action_post to confirm).
   * @param {string} model  — Odoo model
   * @param {string} method — Method name
   * @param {Array} ids     — Record IDs
   * @param {Array} [args]  — Additional positional args
   */
  async callMethod(model, method, ids, args = []) {
    return await this.execute_kw(model, method, [ids, ...args]);
  }

  // -------------------------------------------------------------------------
  // Report / PDF download
  // -------------------------------------------------------------------------

  /**
   * Download a PDF report from Odoo.
   * @param {string} reportName — Report technical name (e.g., "account.report_invoice")
   * @param {Array} ids         — Record IDs to include
   * @returns {Buffer} — PDF file content
   */
  async getReport(reportName, ids) {
    await this._ensureAuth();

    // Odoo report download URL format
    const reportUrl = `${this.url}/report/pdf/${reportName}/${ids.join(",")}`;

    const result = await this._retry(async () => {
      const res = await fetch(reportUrl, {
        method: "GET",
        headers: {
          Cookie: await this._getSessionCookie(),
        },
      });

      if (!res.ok) {
        const error = new Error(`Report download failed: ${res.status}`);
        error.status = res.status;
        throw error;
      }

      return Buffer.from(await res.arrayBuffer());
    });

    return result;
  }

  /**
   * Get a session cookie by authenticating via the web login.
   * Needed for report downloads which use HTTP sessions, not JSON-RPC auth.
   */
  async _getSessionCookie() {
    const res = await fetch(`${this.url}/web/session/authenticate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "call",
        params: {
          db: this.db,
          login: this.username,
          password: this.password,
        },
      }),
    });

    const setCookie = res.headers.get("set-cookie");
    if (!setCookie) {
      throw new Error("Failed to get Odoo session cookie for report download");
    }

    // Extract session_id from Set-Cookie header
    const match = setCookie.match(/session_id=([^;]+)/);
    return match ? `session_id=${match[1]}` : setCookie.split(";")[0];
  }

  // -------------------------------------------------------------------------
  // Low-level JSON-RPC
  // -------------------------------------------------------------------------

  async _jsonRpc(service, method, args) {
    this._requestId++;

    const payload = {
      jsonrpc: "2.0",
      method: "call",
      id: this._requestId,
      params: {
        service,
        method,
        args,
      },
    };

    const res = await fetch(`${this.url}/jsonrpc`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const error = new Error(`Odoo HTTP error: ${res.status} ${res.statusText}`);
      error.status = res.status;
      throw error;
    }

    const data = await res.json();

    if (data.error) {
      const errMsg =
        data.error.data?.message ||
        data.error.message ||
        JSON.stringify(data.error);
      throw new Error(`Odoo RPC error: ${errMsg}`);
    }

    return data.result;
  }

  // -------------------------------------------------------------------------
  // Config loading
  // -------------------------------------------------------------------------

  _loadConfig() {
    // Search for odoo_config.json upward from script dir
    const configNames = ["odoo_config.json", "odoo_config.example.json"];

    for (let dir = __dirname, i = 0; i < 6; i++, dir = path.dirname(dir)) {
      for (const name of configNames) {
        const configPath = path.join(dir, name);
        if (name === "odoo_config.json" && fs.existsSync(configPath)) {
          try {
            return JSON.parse(fs.readFileSync(configPath, "utf-8"));
          } catch {
            // Ignore parse errors
          }
        }
      }
    }

    // Also check the skill directory
    const localConfig = path.join(__dirname, "odoo_config.json");
    if (fs.existsSync(localConfig)) {
      try {
        return JSON.parse(fs.readFileSync(localConfig, "utf-8"));
      } catch {
        // Ignore
      }
    }

    return {};
  }

  // -------------------------------------------------------------------------
  // Retry logic
  // -------------------------------------------------------------------------

  async _retry(fn, maxRetries = 3, baseDelay = 1000) {
    let lastError;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err;
        const status = err.status || 0;

        // Retry on transient errors only
        if (
          status === 429 ||
          status >= 500 ||
          err.code === "ECONNREFUSED" ||
          err.code === "ECONNRESET"
        ) {
          const delay =
            baseDelay * Math.pow(2, attempt) + Math.random() * 500;
          console.error(
            `[odoo] Retry ${attempt + 1}/${maxRetries} (${status || err.code}), waiting ${Math.round(delay)}ms`
          );
          await new Promise((r) => setTimeout(r, delay));
        } else {
          throw err;
        }
      }
    }
    throw lastError;
  }

  // -------------------------------------------------------------------------
  // Action logging
  // -------------------------------------------------------------------------

  async logAction(action, details) {
    const logsDir = path.join(this.vaultPath, "Logs");
    if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });

    const logFile = path.join(logsDir, "accounting.json");

    const entry = {
      timestamp: new Date().toISOString(),
      service: "odoo",
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
