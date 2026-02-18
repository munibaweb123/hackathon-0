/**
 * PayPal Client — REST API v2 wrapper for PayPal Payouts.
 *
 * Uses client_credentials OAuth2 flow. Access tokens cached in memory only —
 * never stored in vault or filesystem. Uses native fetch() (Node 18+).
 */

import fs from "fs";
import path from "path";

const SANDBOX_URL = "https://api-m.sandbox.paypal.com";
const PRODUCTION_URL = "https://api-m.paypal.com";

export class PayPalClient {
  /**
   * @param {object} options
   * @param {string} [options.clientId]     — PayPal client ID
   * @param {string} [options.clientSecret] — PayPal client secret
   * @param {boolean} [options.sandbox]     — Use sandbox (default: true)
   * @param {string} [options.vaultPath]    — Vault path for logging only
   */
  constructor({ clientId, clientSecret, sandbox, vaultPath } = {}) {
    this.clientId = clientId || process.env.PAYPAL_CLIENT_ID || "";
    this.clientSecret = clientSecret || process.env.PAYPAL_CLIENT_SECRET || "";
    this.sandbox =
      sandbox !== undefined
        ? sandbox
        : process.env.PAYPAL_SANDBOX !== "false";
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";

    this.baseUrl = this.sandbox ? SANDBOX_URL : PRODUCTION_URL;
    this._accessToken = null;
    this._tokenExpiry = 0;

    if (!this.clientId || !this.clientSecret) {
      console.error(
        "[paypal] PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET not set. PayPal operations will fail."
      );
    }
  }

  // -------------------------------------------------------------------------
  // Authentication — tokens cached in memory only
  // -------------------------------------------------------------------------

  async _getAccessToken() {
    // Return cached token if still valid (with 60s buffer)
    if (this._accessToken && Date.now() < this._tokenExpiry - 60000) {
      return this._accessToken;
    }

    const credentials = Buffer.from(
      `${this.clientId}:${this.clientSecret}`
    ).toString("base64");

    const res = await fetch(`${this.baseUrl}/v1/oauth2/token`, {
      method: "POST",
      headers: {
        Authorization: `Basic ${credentials}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: "grant_type=client_credentials",
    });

    if (!res.ok) {
      throw new Error(`PayPal auth failed: ${res.status} ${res.statusText}`);
    }

    const data = await res.json();
    this._accessToken = data.access_token;
    this._tokenExpiry = Date.now() + data.expires_in * 1000;

    return this._accessToken;
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Create a PayPal payout.
   *
   * @param {object} params
   * @param {string} params.recipient    — PayPal email address
   * @param {number} params.amount       — Payment amount
   * @param {string} [params.currency]   — Currency code (default: USD)
   * @param {string} [params.reference]  — Sender batch ID / reference
   * @returns {{ payoutId: string, batchId: string, status: string }}
   */
  async createPayment({ recipient, amount, currency = "USD", reference }) {
    if (!this.clientId || !this.clientSecret) {
      throw new Error(
        "PayPal credentials not configured. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET."
      );
    }

    const token = await this._getAccessToken();
    const batchId = reference || `PAYOUT-${Date.now()}`;

    const payload = {
      sender_batch_header: {
        sender_batch_id: batchId,
        email_subject: "You have a payment",
        email_message: `Payment of ${currency} ${amount}`,
      },
      items: [
        {
          recipient_type: "EMAIL",
          amount: {
            value: amount.toFixed(2),
            currency,
          },
          receiver: recipient,
          note: reference || "Payment",
          sender_item_id: `ITEM-${Date.now()}`,
        },
      ],
    };

    const result = await this._retry(async () => {
      const res = await fetch(`${this.baseUrl}/v1/payments/payouts`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.message || err.name || `PayPal API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    const payoutId =
      result.batch_header?.payout_batch_id || `pp_${Date.now()}`;

    await this._logTransaction("paypal_payout_created", {
      payoutId,
      batchId,
      recipient,
      amount,
      currency,
      status: result.batch_header?.batch_status || "PENDING",
    });

    return {
      payoutId,
      batchId,
      status: result.batch_header?.batch_status || "PENDING",
    };
  }

  /**
   * Check payout status.
   *
   * @param {string} payoutId — PayPal payout batch ID
   * @returns {{ status: string, failureReason?: string }}
   */
  async checkStatus(payoutId) {
    if (!this.clientId || !this.clientSecret) {
      return { status: "unknown", failureReason: "PayPal credentials not configured" };
    }

    const token = await this._getAccessToken();

    const result = await this._retry(async () => {
      const res = await fetch(
        `${this.baseUrl}/v1/payments/payouts/${payoutId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.message || `PayPal API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    const status = result.batch_header?.batch_status || "UNKNOWN";
    const errors = result.items
      ?.filter((i) => i.transaction_status === "FAILED")
      .map((i) => i.errors?.message)
      .filter(Boolean);

    return {
      status,
      failureReason: errors?.length > 0 ? errors.join("; ") : null,
    };
  }

  /**
   * Cancel a pending payout (if still in PENDING status).
   *
   * @param {string} payoutId
   * @returns {{ cancelled: boolean, message?: string }}
   */
  async cancelPayment(payoutId) {
    try {
      // First check if it's still cancellable
      const status = await this.checkStatus(payoutId);

      if (status.status !== "PENDING") {
        return {
          cancelled: false,
          message: `Cannot cancel — payout is ${status.status}`,
        };
      }

      // PayPal doesn't have a direct cancel for payouts that are pending processing
      // But we can try to cancel individual items
      const token = await this._getAccessToken();

      // Get payout items
      const res = await fetch(
        `${this.baseUrl}/v1/payments/payouts/${payoutId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (!res.ok) {
        return { cancelled: false, message: "Failed to fetch payout details" };
      }

      const data = await res.json();
      const items = data.items || [];
      let cancelledCount = 0;

      for (const item of items) {
        if (item.transaction_status === "UNCLAIMED") {
          try {
            const cancelRes = await fetch(
              `${this.baseUrl}/v1/payments/payouts-item/${item.payout_item_id}/cancel`,
              {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
              }
            );
            if (cancelRes.ok) cancelledCount++;
          } catch {
            // Continue trying other items
          }
        }
      }

      await this._logTransaction("paypal_payout_cancelled", {
        payoutId,
        cancelledItems: cancelledCount,
      });

      return {
        cancelled: cancelledCount > 0,
        message: `Cancelled ${cancelledCount}/${items.length} payout items`,
      };
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
            `[paypal] Retry ${attempt + 1}/${maxRetries} (${status}), waiting ${Math.round(delay)}ms`
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
      method: "paypal",
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
