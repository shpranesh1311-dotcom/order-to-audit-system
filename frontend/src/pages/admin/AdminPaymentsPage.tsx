import React, { useCallback, useEffect, useState } from "react";
import { CreditCard } from "lucide-react";
import { api, getApiErrorMessage } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { formatDateIN, formatINR } from "@/utils/format";

interface InvoiceRow {
  id: number;
  invoice_number: string;
  customer_id: number;
  buyer_name: string;
  grand_total: string;
  paid_amount: string;
  outstanding_amount: string;
}

interface PaymentRow {
  id: number;
  payment_number: string;
  payment_date: string;
  customer_name: string;
  invoice_number: string;
  payment_method: string;
  reference_number: string | null;
  amount: string;
}

interface AgeingResponse {
  summary: {
    bucket_0_30: string;
    bucket_31_60: string;
    bucket_60_plus: string;
    total_outstanding: string;
  };
  customers: {
    customer_id: number;
    customer_name: string;
    state: string;
    bucket_0_30: string;
    bucket_31_60: string;
    bucket_60_plus: string;
    total_outstanding: string;
  }[];
}

export default function AdminPaymentsPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const isAdmin = user?.role === "admin";
  const [invoices, setInvoices] = useState<InvoiceRow[]>([]);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [ageing, setAgeing] = useState<AgeingResponse | null>(null);
  const [invoiceId, setInvoiceId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("neft");
  const [reference, setReference] = useState("");
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));

  const loadData = useCallback(async () => {
    const [invRes, payRes, ageRes] = await Promise.all([
      api.get<InvoiceRow[]>("/invoices"),
      api.get<PaymentRow[]>("/payments"),
      api.get<AgeingResponse>("/payments/ageing"),
    ]);
    setInvoices(invRes.data);
    setPayments(payRes.data);
    setAgeing(ageRes.data);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const unpaidInvoices = invoices.filter((i) => Number(i.outstanding_amount) > 0);
  const selectedInvoice = unpaidInvoices.find((i) => i.id === Number(invoiceId));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvoice) return;
    try {
      await api.post("/payments", {
        customer_id: selectedInvoice.customer_id,
        invoice_id: selectedInvoice.id,
        payment_date: payDate,
        amount: Number(amount),
        payment_method: method,
        reference_number: reference || undefined,
        idempotency_key: crypto.randomUUID(),
      });
      toast({ title: "Payment Recorded", description: `Allocated ${formatINR(amount)} to ${selectedInvoice.invoice_number}`, type: "success" });
      setAmount("");
      setReference("");
      setInvoiceId("");
      loadData();
    } catch (err) {
      toast({ title: "Payment Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Payments & Outstanding Receivables</h1>
        <p className="text-sm text-muted-foreground">
          Record partial or full invoice payments and monitor customer receivables ageing.
        </p>
      </div>

      {ageing && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="text-xs text-muted-foreground">Total Outstanding</div>
              <div className="text-xl font-bold text-primary mt-1">{formatINR(ageing.summary.total_outstanding)}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-xs text-muted-foreground">0–30 Days</div>
              <div className="text-xl font-bold mt-1">{formatINR(ageing.summary.bucket_0_30)}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-xs text-muted-foreground">31–60 Days</div>
              <div className="text-xl font-bold mt-1">{formatINR(ageing.summary.bucket_31_60)}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-xs text-muted-foreground">Above 60 Days</div>
              <div className="text-xl font-bold text-destructive mt-1">{formatINR(ageing.summary.bucket_60_plus)}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {isAdmin && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-primary" /> Record Payment
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                  <label className="text-xs font-medium">Open Invoice</label>
                  <Select value={invoiceId} onChange={(e) => setInvoiceId(Number(e.target.value))} required>
                    <option value="">Select Invoice...</option>
                    {unpaidInvoices.map((inv) => (
                      <option key={inv.id} value={inv.id}>
                        {inv.invoice_number} — {inv.buyer_name} (Due: {formatINR(inv.outstanding_amount)})
                      </option>
                    ))}
                  </Select>
                </div>
                {selectedInvoice && (
                  <div className="rounded-lg bg-secondary/60 p-2.5 text-xs space-y-1">
                    <div>Invoice Total: <strong>{formatINR(selectedInvoice.grand_total)}</strong></div>
                    <div>Paid So Far: <strong>{formatINR(selectedInvoice.paid_amount)}</strong></div>
                    <div>Outstanding: <strong className="text-primary">{formatINR(selectedInvoice.outstanding_amount)}</strong></div>
                  </div>
                )}
                <div>
                  <label className="text-xs font-medium">Amount (₹)</label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="e.g. 4000"
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-medium">Method</label>
                    <Select value={method} onChange={(e) => setMethod(e.target.value)}>
                      <option value="neft">NEFT</option>
                      <option value="upi">UPI</option>
                      <option value="rtgs">RTGS</option>
                      <option value="cash">Cash</option>
                      <option value="cheque">Cheque</option>
                      <option value="bank_transfer">Bank Transfer</option>
                    </Select>
                  </div>
                  <div>
                    <label className="text-xs font-medium">Date</label>
                    <Input type="date" value={payDate} onChange={(e) => setPayDate(e.target.value)} required />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium">Transaction Reference</label>
                  <Input
                    value={reference}
                    onChange={(e) => setReference(e.target.value)}
                    placeholder="UTR / Cheque / UPI Ref"
                  />
                </div>
                <Button type="submit" className="w-full" disabled={!selectedInvoice}>
                  Post Payment
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        <Card className={isAdmin ? "lg:col-span-2" : "lg:col-span-3"}>
          <CardHeader>
            <CardTitle className="text-base">Customer-wise Outstanding Balances</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3">Customer</th>
                  <th className="py-2 pr-3">State</th>
                  <th className="py-2 pr-3 text-right">0–30 Days</th>
                  <th className="py-2 pr-3 text-right">31–60 Days</th>
                  <th className="py-2 pr-3 text-right">60+ Days</th>
                  <th className="py-2 text-right">Total Due</th>
                </tr>
              </thead>
              <tbody>
                {ageing?.customers.map((c) => (
                  <tr key={c.customer_id} className="border-b border-border/50">
                    <td className="py-2.5 pr-3 font-medium">{c.customer_name}</td>
                    <td className="py-2.5 pr-3">{c.state}</td>
                    <td className="py-2.5 pr-3 text-right">{formatINR(c.bucket_0_30)}</td>
                    <td className="py-2.5 pr-3 text-right">{formatINR(c.bucket_31_60)}</td>
                    <td className="py-2.5 pr-3 text-right">{formatINR(c.bucket_60_plus)}</td>
                    <td className="py-2.5 text-right font-bold text-primary">{formatINR(c.total_outstanding)}</td>
                  </tr>
                ))}
                {(!ageing || ageing.customers.length === 0) && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-muted-foreground">
                      No outstanding receivables.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Payment History ({payments.length})</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3">Payment No</th>
                <th className="py-2 pr-3">Date</th>
                <th className="py-2 pr-3">Customer</th>
                <th className="py-2 pr-3">Invoice</th>
                <th className="py-2 pr-3">Method</th>
                <th className="py-2 pr-3">Reference</th>
                <th className="py-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id} className="border-b border-border/50">
                  <td className="py-2 pr-3 font-medium">{p.payment_number}</td>
                  <td className="py-2 pr-3">{formatDateIN(p.payment_date)}</td>
                  <td className="py-2 pr-3">{p.customer_name}</td>
                  <td className="py-2 pr-3">{p.invoice_number}</td>
                  <td className="py-2 pr-3"><Badge variant="secondary" className="uppercase">{p.payment_method}</Badge></td>
                  <td className="py-2 pr-3 text-muted-foreground">{p.reference_number || "-"}</td>
                  <td className="py-2 text-right font-semibold">{formatINR(p.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
