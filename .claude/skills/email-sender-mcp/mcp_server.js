#!/usr/bin/env node
/**
 * Email Sender MCP Server
 *
 * Exposes Gmail send/draft/reply tools via the Model Context Protocol.
 * Communicates over stdio — compatible with Claude Desktop, MCP Inspector,
 * and any other MCP client.
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

import { GmailClient } from "./gmail_client.js";

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const TOOLS = [
  {
    name: "send_email",
    description:
      "Send an email through Gmail. Supports HTML, plain text, CC/BCC, " +
      "and file attachments from the vault's Attachments/ folder.",
    inputSchema: {
      type: "object",
      properties: {
        to: { type: "string", description: "Recipient email address(es), comma-separated" },
        subject: { type: "string", description: "Email subject line" },
        body: { type: "string", description: "Email body content" },
        cc: { type: "string", description: "CC recipients (comma-separated)" },
        bcc: { type: "string", description: "BCC recipients (comma-separated)" },
        attachments: {
          type: "array",
          items: { type: "string" },
          description: "Filenames from vault Attachments/ folder to attach",
        },
        html: { type: "boolean", description: "Send as HTML (default: plain text)" },
        dry_run: { type: "boolean", description: "Validate only — do not actually send" },
      },
      required: ["to", "subject", "body"],
    },
  },
  {
    name: "draft_email",
    description:
      "Create an email draft in Gmail without sending. " +
      "Useful for review before sending.",
    inputSchema: {
      type: "object",
      properties: {
        to: { type: "string", description: "Recipient email address(es)" },
        subject: { type: "string", description: "Email subject line" },
        body: { type: "string", description: "Email body content" },
        html: { type: "boolean", description: "Draft as HTML (default: plain text)" },
      },
      required: ["to", "subject", "body"],
    },
  },
  {
    name: "reply_to_email",
    description:
      "Reply to an existing email by its Gmail message ID. " +
      "Maintains threading (In-Reply-To / References headers).",
    inputSchema: {
      type: "object",
      properties: {
        message_id: { type: "string", description: "Gmail message ID to reply to" },
        body: { type: "string", description: "Reply body content" },
        reply_all: { type: "boolean", description: "Reply to all recipients (default: sender only)" },
        html: { type: "boolean", description: "Reply as HTML (default: plain text)" },
      },
      required: ["message_id", "body"],
    },
  },
];

// ---------------------------------------------------------------------------
// Server setup
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "email-sender-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

let gmailClient;

try {
  gmailClient = new GmailClient({
    vaultPath: process.env.VAULT_PATH || "./obsidian-vault",
  });
} catch (err) {
  console.error(`[email-sender-mcp] Gmail client init failed: ${err.message}`);
  console.error("[email-sender-mcp] Tools will return errors until credentials are configured.");
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

  if (!gmailClient) {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            success: false,
            error: "Gmail client not initialized. Check OAuth credentials.",
          }),
        },
      ],
    };
  }

  try {
    let result;

    switch (name) {
      case "send_email":
        result = await handleSendEmail(args);
        break;
      case "draft_email":
        result = await handleDraftEmail(args);
        break;
      case "reply_to_email":
        result = await handleReplyToEmail(args);
        break;
      default:
        return {
          content: [
            { type: "text", text: JSON.stringify({ success: false, error: `Unknown tool: ${name}` }) },
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

async function handleSendEmail(args) {
  const { to, subject, body, cc, bcc, attachments, html, dry_run } = args;

  if (dry_run) {
    return {
      success: true,
      action: "send_email",
      mode: "dry_run",
      details: {
        to, cc, bcc, subject,
        bodyLength: body.length,
        attachments: attachments || [],
        html: !!html,
      },
      message: "Dry run — email was NOT sent. Parameters validated successfully.",
    };
  }

  const result = await gmailClient.sendEmail({
    to, cc, bcc, subject, body,
    isHtml: !!html,
    attachments: attachments || [],
  });

  return {
    success: true,
    action: "send_email",
    messageId: result.messageId,
    threadId: result.threadId,
  };
}

async function handleDraftEmail(args) {
  const { to, subject, body, html } = args;

  const result = await gmailClient.createDraft({
    to, subject, body,
    isHtml: !!html,
  });

  return {
    success: true,
    action: "draft_email",
    draftId: result.draftId,
    messageId: result.messageId,
  };
}

async function handleReplyToEmail(args) {
  const { message_id, body, reply_all, html } = args;

  const result = await gmailClient.replyToEmail({
    messageId: message_id,
    body,
    isHtml: !!html,
    replyAll: !!reply_all,
  });

  return {
    success: true,
    action: "reply_to_email",
    messageId: result.messageId,
    threadId: result.threadId,
  };
}

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[email-sender-mcp] Server running on stdio");
}

main().catch((err) => {
  console.error("[email-sender-mcp] Fatal:", err);
  process.exit(1);
});
