/**
 * Stripe Client — Payment Intents API wrapper.
 *
 * Uses Stripe API v1 with Basic auth (secret key). Supports creation,
 * capture, status check, and cancellation of Payment Intents.
 * Uses native fetch() (Node 18+). Credentials via env vars only.
 */

import fs from "fs";
import path from "path";

const STRIPE_API_BASE = "https://api.stripe.com/v1";

export class StripeClient {
  /**
   * @param {object} options
   * @param {string} [options.secretKey] — Stripe secret key (sk_test_* or sk_live_*)
   * @param {string} [options.vaultPath] — Vault path for logging only
   */
  constructor({ secretKey, vaultPath } = {}) {
    this.secretKey = secretKey || process.env.STRIPE_SECRET_KEY || "";
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";

    if (!this.secretKey) {
      console.error(
        "[stripe] STRIPE_SECRET_KEY not set. Stripe operations will fail."
      );
    }
  }

  // -------------------------------------------------------------------------
  // Auth header
  // -------------------------------------------------------------------------

  _authHeader() {
    return `Basic ${Buffer.from(`${this.secretKey}:`).toString("base64")}`;
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Create a Payment Intent (manual capture mode — funds are held, not captured).
   *
   * @param {object} params
   * @param {string} params.recipient    — Description / recipient name
   * @param {number} params.amount       — Amount in major units (e.g., 10.50)
   * @param {string} [params.currency]   — Currency code (default: usd)
   * @param {string} [params.description] — Payment description
   * @returns {{ paymentIntentId: string, clientSecret: string, status: string }}
   */
  async createPayment({ recipient, amount, currency = "usd", description }) {
    if (!this.secretKey) {
      throw new Error(
        "STRIPE_SECRET_KEY not configured. Set the environment variable."
      );
    }

    // Stripe expects amounts in cents (smallest currency unit)
    const amountCents = Math.round(amount * 100);

    const params = new URLSearchParams({
      amount: amountCents.toString(),
      currency: currency.toLowerCase(),
      capture_method: "manual",
      description: description || `Payment to ${recipient}`,
      "metadata[recipient]": recipient,
    });

    const result = await this._retry(async () => {
      const res = await fetch(`${STRIPE_API_BASE}/payment_intents`, {
        method: "POST",
        headers: {
          Authorization: this._authHeader(),
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: params.toString(),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.error?.message || `Stripe API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    await this._logTransaction("stripe_payment_created", {
      paymentIntentId: result.id,
      recipient,
      amount,
      currency,
      status: result.status,
    });

    return {
      paymentIntentId: result.id,
      clientSecret: result.client_secret,
      status: result.status,
    };
  }

  /**
   * Capture a previously created Payment Intent (finalizes the charge).
   *
   * @param {string} paymentIntentId
   * @returns {{ status: string, amount: number }}
   */
  async capturePayment(paymentIntentId) {
    if (!this.secretKey) {
      throw new Error("STRIPE_SECRET_KEY not configured.");
    }

    const result = await this._retry(async () => {
      const res = await fetch(
        `${STRIPE_API_BASE}/payment_intents/${paymentIntentId}/capture`,
        {
          method: "POST",
          headers: { Authorization: this._authHeader() },
        }
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.error?.message || `Stripe capture error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    await this._logTransaction("stripe_payment_captured", {
      paymentIntentId,
      status: result.status,
      amount: result.amount / 100,
    });

    return {
      status: result.status,
      amount: result.amount / 100,
    };
  }

  /**
   * Check Payment Intent status.
   *
   * @param {string} paymentIntentId
   * @returns {{ status: string, amount: number, currency: string, failureReason?: string }}
   */
  async checkStatus(paymentIntentId) {
    if (!this.secretKey) {
      return {
        status: "unknown",
        amount: 0,
        currency: "",
        failureReason: "STRIPE_SECRET_KEY not configured",
      };
    }

    const result = await this._retry(async () => {
      const res = await fetch(
        `${STRIPE_API_BASE}/payment_intents/${paymentIntentId}`,
        {
          headers: { Authorization: this._authHeader() },
        }
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const error = new Error(
          err.error?.message || `Stripe API error: ${res.status}`
        );
        error.status = res.status;
        throw error;
      }
      return res.json();
    });

    return {
      status: result.status,
      amount: result.amount / 100,
      currency: result.currency,
      failureReason: result.last_payment_error?.message || null,
    };
  }

  /**
   * Cancel a Payment Intent.
   *
   * @param {string} paymentIntentId
   * @returns {{ cancelled: boolean, message?: string }}
   */
  async cancelPayment(paymentIntentId) {
    if (!this.secretKey) {
      return { cancelled: false, message: "STRIPE_SECRET_KEY not configured" };
    }

    try {
      const result = await this._retry(async () => {
        const res = await fetch(
          `${STRIPE_API_BASE}/payment_intents/${paymentIntentId}/cancel`,
          {
            method: "POST",
            headers: { Authorization: this._authHeader() },
          }
        );

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          const error = new Error(
            err.error?.message || `Stripe cancel error: ${res.status}`
          );
          error.status = res.status;
          throw error;
        }
        return res.json();
      });

      await this._logTransaction("stripe_payment_cancelled", {
        paymentIntentId,
        status: result.status,
      });

      return { cancelled: true, message: `Payment ${result.status}` };
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
            `[stripe] Retry ${attempt + 1}/${maxRetries} (${status}), waiting ${Math.round(delay)}ms`
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
      method: "stripe",
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
