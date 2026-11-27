import React, { useCallback, useEffect, useState } from "react";
import { Download, RotateCcw, Share2, Truck } from "lucide-react";
import { api, getApiErrorMessage } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { formatDateIN, formatINR } from "@/utils/format";

interface InvoiceItem {
  id: number;
  product_id: number;
  product_name: string;
  hsn_code: string;
  quantity: string;
  unit_price: string;
  taxable_value: string;
}

interface Invoice {
  id: number;
  invoice_number: string;
  invoice_date: string;
  buyer_name: string;
  place_of_supply: string;
  tax_type: string;
  taxable_value: string;
  cgst_amount: string;
  sgst_amount: string;
  igst_amount: string;
  grand_total: string;
  paid_amount: string;
  outstanding_amount: string;
  status: string;
  dispatch_status: string;
  items: InvoiceItem[];
}

interface CreditNote {
  id: number;
  credit_note_number: string;
  invoice_number: string;
  customer_name: string;
  credit_note_date: string;
  reason: string;
  total_amount: string;
}

interface SalesReturn {
  id: number;
  return_number: string;
  invoice_id: number;
  product_name: string;
  return_date: string;
  returned_qty: string;
  usable_qty: string;
  damaged_qty: string;
  stock_restored: boolean;
}

export default function AdminInvoicesPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const isAdmin = user?.role === "admin";
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [creditNotes, setCreditNotes] = useState<CreditNote[]>([]);
  const [returns, setReturns] = useState<SalesReturn[]>([]);
  const [selectedInvId, setSelectedInvId] = useState<number | "">("");
  const [cnReason, setCnReason] = useState("");
  const [cnTaxable, setCnTaxable] = useState("");
  const [retInvId, setRetInvId] = useState<number | "">("");
  const [retProdId, setRetProdId] = useState<number | "">("");
  const [retTotal, setRetTotal] = useState("");
  const [retUsable, setRetUsable] = useState("");
  const [retDamaged, setRetDamaged] = useState("");

  const loadAll = useCallback(async () => {
    const [invRes, cnRes, retRes] = await Promise.all([
      api.get<Invoice[]>("/invoices"),
      api.get<CreditNote[]>("/invoices/credit-notes"),
      api.get<SalesReturn[]>("/invoices/sales-returns"),
    ]);
    setInvoices(invRes.data);
    setCreditNotes(cnRes.data);
    setReturns(retRes.data);
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleDispatch = async (inv: Invoice) => {
    try {
      await api.post(`/invoices/${inv.id}/dispatch`);
      toast({
        title: `Dispatched ${inv.invoice_number}`,
        description: "Finished goods stock reduced via append-only stock ledger.",
        type: "success",
      });
      loadAll();
    } catch (err) {
      toast({ title: "Dispatch Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  const handleDownloadPdf = async (inv: Invoice) => {
    try {
      const res = await api.get(`/invoices/${inv.id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${inv.invoice_number.replace(/\//g, "-")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast({ title: "PDF Download Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  const handleShareWhatsApp = (inv: Invoice) => {
    const text = encodeURIComponent(
      `GST Tax Invoice ${inv.invoice_number} from Kaveri Crunch Foods\nCustomer: ${inv.buyer_name}\nAmount: ${formatINR(inv.grand_total)}\nBalance Due: ${formatINR(inv.outstanding_amount)}`
    );
    window.open(`https://wa.me/?text=${text}`, "_blank", "noopener,noreferrer");
  };

  const handleCreateCreditNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvId || !cnReason.trim()) return;
    try {
      await api.post("/invoices/credit-notes", {
        invoice_id: Number(selectedInvId),
        reason: cnReason.trim(),
        taxable_value: cnTaxable ? Number(cnTaxable) : undefined,
      });
      toast({ title: "Credit Note Posted", description: "Physical stock unchanged (per GST rules).", type: "success" });
      setCnReason("");
      setCnTaxable("");
      loadAll();
    } catch (err) {
      toast({ title: "Credit Note Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  const handleCreateReturn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!retInvId || !retProdId) return;
    try {
      await api.post("/invoices/sales-returns", {
        invoice_id: Number(retInvId),
        product_id: Number(retProdId),
        returned_qty: Number(retTotal),
        usable_qty: Number(retUsable),
        damaged_qty: Number(retDamaged),
      });
      toast({ title: "Sales Return Inspected & Recorded", type: "success" });
      setRetTotal("");
      setRetUsable("");
      setRetDamaged("");
      loadAll();
    } catch (err) {
      toast({ title: "Sales Return Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  const selectedRetInvoice = invoices.find((i) => i.id === Number(retInvId));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">GST Invoices, Dispatch & Returns</h1>
        <p className="text-sm text-muted-foreground">
          Intra-state Tamil Nadu (CGST + SGST) and Inter-state (IGST) billing, dispatch, credit notes, and physical return inspection.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tax Invoices ({invoices.length})</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3">Invoice No</th>
                <th className="py-2 pr-3">Date</th>
                <th className="py-2 pr-3">Customer / Supply</th>
                <th className="py-2 pr-3 text-right">Taxable</th>
                <th className="py-2 pr-3 text-right">CGST</th>
                <th className="py-2 pr-3 text-right">SGST</th>
                <th className="py-2 pr-3 text-right">IGST</th>
                <th className="py-2 pr-3 text-right">Grand Total</th>
                <th className="py-2 pr-3 text-right">Due</th>
                <th className="py-2 pr-3">Dispatch</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-border/50">
                  <td className="py-2.5 pr-3 font-semibold">{inv.invoice_number}</td>
                  <td className="py-2.5 pr-3">{formatDateIN(inv.invoice_date)}</td>
                  <td className="py-2.5 pr-3">
                    <div>{inv.buyer_name}</div>
                    <div className="text-xs text-muted-foreground">{inv.place_of_supply} ({inv.tax_type})</div>
                  </td>
                  <td className="py-2.5 pr-3 text-right">{formatINR(inv.taxable_value)}</td>
                  <td className="py-2.5 pr-3 text-right">{formatINR(inv.cgst_amount)}</td>
                  <td className="py-2.5 pr-3 text-right">{formatINR(inv.sgst_amount)}</td>
                  <td className="py-2.5 pr-3 text-right">{formatINR(inv.igst_amount)}</td>
                  <td className="py-2.5 pr-3 text-right font-bold">{formatINR(inv.grand_total)}</td>
                  <td className="py-2.5 pr-3 text-right font-medium text-amber-700 dark:text-amber-400">
                    {formatINR(inv.outstanding_amount)}
                  </td>
                  <td className="py-2.5 pr-3">
                    <Badge variant={inv.dispatch_status === "dispatched" ? "success" : "warning"} className="capitalize">
                      {inv.dispatch_status}
                    </Badge>
                  </td>
                  <td className="py-2.5 text-right">
                    <div className="flex justify-end gap-1.5">
                      <Button size="sm" variant="outline" onClick={() => handleDownloadPdf(inv)} title="Download PDF">
                        <Download className="h-3.5 w-3.5" /> PDF
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleShareWhatsApp(inv)} title="Share via WhatsApp">
                        <Share2 className="h-3.5 w-3.5" />
                      </Button>
                      {isAdmin && inv.dispatch_status !== "dispatched" && (
                        <Button size="sm" onClick={() => handleDispatch(inv)}>
                          <Truck className="h-3.5 w-3.5" /> Dispatch
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {invoices.length === 0 && (
                <tr>
                  <td colSpan={11} className="py-8 text-center text-muted-foreground">
                    No invoices generated yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {isAdmin && (
        <div className="grid md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Issue Accounting Credit Note</CardTitle>
              <p className="text-xs text-muted-foreground">
                Adjusts GST & customer ledger only. Does not modify physical finished-goods stock.
              </p>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateCreditNote} className="space-y-3">
                <Select value={selectedInvId} onChange={(e) => setSelectedInvId(Number(e.target.value))} required>
                  <option value="">Select Invoice...</option>
                  {invoices.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.invoice_number} — {i.buyer_name} ({formatINR(i.grand_total)})
                    </option>
                  ))}
                </Select>
                <Input
                  type="number"
                  step="0.01"
                  value={cnTaxable}
                  onChange={(e) => setCnTaxable(e.target.value)}
                  placeholder="Taxable value (leave blank for full invoice)"
                />
                <Input
                  value={cnReason}
                  onChange={(e) => setCnReason(e.target.value)}
                  placeholder="Reason (e.g. Price correction / damaged goods)"
                  required
                />
                <Button type="submit" size="sm">Create Credit Note</Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Record Inspected Physical Sales Return</CardTitle>
              <p className="text-xs text-muted-foreground">
                Only inspected usable packets are restored to saleable stock; damaged packets are logged separately.
              </p>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateReturn} className="space-y-3">
                <Select
                  value={retInvId}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    setRetInvId(id);
                    const inv = invoices.find((x) => x.id === id);
                    if (inv?.items[0]) setRetProdId(inv.items[0].product_id);
                  }}
                  required
                >
                  <option value="">Select Dispatched Invoice...</option>
                  {invoices.filter((i) => i.dispatch_status === "dispatched").map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.invoice_number} — {i.buyer_name}
                    </option>
                  ))}
                </Select>
                {selectedRetInvoice && (
                  <Select value={retProdId} onChange={(e) => setRetProdId(Number(e.target.value))} required>
                    {selectedRetInvoice.items.map((it) => (
                      <option key={it.id} value={it.product_id}>
                        {it.product_name} (Invoiced: {Number(it.quantity)})
                      </option>
                    ))}
                  </Select>
                )}
                <div className="grid grid-cols-3 gap-2">
                  <Input type="number" value={retTotal} onChange={(e) => setRetTotal(e.target.value)} placeholder="Returned" required />
                  <Input type="number" value={retUsable} onChange={(e) => setRetUsable(e.target.value)} placeholder="Usable" required />
                  <Input type="number" value={retDamaged} onChange={(e) => setRetDamaged(e.target.value)} placeholder="Damaged" required />
                </div>
                <Button type="submit" size="sm" variant="secondary">
                  <RotateCcw className="h-3.5 w-3.5" /> Record Inspected Return
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      )}

      {(creditNotes.length > 0 || returns.length > 0) && (
        <div className="grid md:grid-cols-2 gap-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Credit Notes ({creditNotes.length})</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              {creditNotes.map((cn) => (
                <div key={cn.id} className="flex justify-between border-b border-border/50 pb-2">
                  <div>
                    <div className="font-medium">{cn.credit_note_number} ({cn.invoice_number})</div>
                    <div className="text-xs text-muted-foreground">{cn.reason}</div>
                  </div>
                  <div className="font-semibold">{formatINR(cn.total_amount)}</div>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">Physical Sales Returns ({returns.length})</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              {returns.map((r) => (
                <div key={r.id} className="flex justify-between border-b border-border/50 pb-2">
                  <div>
                    <div className="font-medium">{r.return_number} — {r.product_name}</div>
                    <div className="text-xs text-muted-foreground">
                      Usable: {Number(r.usable_qty)} | Damaged: {Number(r.damaged_qty)}
                    </div>
                  </div>
                  <Badge variant={r.stock_restored ? "success" : "warning"}>
                    {r.stock_restored ? "Usable Restocked" : "Scrap Only"}
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
