import { NextRequest, NextResponse } from "next/server";

const FINANCIAL_MCP_URL =
  process.env.FINANCIAL_MCP_URL || "http://localhost:8001";

export async function GET(request: NextRequest) {
  const action = request.nextUrl.searchParams.get("action");

  try {
    switch (action) {
      case "status": {
        const res = await fetch(`${FINANCIAL_MCP_URL}/xero/status`);
        if (!res.ok) {
          return NextResponse.json(
            { connected: false, status: "auth_required" },
            { status: 200 }
          );
        }
        return NextResponse.json(await res.json());
      }

      case "invoices": {
        const status = request.nextUrl.searchParams.get("status") || "";
        const fromDate = request.nextUrl.searchParams.get("fromDate") || "";
        const toDate = request.nextUrl.searchParams.get("toDate") || "";
        const params = new URLSearchParams();
        if (status) params.set("status", status);
        if (fromDate) params.set("fromDate", fromDate);
        if (toDate) params.set("toDate", toDate);
        const res = await fetch(
          `${FINANCIAL_MCP_URL}/xero/invoices?${params.toString()}`
        );
        if (!res.ok)
          return NextResponse.json(
            { error: "Failed to fetch invoices" },
            { status: res.status }
          );
        return NextResponse.json(await res.json());
      }

      case "contacts": {
        const search = request.nextUrl.searchParams.get("search") || "";
        const params = search ? `?search=${encodeURIComponent(search)}` : "";
        const res = await fetch(`${FINANCIAL_MCP_URL}/xero/contacts${params}`);
        if (!res.ok)
          return NextResponse.json(
            { error: "Failed to fetch contacts" },
            { status: res.status }
          );
        return NextResponse.json(await res.json());
      }

      case "transactions": {
        const uncategorized =
          request.nextUrl.searchParams.get("uncategorized") || "true";
        const res = await fetch(
          `${FINANCIAL_MCP_URL}/xero/bank-transactions?uncategorized=${uncategorized}`
        );
        if (!res.ok)
          return NextResponse.json(
            { error: "Failed to fetch transactions" },
            { status: res.status }
          );
        return NextResponse.json(await res.json());
      }

      case "summary": {
        const periodStart =
          request.nextUrl.searchParams.get("periodStart") || "";
        const periodEnd = request.nextUrl.searchParams.get("periodEnd") || "";
        const res = await fetch(
          `${FINANCIAL_MCP_URL}/xero/summary?periodStart=${periodStart}&periodEnd=${periodEnd}`
        );
        if (!res.ok)
          return NextResponse.json(
            { error: "Failed to fetch summary" },
            { status: res.status }
          );
        return NextResponse.json(await res.json());
      }

      default:
        return NextResponse.json(
          {
            error:
              "Unknown action. Use: status, invoices, contacts, transactions, summary",
          },
          { status: 400 }
        );
    }
  } catch {
    return NextResponse.json(
      {
        error: "Financial MCP server unreachable",
        connected: false,
        status: "error",
      },
      { status: 503 }
    );
  }
}

export async function POST(request: NextRequest) {
  const action = request.nextUrl.searchParams.get("action");

  try {
    switch (action) {
      case "connect": {
        const res = await fetch(`${FINANCIAL_MCP_URL}/xero/connect`, {
          method: "POST",
        });
        if (!res.ok)
          return NextResponse.json(
            { error: "Failed to initiate connection" },
            { status: res.status }
          );
        return NextResponse.json(await res.json());
      }

      case "create-invoice": {
        const body = await request.json();
        const res = await fetch(`${FINANCIAL_MCP_URL}/xero/invoices/create`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok)
          return NextResponse.json(
            { error: "Failed to create invoice" },
            { status: res.status }
          );
        return NextResponse.json(await res.json());
      }

      case "categorize": {
        const body = await request.json();
        const { transactionId, ...rest } = body;
        const res = await fetch(
          `${FINANCIAL_MCP_URL}/xero/bank-transactions/${transactionId}/categorize`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(rest),
          }
        );
        if (!res.ok)
          return NextResponse.json(
            { error: "Failed to categorize transaction" },
            { status: res.status }
          );
        return NextResponse.json(await res.json());
      }

      default:
        return NextResponse.json(
          {
            error: "Unknown action. Use: connect, create-invoice, categorize",
          },
          { status: 400 }
        );
    }
  } catch {
    return NextResponse.json(
      { error: "Financial MCP server unreachable" },
      { status: 503 }
    );
  }
}
