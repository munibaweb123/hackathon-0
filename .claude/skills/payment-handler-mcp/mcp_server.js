#!/usr/bin/env node
/**
 * Payment Handler MCP Server
 *
 * Secure payment workflow with HITL approval for ALL payments.
 * Supports bank transfer, PayPal, and Stripe. Every payment request
 * goes through fraud detection → approval file → human review.
 *
 *   npx @modelcontextprotocol/inspector node mcp_server.js
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import dotenv from "dotenv";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

// Load .env — search upward from script dir
const __dirname = path.dirname(fileURLToPath(import.meta.url));
for (let dir = __dirname, i = 0; i < 6; i++, dir = path.dirname(dir)) {
  dotenv.config({ path: path.join(dir, ".env") });
}

import { FraudDetector } from "./fraud_detection.js";
import { PaymentApprovalValidator } from "./approval_validator.js";
import { BankTransferClient } from "./payment_clients/bank_transfer.js";
import { PayPalClient } from "./payment_clients/paypal_client.js";
import { StripeClient } from "./payment_clients/stripe_client.js";

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const TOOLS = [
  {
    name: "draft_payment",
    description:
      "Draft a payment for human approval. Runs fraud detection first, " +
      "then creates an approval file in pending-approval/. " +
      "The payment is NEVER executed automatically — a human must " +
      "move the file to Approved/ to proceed.",
    inputSchema: {
      type: "object",
      properties: {
        recipient: {
          type: "string",
          description: "Payee name or identifier",
        },
        amount: {
          type: "number",
          description: "Payment amount (in major currency units, e.g. 150.00)",
        },
        method: {
          type: "string",
          enum: ["bank_transfer", "paypal", "stripe"],
          description: "Payment method",
        },
        reference: {
          type: "string",
          description: "Invoice or reference number",
        },
        category: {
          type: "string",
          description: "Payment category (e.g., vendor, salary, subscription)",
        },
        currency: {
          type: "string",
          description: "Currency code (default: USD)",
        },
      },
      required: ["recipient", "amount", "method"],
    },
  },
  {
    name: "verify_payment_status",
    description:
      "Check the status of a payment by its approval ID or provider transaction ID. " +
      "Read-only — no approval needed.",
    inputSchema: {
      type: "object",
      properties: {
        payment_id: {
          type: "string",
          description: "Approval ID (8-char hex) or provider transaction ID",
        },
        method: {
          type: "string",
          enum: ["bank_transfer", "paypal", "stripe"],
          description: "Payment method (helps narrow the search). If omitted, tries all.",
        },
      },
      required: ["payment_id"],
    },
  },
  {
    name: "cancel_pending_payment",
    description:
      "Cancel a pending payment. If still in pending-approval/, " +
      "moves the file to Rejected/. If already sent to a provider, " +
      "attempts to cancel with the provider.",
    inputSchema: {
      type: "object",
      properties: {
        payment_id: {
          type: "string",
          description: "Approval ID or provider transaction ID",
        },
      },
      required: ["payment_id"],
    },
  },
  {
    name: "list_scheduled_payments",
    description:
      "List all pending payment approvals awaiting human review. " +
      "Read-only — no approval needed.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

// ---------------------------------------------------------------------------
// Server setup
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "payment-handler-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

const vaultPath = process.env.VAULT_PATH || "./obsidian-vault";
const fraudDetector = new FraudDetector({ vaultPath });
const approvalValidator = new PaymentApprovalValidator({ vaultPath });

// Lazily initialized payment clients
let bankClient = null;
let paypalClient = null;
let stripeClient = null;

function getBankClient() {
  if (!bankClient) bankClient = new BankTransferClient({ vaultPath });
  return bankClient;
}

function getPayPalClient() {
  if (!paypalClient) paypalClient = new PayPalClient({ vaultPath });
  return paypalClient;
}

function getStripeClient() {
  if (!stripeClient) stripeClient = new StripeClient({ vaultPath });
  return stripeClient;
}

// ---------------------------------------------------------------------------
// List tools
// ---------------------------------------------------------------------------

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools: TOOLS };
});

// ---------------------------------------------------------------------------
// Call tool
// ---------------------------------------------------------------------------

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result;

    switch (name) {
      case "draft_payment":
        result = await handleDraftPayment(args);
        break;
      case "verify_payment_status":
        result = await handleVerifyPaymentStatus(args);
        break;
      case "cancel_pending_payment":
        result = await handleCancelPendingPayment(args);
        break;
      case "list_scheduled_payments":
        result = await handleListScheduledPayments();
        break;
      default:
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                error: `Unknown tool: ${name}`,
              }),
            },
          ],
          isError: true,
        };
    }

    return {
      content: [{ type: "text", text: JSON.stringify(result) }],
    };
  } catch (err) {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            success: false,
            error: err.message,
            tool: name,
          }),
        },
      ],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

async function handleDraftPayment(args) {
  const {
    recipient,
    amount,
    method,
    reference,
    category,
    currency = "USD",
  } = args;

  // Validate inputs
  if (amount <= 0) {
    return { success: false, error: "Payment amount must be positive" };
  }

  if (!["bank_transfer", "paypal", "stripe"].includes(method)) {
    return {
      success: false,
      error: `Invalid method: ${method}. Use bank_transfer, paypal, or stripe.`,
    };
  }

  // 1. Run fraud detection
  const fraudResult = fraudDetector.analyze({
    recipient,
    amount,
    method,
    reference,
    currency,
  });

  // 2. Create approval file (ALWAYS — no auto-execute)
  const approval = approvalValidator.createPaymentApproval({
    recipient,
    amount,
    method,
    reference,
    category,
    currency,
    fraudFlags: fraudResult.flags,
    riskScore: fraudResult.riskScore,
    fraudDetails: fraudResult.details,
  });

  // 3. Log the draft attempt
  logPaymentAttempt("draft_payment", {
    approvalId: approval.approvalId,
    recipient,
    amount,
    currency,
    method,
    reference,
    category,
    riskScore: fraudResult.riskScore,
    fraudFlags: fraudResult.flags,
    status: "pending_approval",
  });

  return {
    success: true,
    action: "draft_payment",
    status: "pending_approval",
    approvalId: approval.approvalId,
    approvalFile: approval.filename,
    riskLevel: approval.riskLevel,
    riskScore: fraudResult.riskScore,
    fraudFlags: fraudResult.flags,
    safe: fraudResult.safe,
    message: fraudResult.safe
      ? "Payment drafted for approval. Move the file from pending-approval/ to Approved/ to execute."
      : `Payment drafted with ${fraudResult.flags.length} security flag(s). Review carefully before approving.`,
  };
}

async function handleVerifyPaymentStatus(args) {
  const { payment_id, method } = args;

  // First check approval status
  const approvalStatus = approvalValidator.checkPaymentApproval(payment_id);

  if (
    approvalStatus.status !== "not_found" &&
    approvalStatus.status !== "approved"
  ) {
    return {
      success: true,
      action: "verify_payment_status",
      paymentId: payment_id,
      approvalStatus: approvalStatus.status,
      expiresIn: approvalStatus.expiresIn || null,
      providerStatus: null,
      message:
        approvalStatus.status === "pending"
          ? `Payment is awaiting approval (expires in ${approvalStatus.expiresIn})`
          : `Payment was ${approvalStatus.status}`,
    };
  }

  // Try provider status checks
  const methods = method
    ? [method]
    : ["stripe", "paypal", "bank_transfer"];

  for (const m of methods) {
    try {
      let status;
      switch (m) {
        case "stripe":
          status = await getStripeClient().checkStatus(payment_id);
          break;
        case "paypal":
          status = await getPayPalClient().checkStatus(payment_id);
          break;
        case "bank_transfer":
          status = await getBankClient().checkStatus(payment_id);
          break;
      }

      if (status && status.status !== "unknown") {
        return {
          success: true,
          action: "verify_payment_status",
          paymentId: payment_id,
          method: m,
          approvalStatus: approvalStatus.status,
          providerStatus: status.status,
          failureReason: status.failureReason || null,
        };
      }
    } catch {
      // Try next method
    }
  }

  return {
    success: true,
    action: "verify_payment_status",
    paymentId: payment_id,
    approvalStatus: approvalStatus.status,
    providerStatus: null,
    message: "Payment not found in any provider. Check the payment ID.",
  };
}

async function handleCancelPendingPayment(args) {
  const { payment_id } = args;

  // Try to cancel in approval system first
  const cancelResult = approvalValidator.cancelApproval(payment_id);

  if (cancelResult.cancelled) {
    logPaymentAttempt("cancel_payment", {
      paymentId: payment_id,
      source: "approval_system",
      status: "cancelled",
    });

    return {
      success: true,
      action: "cancel_pending_payment",
      paymentId: payment_id,
      ...cancelResult,
    };
  }

  // If not found in approval system, try providers
  const providers = [
    { name: "stripe", client: getStripeClient() },
    { name: "paypal", client: getPayPalClient() },
    { name: "bank_transfer", client: getBankClient() },
  ];

  for (const { name, client } of providers) {
    try {
      let result;
      switch (name) {
        case "stripe":
          result = await client.cancelPayment(payment_id);
          break;
        case "paypal":
          result = await client.cancelPayment(payment_id);
          break;
        case "bank_transfer":
          result = await client.cancelTransfer(payment_id);
          break;
      }

      if (result && result.cancelled) {
        logPaymentAttempt("cancel_payment", {
          paymentId: payment_id,
          source: name,
          status: "cancelled",
        });

        return {
          success: true,
          action: "cancel_pending_payment",
          paymentId: payment_id,
          provider: name,
          ...result,
        };
      }
    } catch {
      // Try next provider
    }
  }

  return {
    success: false,
    action: "cancel_pending_payment",
    paymentId: payment_id,
    message:
      "Could not cancel — payment not found in approval system or any provider.",
  };
}

async function handleListScheduledPayments() {
  const pending = approvalValidator.listPendingPayments();

  return {
    success: true,
    action: "list_scheduled_payments",
    count: pending.length,
    payments: pending,
  };
}

// ---------------------------------------------------------------------------
// Payment logging
// ---------------------------------------------------------------------------

function logPaymentAttempt(action, details) {
  const logsDir = path.join(vaultPath, "Logs");
  if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });

  const logFile = path.join(logsDir, "payments.json");

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

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[payment-handler-mcp] Server running on stdio");
}

main().catch((err) => {
  console.error("[payment-handler-mcp] Fatal:", err);
  process.exit(1);
});
