/**
 * Fraud Detection — analyzes payment requests for suspicious patterns.
 *
 * Pure-logic module with no API or approval dependencies.
 * Reads payment history from Logs/payments.json to detect:
 *   1. New (first-time) recipients
 *   2. High velocity (>3 payments/hour to same recipient)
 *   3. Amount anomalies (>2× historical average)
 *   4. Daily spending limit exceeded
 *   5. Possible duplicate transactions
 */

import fs from "fs";
import path from "path";

const DEFAULT_DAILY_LIMIT = 5000;
const VELOCITY_THRESHOLD = 3; // max payments per hour to same recipient
const ANOMALY_MULTIPLIER = 2; // flag if > 2× average
const DUPLICATE_WINDOW_MS = 10 * 60 * 1000; // 10 minutes
const HISTORY_DAYS = 30;

export class FraudDetector {
  /**
   * @param {object} options
   * @param {string} [options.vaultPath]   — Obsidian vault path
   * @param {number} [options.dailyLimit]  — Max cumulative daily spend
   */
  constructor({ vaultPath, dailyLimit } = {}) {
    this.vaultPath = vaultPath || process.env.VAULT_PATH || "./obsidian-vault";
    this.dailyLimit =
      dailyLimit ||
      Number(process.env.PAYMENT_DAILY_LIMIT) ||
      DEFAULT_DAILY_LIMIT;
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Analyze a payment for fraud indicators.
   *
   * @param {object} payment
   * @param {string} payment.recipient  — Payee name or identifier
   * @param {number} payment.amount     — Payment amount
   * @param {string} [payment.method]   — Payment method
   * @param {string} [payment.reference] — Invoice/reference number
   * @param {string} [payment.currency] — Currency code
   * @returns {{ safe: boolean, flags: string[], riskScore: number, details: object }}
   */
  analyze(payment) {
    const history = this._loadHistory();
    const flags = [];
    const details = {};

    // 1. New recipient check
    if (!this._isKnownRecipient(payment.recipient, history)) {
      flags.push("new_recipient");
      details.new_recipient =
        "First-time payment to this recipient. Extra scrutiny recommended.";
    }

    // 2. Velocity check
    const recentCount = this._getRecentPaymentCount(
      payment.recipient,
      history,
      60 * 60 * 1000 // 1 hour
    );
    if (recentCount >= VELOCITY_THRESHOLD) {
      flags.push("high_velocity");
      details.high_velocity = `${recentCount} payments to "${payment.recipient}" in the last hour (threshold: ${VELOCITY_THRESHOLD})`;
    }

    // 3. Amount anomaly
    const avgAmount = this._getAverageAmount(payment.recipient, history);
    if (avgAmount > 0 && payment.amount > avgAmount * ANOMALY_MULTIPLIER) {
      flags.push("amount_anomaly");
      details.amount_anomaly = `Amount ${payment.amount} is ${(payment.amount / avgAmount).toFixed(1)}× the average (${avgAmount.toFixed(2)}) for this recipient`;
    }

    // 4. Daily limit
    const todayTotal = this._getTodayTotal(history);
    if (todayTotal + payment.amount > this.dailyLimit) {
      flags.push("daily_limit_exceeded");
      details.daily_limit_exceeded = `Today's total would be ${(todayTotal + payment.amount).toFixed(2)} (limit: ${this.dailyLimit})`;
    }

    // 5. Duplicate detection
    const duplicate = this._findDuplicate(payment, history);
    if (duplicate) {
      flags.push("possible_duplicate");
      details.possible_duplicate = `Similar payment found at ${duplicate.timestamp}: ${duplicate.recipient} / ${duplicate.amount} / ${duplicate.reference || "no ref"}`;
    }

    // Compute risk score (0-100)
    const riskScore = this._computeRiskScore(flags, payment);

    return {
      safe: flags.length === 0,
      flags,
      riskScore,
      details,
    };
  }

  // -------------------------------------------------------------------------
  // Private — history loading
  // -------------------------------------------------------------------------

  _loadHistory() {
    const logFile = path.join(this.vaultPath, "Logs", "payments.json");

    if (!fs.existsSync(logFile)) {
      return [];
    }

    try {
      const raw = JSON.parse(fs.readFileSync(logFile, "utf-8"));
      const cutoff = Date.now() - HISTORY_DAYS * 24 * 60 * 60 * 1000;

      return raw.filter((entry) => {
        const ts = new Date(entry.timestamp).getTime();
        return ts > cutoff;
      });
    } catch {
      return [];
    }
  }

  // -------------------------------------------------------------------------
  // Private — individual checks
  // -------------------------------------------------------------------------

  _isKnownRecipient(recipient, history) {
    const normalized = recipient.toLowerCase().trim();
    return history.some(
      (entry) =>
        entry.recipient &&
        entry.recipient.toLowerCase().trim() === normalized &&
        entry.status !== "failed" &&
        entry.status !== "cancelled"
    );
  }

  _getRecentPaymentCount(recipient, history, windowMs) {
    const normalized = recipient.toLowerCase().trim();
    const cutoff = Date.now() - windowMs;

    return history.filter((entry) => {
      const ts = new Date(entry.timestamp).getTime();
      return (
        ts > cutoff &&
        entry.recipient &&
        entry.recipient.toLowerCase().trim() === normalized
      );
    }).length;
  }

  _getAverageAmount(recipient, history) {
    const normalized = recipient.toLowerCase().trim();
    const payments = history.filter(
      (entry) =>
        entry.recipient &&
        entry.recipient.toLowerCase().trim() === normalized &&
        typeof entry.amount === "number" &&
        entry.status !== "failed" &&
        entry.status !== "cancelled"
    );

    if (payments.length === 0) return 0;

    const sum = payments.reduce((total, p) => total + p.amount, 0);
    return sum / payments.length;
  }

  _getTodayTotal(history) {
    const today = new Date().toISOString().split("T")[0];

    return history
      .filter((entry) => {
        const entryDate = entry.timestamp?.split("T")[0];
        return (
          entryDate === today &&
          entry.status !== "failed" &&
          entry.status !== "cancelled"
        );
      })
      .reduce((sum, entry) => sum + (entry.amount || 0), 0);
  }

  _findDuplicate(payment, history) {
    const cutoff = Date.now() - DUPLICATE_WINDOW_MS;
    const normalized = payment.recipient.toLowerCase().trim();

    return history.find((entry) => {
      const ts = new Date(entry.timestamp).getTime();
      return (
        ts > cutoff &&
        entry.recipient &&
        entry.recipient.toLowerCase().trim() === normalized &&
        entry.amount === payment.amount &&
        (payment.reference
          ? entry.reference === payment.reference
          : true)
      );
    });
  }

  // -------------------------------------------------------------------------
  // Risk score computation
  // -------------------------------------------------------------------------

  _computeRiskScore(flags, payment) {
    let score = 0;

    const weights = {
      new_recipient: 25,
      high_velocity: 30,
      amount_anomaly: 20,
      daily_limit_exceeded: 15,
      possible_duplicate: 35,
    };

    for (const flag of flags) {
      score += weights[flag] || 10;
    }

    // Scale by amount (larger payments = higher base risk)
    if (payment.amount > 1000) score += 5;
    if (payment.amount > 5000) score += 10;
    if (payment.amount > 10000) score += 15;

    return Math.min(score, 100);
  }
}
