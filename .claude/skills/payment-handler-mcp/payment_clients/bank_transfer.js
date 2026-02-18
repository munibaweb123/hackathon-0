/**
 * Bank Transfer Client — configurable backend for bank wire transfers.
 *
 * Connects to a configurable banking API endpoint. Uses native fetch() (Node 18+).
 * Credentials loaded from env vars only — never stored in vault.
 */

import fs from "fs";
import path from "path";

export class BankTransferClient {
  /**
   * @param {object} options
   * @param {string} [options.apiUrl]    — Banking API base URL
   * @param {string} [options.apiKey]    — API key for authentication
   * @param {string} [options.vaultPath] — Obsidian vault path (for logging only)
   */
  constructor({ apiUrl, apiKey, vaultPath } = {}) {
    this.apiUrl = apiUrl || process.env.BANK_API_URL || "";
    this.apiKey = apiKey || process.env.BANK_API_KEY || "";
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";

    if (!this.apiUrl) {
      console.error(
        "[bank_transfer] BANK_API_URL not set. Bank transfer operations will fail."
      );
    }
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Initiate a bank transfer.
   *
   * @param {object} params
   * @param {string} params.recipient    — Recipient name
   * @param {number} params.amount       — Transfer amount
   * @param {string} [params.currency]   — Currency code (default: USD)
   * @param {string} [params.reference]  — Payment reference
   * @param {object} [params.bankDetails] — IBAN, routing, account number
   * @returns {{ transactionId: string, status: string }}
   */
  async initiateTransfer({ recipient, amount, currency = "USD", reference, bankDetails }) {
    if (!this.apiUrl) {
      throw new Error(
        "BANK_API_URL not configured. Set the environment variable to enable bank transfers."
      );
    }

    const payload = {
      recipient,
      amount,
      currency,
      reference: reference || `PAY-${Date.now()}`,
      bank_details: bankDetails || {},
    };

    const result = await this._retry(async () => {
      const res = await fetch(`${this.apiUrl}/transfers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.message || `Bank API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    const transactionId = result.id || result.transaction_id || `bank_${Date.now()}`;

    await this._logTransaction("bank_transfer_initiated", {
      transactionId,
      recipient,
      amount,
      currency,
      reference,
      status: result.status || "pending",
    });

    return {
      transactionId,
      status: result.status || "pending",
    };
  }

  /**
   * Check transfer status.
   *
   * @param {string} transactionId
   * @returns {{ status: string, settledAt?: string, failureReason?: string }}
   */
  async checkStatus(transactionId) {
    if (!this.apiUrl) {
      return { status: "unknown", failureReason: "BANK_API_URL not configured" };
    }

    const result = await this._retry(async () => {
      const res = await fetch(`${this.apiUrl}/transfers/${transactionId}`, {
        headers: { Authorization: `Bearer ${this.apiKey}` },
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.message || `Bank API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    return {
      status: result.status || "unknown",
      settledAt: result.settled_at || null,
      failureReason: result.failure_reason || null,
    };
  }

  /**
   * Cancel a pending transfer.
   *
   * @param {string} transactionId
   * @returns {{ cancelled: boolean, message?: string }}
   */
  async cancelTransfer(transactionId) {
    if (!this.apiUrl) {
      return { cancelled: false, message: "BANK_API_URL not configured" };
    }

    try {
      const result = await this._retry(async () => {
        const res = await fetch(
          `${this.apiUrl}/transfers/${transactionId}/cancel`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${this.apiKey}` },
          }
        );

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          const error = new Error(
            err.message || `Cancel failed: ${res.status}`
          );
          error.status = res.status;
          throw error;
        }
        return res.json();
      });

      await this._logTransaction("bank_transfer_cancelled", {
        transactionId,
      });

      return { cancelled: true, message: result.message || "Transfer cancelled" };
    } catch (err) {
      return { cancelled: false, message: err.message };
    }
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  async _retry(fn, maxRetries = 3, baseDelay = 1000) {
    let lastError;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err;
        const status = err.status || 0;
        if (status === 429 || status >= 500) {
          const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 500;
          console.error(
            `[bank_transfer] Retry ${attempt + 1}/${maxRetries} (${status}), waiting ${Math.round(delay)}ms`
          );
          await new Promise((r) => setTimeout(r, delay));
        } else {
          throw err;
        }
      }
    }
    throw lastError;
  }

  async _logTransaction(action, details) {
    const logsDir = path.join(this.vaultPath, "Logs");
    if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });

    const logFile = path.join(logsDir, "payments.json");
    const entry = {
      timestamp: new Date().toISOString(),
      method: "bank_transfer",
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
