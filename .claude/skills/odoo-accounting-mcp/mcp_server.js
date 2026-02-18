#!/usr/bin/env node
/**
 * Odoo Accounting MCP Server
 *
 * Exposes accounting tools for Odoo Community Edition (v19+) via MCP.
 * Financial write operations require HITL approval (pending-approval/ → Approved/).
 * Read-only queries (balances, unpaid invoices) execute directly.
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
import path from "path";
import { fileURLToPath } from "url";

// Load .env — search upward from script dir
const __dirname = path.dirname(fileURLToPath(import.meta.url));
for (let dir = __dirname, i = 0; i < 6; i++, dir = path.dirname(dir)) {
  dotenv.config({ path: path.join(dir, ".env") });
}

import { OdooClient } from "./odoo_client.js";
import { InvoiceGenerator } from "./invoice_generator.js";
import { ApprovalHandler } from "../social-poster-mcp/approval_handler.js";

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const TOOLS = [
  {
    name: "create_invoice",
    description:
      "Create a customer invoice in Odoo. Requires HITL approval — " +
      "creates an approval file in pending-approval/ before execution.",
    inputSchema: {
      type: "object",
      properties: {
        partner_name: {
          type: "string",
          description: "Customer name (auto-resolved or created in Odoo)",
        },
        line_items: {
          type: "array",
          items: {
            type: "object",
            properties: {
              description: { type: "string" },
              quantity: { type: "number" },
              unit_price: { type: "number" },
            },
            required: ["description", "quantity", "unit_price"],
          },
          description: "Invoice line items",
        },
        due_date: {
          type: "string",
          description: "Due date (YYYY-MM-DD)",
        },
        currency: {
          type: "string",
          description: "Currency code (e.g., USD, EUR, PKR). Defaults to company currency.",
        },
      },
      required: ["partner_name", "line_items"],
    },
  },
  {
    name: "record_payment",
    description:
      "Record a payment against an existing invoice. Requires HITL approval.",
    inputSchema: {
      type: "object",
      properties: {
        invoice_id: {
          type: "number",
          description: "Odoo invoice ID (account.move)",
        },
        amount: {
          type: "number",
          description: "Payment amount",
        },
        payment_date: {
          type: "string",
          description: "Payment date (YYYY-MM-DD). Defaults to today.",
        },
        method: {
          type: "string",
          enum: ["bank", "cash", "check"],
          description: "Payment method (default: bank)",
        },
      },
      required: ["invoice_id", "amount"],
    },
  },
  {
    name: "create_expense",
    description:
      "Log an expense in Odoo. Requires HITL approval.",
    inputSchema: {
      type: "object",
      properties: {
        category: {
          type: "string",
          description: "Expense category (e.g., Travel, Office Supplies, Internet)",
        },
        amount: {
          type: "number",
          description: "Expense amount",
        },
        description: {
          type: "string",
          description: "Expense description",
        },
        date: {
          type: "string",
          description: "Expense date (YYYY-MM-DD). Defaults to today.",
        },
      },
      required: ["category", "amount", "description"],
    },
  },
  {
    name: "get_account_balance",
    description:
      "Get current balance for an account type. Read-only — no approval needed.",
    inputSchema: {
      type: "object",
      properties: {
        account_type: {
          type: "string",
          enum: ["receivable", "payable", "bank", "cash"],
          description: "Account type to query",
        },
      },
      required: ["account_type"],
    },
  },
  {
    name: "list_unpaid_invoices",
    description:
      "List all unpaid or partially paid customer invoices. Read-only — no approval needed.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "create_partner",
    description:
      "Create a new customer/vendor in Odoo. Requires HITL approval.",
    inputSchema: {
      type: "object",
      properties: {
        name: {
          type: "string",
          description: "Partner name (company or individual)",
        },
        email: {
          type: "string",
          description: "Email address",
        },
        phone: {
          type: "string",
          description: "Phone number",
        },
        address: {
          type: "string",
          description: "Full address",
        },
      },
      required: ["name"],
    },
  },
];

// ---------------------------------------------------------------------------
// Server setup
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "odoo-accounting-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

const vaultPath = process.env.VAULT_PATH || "./obsidian-vault";
const approvalHandler = new ApprovalHandler({ vaultPath });

// Lazily initialized Odoo client and invoice generator
let odooClient = null;
let invoiceGen = null;

function getOdooClient() {
  if (!odooClient) {
    odooClient = new OdooClient({ vaultPath });
  }
  return odooClient;
}

function getInvoiceGenerator() {
  if (!invoiceGen) {
    invoiceGen = new InvoiceGenerator(getOdooClient(), vaultPath);
  }
  return invoiceGen;
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
      case "create_invoice":
        result = await handleCreateInvoice(args);
        break;
      case "record_payment":
        result = await handleRecordPayment(args);
        break;
      case "create_expense":
        result = await handleCreateExpense(args);
        break;
      case "get_account_balance":
        result = await handleGetAccountBalance(args);
        break;
      case "list_unpaid_invoices":
        result = await handleListUnpaidInvoices(args);
        break;
      case "create_partner":
        result = await handleCreatePartner(args);
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
// Tool handlers — HITL (approval required)
// ---------------------------------------------------------------------------

async function handleCreateInvoice(args) {
  const { partner_name, line_items, due_date, currency } = args;

  if (!line_items || line_items.length === 0) {
    return { success: false, error: "At least one line item is required" };
  }

  const total = line_items.reduce(
    (sum, item) => sum + (item.quantity || 1) * (item.unit_price || 0),
    0
  );

  const linesSummary = line_items
    .map(
      (item) =>
        `  - ${item.description}: ${item.quantity} × ${item.unit_price} = ${(item.quantity || 1) * (item.unit_price || 0)}`
    )
    .join("\n");

  const content = [
    `Customer: ${partner_name}`,
    `Total: ${currency || "default"} ${total.toFixed(2)}`,
    `Due: ${due_date || "default terms"}`,
    "",
    "Line items:",
    linesSummary,
  ].join("\n");

  const approval = approvalHandler.createApprovalRequest({
    platform: "odoo",
    action: "create_invoice",
    content,
    metadata: {
      partner_name,
      total: total.toFixed(2),
      currency: currency || "company_default",
      line_count: `${line_items.length}`,
      due_date: due_date || "default",
      risk_level_override: "high",
    },
  });

  return {
    success: true,
    action: "create_invoice",
    status: "pending_approval",
    approvalId: approval.approvalId,
    approvalFile: approval.filename,
    estimatedTotal: total,
    message:
      "Invoice drafted for approval. Move the file from pending-approval/ to Approved/ to create in Odoo.",
  };
}

async function handleRecordPayment(args) {
  const { invoice_id, amount, payment_date, method } = args;

  if (amount <= 0) {
    return { success: false, error: "Payment amount must be positive" };
  }

  const content = [
    `Invoice ID: ${invoice_id}`,
    `Amount: ${amount}`,
    `Method: ${method || "bank"}`,
    `Date: ${payment_date || "today"}`,
  ].join("\n");

  const approval = approvalHandler.createApprovalRequest({
    platform: "odoo",
    action: "record_payment",
    content,
    metadata: {
      invoice_id: `${invoice_id}`,
      amount: `${amount}`,
      method: method || "bank",
      payment_date: payment_date || new Date().toISOString().split("T")[0],
      risk_level_override: "high",
    },
  });

  return {
    success: true,
    action: "record_payment",
    status: "pending_approval",
    approvalId: approval.approvalId,
    approvalFile: approval.filename,
    message:
      "Payment recorded for approval. Move the file from pending-approval/ to Approved/ to process.",
  };
}

async function handleCreateExpense(args) {
  const { category, amount, description, date } = args;

  if (amount <= 0) {
    return { success: false, error: "Expense amount must be positive" };
  }

  const content = [
    `Category: ${category}`,
    `Amount: ${amount}`,
    `Description: ${description}`,
    `Date: ${date || "today"}`,
  ].join("\n");

  const approval = approvalHandler.createApprovalRequest({
    platform: "odoo",
    action: "create_expense",
    content,
    metadata: {
      category,
      amount: `${amount}`,
      description,
      date: date || new Date().toISOString().split("T")[0],
      risk_level_override: "medium",
    },
  });

  return {
    success: true,
    action: "create_expense",
    status: "pending_approval",
    approvalId: approval.approvalId,
    approvalFile: approval.filename,
    message:
      "Expense drafted for approval. Move the file from pending-approval/ to Approved/ to record.",
  };
}

async function handleCreatePartner(args) {
  const { name, email, phone, address } = args;

  const content = [
    `Name: ${name}`,
    email ? `Email: ${email}` : null,
    phone ? `Phone: ${phone}` : null,
    address ? `Address: ${address}` : null,
  ]
    .filter(Boolean)
    .join("\n");

  const approval = approvalHandler.createApprovalRequest({
    platform: "odoo",
    action: "create_partner",
    content,
    metadata: {
      name,
      email: email || "",
      phone: phone || "",
      risk_level_override: "medium",
    },
  });

  return {
    success: true,
    action: "create_partner",
    status: "pending_approval",
    approvalId: approval.approvalId,
    approvalFile: approval.filename,
    message:
      "Partner creation pending approval. Move the file from pending-approval/ to Approved/ to create.",
  };
}

// ---------------------------------------------------------------------------
// Tool handlers — Read-only (no approval needed)
// ---------------------------------------------------------------------------

async function handleGetAccountBalance(args) {
  const { account_type } = args;

  const gen = getInvoiceGenerator();
  const result = await gen.getAccountBalance(account_type);

  return {
    success: true,
    action: "get_account_balance",
    ...result,
  };
}

async function handleListUnpaidInvoices() {
  const gen = getInvoiceGenerator();
  const invoices = await gen.getUnpaidInvoices();

  return {
    success: true,
    action: "list_unpaid_invoices",
    count: invoices.length,
    invoices,
  };
}

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[odoo-accounting-mcp] Server running on stdio");
}

main().catch((err) => {
  console.error("[odoo-accounting-mcp] Fatal:", err);
  process.exit(1);
});
