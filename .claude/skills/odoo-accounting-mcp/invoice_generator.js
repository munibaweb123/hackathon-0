/**
 * Invoice Generator — higher-level accounting operations built on OdooClient.
 *
 * Handles invoice creation (with line items), payment recording, expense logging,
 * partner management, balance queries, and PDF download via Odoo's report engine.
 */

import fs from "fs";
import path from "path";

export class InvoiceGenerator {
  /**
   * @param {import('./odoo_client.js').OdooClient} odooClient
   * @param {string} [vaultPath]
   */
  constructor(odooClient, vaultPath) {
    this.odoo = odooClient;
    this.vaultPath = vaultPath || odooClient.vaultPath || "./obsidian-vault";
    this._ensureAccountingFolders();
  }

  // -------------------------------------------------------------------------
  // Invoice operations
  // -------------------------------------------------------------------------

  /**
   * Create a customer invoice in Odoo.
   *
   * @param {object} params
   * @param {string} params.partnerName    — Customer name (resolved or created)
   * @param {Array}  params.lineItems      — Array of { description, quantity, unit_price }
   * @param {string} [params.dueDate]      — Due date (YYYY-MM-DD)
   * @param {string} [params.currency]     — Currency code (e.g., "USD", "EUR")
   * @returns {{ invoiceId: number, invoiceName: string, partnerId: number, total: number }}
   */
  async createInvoice({ partnerName, lineItems, dueDate, currency }) {
    // 1. Resolve or create partner
    const partnerId = await this._resolveOrCreatePartner(partnerName);

    // 2. Resolve currency if specified
    let currencyId;
    if (currency) {
      const currencies = await this.odoo.searchRead(
        "res.currency",
        [["name", "=", currency.toUpperCase()]],
        ["id"],
        { limit: 1 }
      );
      if (currencies.length > 0) {
        currencyId = currencies[0].id;
      }
    }

    // 3. Build invoice line values (Odoo one2many command format)
    const invoiceLines = lineItems.map((item) => [
      0, 0, {
        name: item.description || "Service",
        quantity: item.quantity || 1,
        price_unit: item.unit_price || 0,
      },
    ]);

    // 4. Create the invoice (account.move)
    const invoiceValues = {
      move_type: "out_invoice",
      partner_id: partnerId,
      invoice_line_ids: invoiceLines,
    };

    if (dueDate) {
      invoiceValues.invoice_date_due = dueDate;
    }
    if (currencyId) {
      invoiceValues.currency_id = currencyId;
    }

    const invoiceId = await this.odoo.create("account.move", invoiceValues);

    // 5. Read back to get the invoice name and total
    const invoices = await this.odoo.searchRead(
      "account.move",
      [["id", "=", invoiceId]],
      ["name", "amount_total", "state"],
      { limit: 1 }
    );

    const invoice = invoices[0] || {};

    await this.odoo.logAction("create_invoice", {
      invoiceId,
      invoiceName: invoice.name,
      partnerId,
      partnerName,
      total: invoice.amount_total,
      currency: currency || "default",
      lineItems: lineItems.length,
    });

    return {
      invoiceId,
      invoiceName: invoice.name || `INV/${invoiceId}`,
      partnerId,
      total: invoice.amount_total || 0,
    };
  }

  /**
   * Confirm/validate a draft invoice (moves it from Draft → Posted).
   * @param {number} invoiceId
   */
  async confirmInvoice(invoiceId) {
    await this.odoo.callMethod("account.move", "action_post", [invoiceId]);

    await this.odoo.logAction("confirm_invoice", { invoiceId });

    return { invoiceId, state: "posted" };
  }

  /**
   * Download invoice PDF from Odoo's report engine and save to vault.
   *
   * @param {number} invoiceId
   * @returns {{ pdfPath: string, filename: string }}
   */
  async downloadPdf(invoiceId) {
    // Get invoice name for the filename
    const invoices = await this.odoo.searchRead(
      "account.move",
      [["id", "=", invoiceId]],
      ["name"],
      { limit: 1 }
    );

    const invoiceName = invoices[0]?.name || `INV_${invoiceId}`;
    const safeFilename = invoiceName.replace(/[/\\?%*:|"<>]/g, "_");

    const pdfBuffer = await this.odoo.getReport(
      "account.report_invoice",
      [invoiceId]
    );

    const pdfDir = path.join(this.vaultPath, "Accounting", "invoices");
    const filename = `${safeFilename}.pdf`;
    const pdfPath = path.join(pdfDir, filename);

    fs.writeFileSync(pdfPath, pdfBuffer);

    await this.odoo.logAction("download_invoice_pdf", {
      invoiceId,
      pdfPath,
      filename,
    });

    return { pdfPath, filename };
  }

  // -------------------------------------------------------------------------
  // Payment operations
  // -------------------------------------------------------------------------

  /**
   * Record a payment against an invoice.
   *
   * @param {object} params
   * @param {number} params.invoiceId     — Odoo invoice ID (account.move)
   * @param {number} params.amount        — Payment amount
   * @param {string} [params.paymentDate] — Date (YYYY-MM-DD)
   * @param {string} [params.method]      — Payment method (bank|cash|check)
   * @returns {{ paymentId: number, paymentName: string, state: string }}
   */
  async recordPayment({ invoiceId, amount, paymentDate, method }) {
    // Find the journal for the payment method
    const journalDomain = [];
    if (method === "cash") {
      journalDomain.push(["type", "=", "cash"]);
    } else if (method === "check") {
      journalDomain.push(["type", "=", "bank"]);
    } else {
      // Default: bank
      journalDomain.push(["type", "=", "bank"]);
    }

    const journals = await this.odoo.searchRead(
      "account.journal",
      journalDomain,
      ["id", "name"],
      { limit: 1 }
    );

    if (journals.length === 0) {
      throw new Error(
        `No ${method || "bank"} journal found. Configure journals in Odoo Accounting settings.`
      );
    }

    const journalId = journals[0].id;

    // Get invoice details for partner
    const invoices = await this.odoo.searchRead(
      "account.move",
      [["id", "=", invoiceId]],
      ["partner_id", "name", "currency_id"],
      { limit: 1 }
    );

    if (invoices.length === 0) {
      throw new Error(`Invoice ID ${invoiceId} not found`);
    }

    const invoice = invoices[0];

    // Create payment
    const paymentValues = {
      payment_type: "inbound",
      partner_type: "customer",
      partner_id: invoice.partner_id[0],
      amount,
      journal_id: journalId,
      ref: invoice.name,
    };

    if (paymentDate) {
      paymentValues.date = paymentDate;
    }

    if (invoice.currency_id) {
      paymentValues.currency_id = invoice.currency_id[0];
    }

    const paymentId = await this.odoo.create("account.payment", paymentValues);

    // Confirm the payment
    await this.odoo.callMethod("account.payment", "action_post", [paymentId]);

    // Read back the payment
    const payments = await this.odoo.searchRead(
      "account.payment",
      [["id", "=", paymentId]],
      ["name", "state", "amount"],
      { limit: 1 }
    );

    const payment = payments[0] || {};

    // Save payment record to vault
    const paymentRecord = [
      "---",
      `id: ${paymentId}`,
      `invoice: ${invoice.name}`,
      `amount: ${amount}`,
      `method: ${method || "bank"}`,
      `date: ${paymentDate || new Date().toISOString().split("T")[0]}`,
      `state: ${payment.state || "posted"}`,
      "---",
      "",
      `# Payment ${payment.name || paymentId}`,
      "",
      `- **Invoice:** ${invoice.name}`,
      `- **Amount:** ${amount}`,
      `- **Method:** ${method || "bank"}`,
      `- **Journal:** ${journals[0].name}`,
      `- **Date:** ${paymentDate || new Date().toISOString().split("T")[0]}`,
    ].join("\n");

    const paymentFile = path.join(
      this.vaultPath,
      "Accounting",
      "payments",
      `PAYMENT_${paymentId}.md`
    );
    fs.writeFileSync(paymentFile, paymentRecord, "utf-8");

    await this.odoo.logAction("record_payment", {
      paymentId,
      paymentName: payment.name,
      invoiceId,
      invoiceName: invoice.name,
      amount,
      method: method || "bank",
    });

    return {
      paymentId,
      paymentName: payment.name || `PAY/${paymentId}`,
      state: payment.state || "posted",
    };
  }

  // -------------------------------------------------------------------------
  // Expense operations
  // -------------------------------------------------------------------------

  /**
   * Create an expense record.
   *
   * @param {object} params
   * @param {string} params.category     — Expense category
   * @param {number} params.amount       — Expense amount
   * @param {string} params.description  — Description
   * @param {string} [params.date]       — Date (YYYY-MM-DD)
   * @returns {{ expenseId: number, expenseName: string }}
   */
  async createExpense({ category, amount, description, date }) {
    // Search for the expense product/category
    const products = await this.odoo.searchRead(
      "product.product",
      [["name", "ilike", category], ["can_be_expensed", "=", true]],
      ["id", "name"],
      { limit: 1 }
    );

    const productId = products.length > 0 ? products[0].id : null;

    // Create the expense (hr.expense model)
    const expenseValues = {
      name: description,
      total_amount: amount,
    };

    if (productId) {
      expenseValues.product_id = productId;
    }

    if (date) {
      expenseValues.date = date;
    }

    const expenseId = await this.odoo.create("hr.expense", expenseValues);

    // Read back
    const expenses = await this.odoo.searchRead(
      "hr.expense",
      [["id", "=", expenseId]],
      ["name", "total_amount", "state"],
      { limit: 1 }
    );

    const expense = expenses[0] || {};

    // Save expense record to vault
    const expenseRecord = [
      "---",
      `id: ${expenseId}`,
      `category: ${category}`,
      `amount: ${amount}`,
      `description: ${description}`,
      `date: ${date || new Date().toISOString().split("T")[0]}`,
      "---",
      "",
      `# Expense: ${description}`,
      "",
      `- **Category:** ${category}`,
      `- **Amount:** ${amount}`,
      `- **Date:** ${date || new Date().toISOString().split("T")[0]}`,
      `- **State:** ${expense.state || "draft"}`,
    ].join("\n");

    const expenseFile = path.join(
      this.vaultPath,
      "Accounting",
      "expenses",
      `EXPENSE_${expenseId}.md`
    );
    fs.writeFileSync(expenseFile, expenseRecord, "utf-8");

    await this.odoo.logAction("create_expense", {
      expenseId,
      category,
      amount,
      description,
    });

    return {
      expenseId,
      expenseName: expense.name || description,
    };
  }

  // -------------------------------------------------------------------------
  // Balance and reporting
  // -------------------------------------------------------------------------

  /**
   * Get account balance by type.
   *
   * @param {string} accountType — "receivable" | "payable" | "bank" | "cash"
   * @returns {{ accountType: string, balance: number, accounts: Array }}
   */
  async getAccountBalance(accountType) {
    const typeMap = {
      receivable: "asset_receivable",
      payable: "liability_payable",
      bank: "asset_cash",
      cash: "asset_cash",
    };

    const odooType = typeMap[accountType];
    if (!odooType) {
      throw new Error(
        `Invalid account type: ${accountType}. Use: receivable, payable, bank, cash`
      );
    }

    // For bank/cash differentiation
    let extraDomain = [];
    if (accountType === "bank") {
      // Filter bank journals
      const bankJournals = await this.odoo.searchRead(
        "account.journal",
        [["type", "=", "bank"]],
        ["default_account_id"],
        {}
      );
      const bankAccountIds = bankJournals
        .map((j) => j.default_account_id?.[0])
        .filter(Boolean);
      if (bankAccountIds.length > 0) {
        extraDomain = [["id", "in", bankAccountIds]];
      }
    } else if (accountType === "cash") {
      const cashJournals = await this.odoo.searchRead(
        "account.journal",
        [["type", "=", "cash"]],
        ["default_account_id"],
        {}
      );
      const cashAccountIds = cashJournals
        .map((j) => j.default_account_id?.[0])
        .filter(Boolean);
      if (cashAccountIds.length > 0) {
        extraDomain = [["id", "in", cashAccountIds]];
      }
    }

    const domain = [
      ["account_type", "=", odooType],
      ...extraDomain,
    ];

    const accounts = await this.odoo.searchRead(
      "account.account",
      domain,
      ["id", "name", "code", "current_balance"],
      {}
    );

    const totalBalance = accounts.reduce(
      (sum, acc) => sum + (acc.current_balance || 0),
      0
    );

    return {
      accountType,
      balance: totalBalance,
      accounts: accounts.map((a) => ({
        id: a.id,
        code: a.code,
        name: a.name,
        balance: a.current_balance || 0,
      })),
    };
  }

  /**
   * List unpaid/partially paid invoices.
   *
   * @returns {Array<{ id, name, partnerName, amountTotal, amountResidual, dueDate, state }>}
   */
  async getUnpaidInvoices() {
    const invoices = await this.odoo.searchRead(
      "account.move",
      [
        ["move_type", "=", "out_invoice"],
        ["payment_state", "in", ["not_paid", "partial"]],
        ["state", "=", "posted"],
      ],
      [
        "id",
        "name",
        "partner_id",
        "amount_total",
        "amount_residual",
        "invoice_date_due",
        "state",
        "payment_state",
      ],
      { order: "invoice_date_due asc" }
    );

    return invoices.map((inv) => ({
      id: inv.id,
      name: inv.name,
      partnerName: inv.partner_id?.[1] || "Unknown",
      amountTotal: inv.amount_total,
      amountResidual: inv.amount_residual,
      dueDate: inv.invoice_date_due || null,
      state: inv.state,
      paymentState: inv.payment_state,
    }));
  }

  // -------------------------------------------------------------------------
  // Partner management
  // -------------------------------------------------------------------------

  /**
   * Create a new partner (customer/vendor).
   *
   * @param {object} params
   * @param {string} params.name     — Partner name
   * @param {string} [params.email]  — Email address
   * @param {string} [params.phone]  — Phone number
   * @param {string} [params.address] — Full address
   * @returns {{ partnerId: number, partnerName: string }}
   */
  async createPartner({ name, email, phone, address }) {
    const partnerValues = {
      name,
      customer_rank: 1,
    };

    if (email) partnerValues.email = email;
    if (phone) partnerValues.phone = phone;
    if (address) partnerValues.street = address;

    const partnerId = await this.odoo.create("res.partner", partnerValues);

    await this.odoo.logAction("create_partner", {
      partnerId,
      name,
      email,
      phone,
    });

    return { partnerId, partnerName: name };
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  async _resolveOrCreatePartner(name) {
    // Try to find existing partner by name
    const existing = await this.odoo.searchRead(
      "res.partner",
      [["name", "ilike", name]],
      ["id", "name"],
      { limit: 1 }
    );

    if (existing.length > 0) {
      return existing[0].id;
    }

    // Create new partner
    const partnerId = await this.odoo.create("res.partner", {
      name,
      customer_rank: 1,
    });

    return partnerId;
  }

  _ensureAccountingFolders() {
    const folders = [
      path.join(this.vaultPath, "Accounting"),
      path.join(this.vaultPath, "Accounting", "invoices"),
      path.join(this.vaultPath, "Accounting", "payments"),
      path.join(this.vaultPath, "Accounting", "expenses"),
    ];

    for (const folder of folders) {
      if (!fs.existsSync(folder)) {
        fs.mkdirSync(folder, { recursive: true });
      }
    }
  }
}
