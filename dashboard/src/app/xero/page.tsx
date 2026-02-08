"use client";

import { useState, useEffect } from "react";
import { XeroConnection } from "@/components/xero-connection";

interface Invoice {
  invoiceId: string;
  invoiceNumber: string;
  contact?: { name: string };
  status: string;
  total: number;
  amountDue: number;
  currency: string;
  dueDate: string;
}

export default function XeroPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    fetchInvoices();
  }, [statusFilter]);

  async function fetchInvoices() {
    setLoading(true);
    try {
      const params = statusFilter ? `&status=${statusFilter}` : "";
      const res = await fetch(`/api/xero?action=invoices${params}`);
      if (res.ok) {
        const data = await res.json();
        setInvoices(Array.isArray(data) ? data : []);
      }
    } catch {
      setInvoices([]);
    } finally {
      setLoading(false);
    }
  }

  const statusColors: Record<string, string> = {
    DRAFT: "bg-gray-100 text-gray-800",
    SUBMITTED: "bg-blue-100 text-blue-800",
    AUTHORISED: "bg-green-100 text-green-800",
    PAID: "bg-emerald-100 text-emerald-800",
    VOIDED: "bg-red-100 text-red-800",
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Xero Accounting</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <XeroConnection />

        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-2">Quick Stats</h3>
          <div className="space-y-2 text-sm">
            <p>
              <span className="text-muted-foreground">Total Invoices:</span>{" "}
              {invoices.length}
            </p>
            <p>
              <span className="text-muted-foreground">Outstanding:</span>{" "}
              {invoices.filter((i) => i.amountDue > 0).length}
            </p>
            <p>
              <span className="text-muted-foreground">Total Due:</span>{" "}
              {invoices
                .reduce((sum, i) => sum + (i.amountDue || 0), 0)
                .toLocaleString("en-US", {
                  style: "currency",
                  currency: invoices[0]?.currency || "USD",
                })}
            </p>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-lg font-semibold mb-2">Actions</h3>
          <div className="space-y-2">
            <button
              onClick={fetchInvoices}
              className="w-full px-3 py-1.5 text-sm border rounded-md hover:bg-accent"
            >
              Refresh Data
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-lg border bg-card">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Invoices</h2>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm border rounded-md px-2 py-1"
          >
            <option value="">All Statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="AUTHORISED">Authorised</option>
            <option value="PAID">Paid</option>
            <option value="VOIDED">Voided</option>
          </select>
        </div>

        {loading ? (
          <div className="p-8 text-center text-muted-foreground">
            Loading invoices...
          </div>
        ) : invoices.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            No invoices found. Connect Xero to get started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left p-3 font-medium">Invoice #</th>
                  <th className="text-left p-3 font-medium">Contact</th>
                  <th className="text-left p-3 font-medium">Status</th>
                  <th className="text-right p-3 font-medium">Total</th>
                  <th className="text-right p-3 font-medium">Due</th>
                  <th className="text-left p-3 font-medium">Due Date</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((invoice) => (
                  <tr key={invoice.invoiceId} className="border-b">
                    <td className="p-3 font-mono">
                      {invoice.invoiceNumber || invoice.invoiceId.slice(0, 8)}
                    </td>
                    <td className="p-3">
                      {invoice.contact?.name || "Unknown"}
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          statusColors[invoice.status] || "bg-gray-100"
                        }`}
                      >
                        {invoice.status}
                      </span>
                    </td>
                    <td className="p-3 text-right font-mono">
                      {invoice.total?.toLocaleString("en-US", {
                        style: "currency",
                        currency: invoice.currency || "USD",
                      })}
                    </td>
                    <td className="p-3 text-right font-mono">
                      {invoice.amountDue?.toLocaleString("en-US", {
                        style: "currency",
                        currency: invoice.currency || "USD",
                      })}
                    </td>
                    <td className="p-3">
                      {invoice.dueDate
                        ? new Date(invoice.dueDate).toLocaleDateString()
                        : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
