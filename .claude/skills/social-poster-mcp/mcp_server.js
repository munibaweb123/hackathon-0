#!/usr/bin/env node
/**
 * Social Poster MCP Server
 *
 * Exposes tools for drafting social media posts (with HITL approval)
 * and fetching post analytics across Facebook, Instagram, and Twitter/X.
 *
 * All draft_* tools create approval files — no direct posting.
 * Humans must move the file from pending-approval/ to Approved/ to trigger posting.
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

import { ApprovalHandler } from "./approval_handler.js";
import { FacebookClient } from "./facebook_client.js";
import { InstagramClient } from "./instagram_client.js";
import { TwitterClient } from "./twitter_client.js";

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const TOOLS = [
  {
    name: "draft_facebook_post",
    description:
      "Draft a Facebook Page post for approval. Creates an approval file in " +
      "pending-approval/ — the post is NOT published until a human moves " +
      "the file to the Approved/ folder.",
    inputSchema: {
      type: "object",
      properties: {
        message: {
          type: "string",
          description: "Post text (max 63,206 chars)",
        },
        link: {
          type: "string",
          description: "URL to share with the post",
        },
        image_file: {
          type: "string",
          description: "Image filename from vault Attachments/ folder",
        },
      },
      required: ["message"],
    },
  },
  {
    name: "draft_instagram_post",
    description:
      "Draft an Instagram post for approval. Instagram requires an image — " +
      "provide either image_url (public URL) or image_file (from vault). " +
      "Creates an approval file; not published until approved.",
    inputSchema: {
      type: "object",
      properties: {
        caption: {
          type: "string",
          description: "Post caption (max 2,200 chars)",
        },
        image_url: {
          type: "string",
          description: "Public URL of the image to post",
        },
        image_file: {
          type: "string",
          description: "Image filename from vault Attachments/ (requires MEDIA_HOST_URL)",
        },
      },
      required: ["caption"],
    },
  },
  {
    name: "draft_twitter_post",
    description:
      "Draft a tweet for approval. Validates the 280 character limit. " +
      "Creates an approval file; not published until approved.",
    inputSchema: {
      type: "object",
      properties: {
        text: {
          type: "string",
          description: "Tweet text (max 280 chars)",
        },
        image_file: {
          type: "string",
          description: "Image filename from vault Attachments/ folder",
        },
      },
      required: ["text"],
    },
  },
  {
    name: "get_post_analytics",
    description:
      "Get engagement metrics for a published post. " +
      "No approval needed — read-only operation.",
    inputSchema: {
      type: "object",
      properties: {
        platform: {
          type: "string",
          enum: ["facebook", "instagram", "twitter"],
          description: "Social media platform",
        },
        post_id: {
          type: "string",
          description: "Platform-specific post/tweet ID",
        },
      },
      required: ["platform", "post_id"],
    },
  },
];

// ---------------------------------------------------------------------------
// Server setup
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "social-poster-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

const vaultPath = process.env.VAULT_PATH || "./obsidian-vault";
const approvalHandler = new ApprovalHandler({ vaultPath });

// Platform clients — initialized lazily on first analytics request
let facebookClient = null;
let instagramClient = null;
let twitterClient = null;

function getFacebookClient() {
  if (!facebookClient) {
    facebookClient = new FacebookClient({ vaultPath });
  }
  return facebookClient;
}

function getInstagramClient() {
  if (!instagramClient) {
    instagramClient = new InstagramClient({ vaultPath });
  }
  return instagramClient;
}

function getTwitterClient() {
  if (!twitterClient) {
    twitterClient = new TwitterClient({ vaultPath });
  }
  return twitterClient;
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
      case "draft_facebook_post":
        result = await handleDraftFacebookPost(args);
        break;
      case "draft_instagram_post":
        result = await handleDraftInstagramPost(args);
        break;
      case "draft_twitter_post":
        result = await handleDraftTwitterPost(args);
        break;
      case "get_post_analytics":
        result = await handleGetPostAnalytics(args);
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
// Tool handlers — Draft (with approval)
// ---------------------------------------------------------------------------

async function handleDraftFacebookPost(args) {
  const { message, link, image_file } = args;

  if (message && message.length > 63206) {
    return {
      success: false,
      error: `Message exceeds Facebook limit: ${message.length}/63,206 chars`,
    };
  }

  const approval = approvalHandler.createApprovalRequest({
    platform: "facebook",
    action: "post",
    content: message,
    link,
    imageFile: image_file,
    metadata: {
      char_count: `${(message || "").length}/63206`,
    },
  });

  return {
    success: true,
    action: "draft_facebook_post",
    status: "pending_approval",
    approvalId: approval.approvalId,
    approvalFile: approval.filename,
    message:
      "Facebook post drafted. Move the approval file from pending-approval/ to Approved/ to publish.",
  };
}

async function handleDraftInstagramPost(args) {
  const { caption, image_url, image_file } = args;

  if (caption && caption.length > 2200) {
    return {
      success: false,
      error: `Caption exceeds Instagram limit: ${caption.length}/2,200 chars`,
    };
  }

  if (!image_url && !image_file) {
    return {
      success: false,
      error: "Instagram requires an image. Provide image_url or image_file.",
    };
  }

  const approval = approvalHandler.createApprovalRequest({
    platform: "instagram",
    action: "post",
    content: caption || "",
    imageFile: image_file || image_url,
    metadata: {
      image_source: image_url ? "url" : "vault",
      char_count: `${(caption || "").length}/2200`,
    },
  });

  return {
    success: true,
    action: "draft_instagram_post",
    status: "pending_approval",
    approvalId: approval.approvalId,
    approvalFile: approval.filename,
    message:
      "Instagram post drafted. Move the approval file from pending-approval/ to Approved/ to publish.",
  };
}

async function handleDraftTwitterPost(args) {
  const { text, image_file } = args;

  if (!text) {
    return { success: false, error: "Tweet text is required" };
  }

  if (text.length > 280) {
    return {
      success: false,
      error: `Tweet exceeds character limit: ${text.length}/280 chars`,
    };
  }

  const approval = approvalHandler.createApprovalRequest({
    platform: "twitter",
    action: "tweet",
    content: text,
    imageFile: image_file,
    metadata: {
      char_count: `${text.length}/280`,
    },
  });

  return {
    success: true,
    action: "draft_twitter_post",
    status: "pending_approval",
    approvalId: approval.approvalId,
    approvalFile: approval.filename,
    message:
      "Tweet drafted. Move the approval file from pending-approval/ to Approved/ to publish.",
  };
}

// ---------------------------------------------------------------------------
// Tool handler — Analytics (no approval needed)
// ---------------------------------------------------------------------------

async function handleGetPostAnalytics(args) {
  const { platform, post_id } = args;

  switch (platform) {
    case "facebook": {
      const client = getFacebookClient();
      const metrics = await client.getPostInsights(post_id);
      return {
        success: true,
        platform: "facebook",
        postId: post_id,
        metrics,
      };
    }
    case "instagram": {
      const client = getInstagramClient();
      const metrics = await client.getPostInsights(post_id);
      return {
        success: true,
        platform: "instagram",
        postId: post_id,
        metrics,
      };
    }
    case "twitter": {
      const client = getTwitterClient();
      const metrics = await client.getTweetMetrics(post_id);
      return {
        success: true,
        platform: "twitter",
        postId: post_id,
        metrics,
      };
    }
    default:
      return {
        success: false,
        error: `Unsupported platform: ${platform}. Use facebook, instagram, or twitter.`,
      };
  }
}

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[social-poster-mcp] Server running on stdio");
}

main().catch((err) => {
  console.error("[social-poster-mcp] Fatal:", err);
  process.exit(1);
});
