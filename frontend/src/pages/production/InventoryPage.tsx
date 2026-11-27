import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { api, getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { formatDateIN, formatINR } from "@/utils/format";

export default function InventoryPage() {
  const { toast } = useToast();
  const [summary, setSummary] = useState<any>(null);
  const [ledger, setLedger] = useState<any[]>([]);
  const [catFilter, setCatFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [reconciliation, setReconciliation] = useState<any>(null);

  const loadData = useCallback(async () => {
    const params = new URLSearchParams();
    if (catFilter) params.set("item_category", catFilter);
    if (typeFilter) params.set("transaction_type", typeFilter);
    const [sumRes, ledRes] = await Promise.all([
      api.get("/inventory/summary"),
      api.get(`/inventory/ledger?${params.toString()}`),
    ]);
    setSummary(sumRes.data);
    setLedger(ledRes.data);
  }, [catFilter, typeFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const runReconcile = async () => {
    try {
      const res = await api.get("/inventory/reconcile");
      setReconciliation(res.data);
      toast({
        title: res.data.is_fully_consistent ? "Stock Ledger Consistent" : "Discrepancy Detected",
        description: res.data.is_fully_consistent
          ? "All cached balances match SUM(stock_ledger.signed_quantity)."
          : `${res.data.discrepancy_count} item(s) out of sync.`,
        type: res.data.is_fully_consistent ? "success" : "error",
      });
    } catch (err) {
      toast({ title: "Reconciliation Error", description: getApiErrorMessage(err), type: "error" });
    }
  };

  if (!summary) return <div className="text-sm text-muted-foreground">Loading inventory...</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Inventory & Append-Only Stock Ledger</h1>
          <p className="text-sm text-muted-foreground">
            All stock balances are calculated directly from immutable ledger movements.
          </p>
        </div>
        <Button variant="outline" onClick={runReconcile}>
          <RefreshCw className="h-4 w-4" /> Verify Ledger Reconciliation
        </Button>
      </div>

      {reconciliation && (
        <Card className={reconciliation.is_fully_consistent ? "border-emerald-500/40" : "border-red-500/40"}>
          <CardContent className="p-4 flex items-center gap-3 text-sm">
            {reconciliation.is_fully_consistent ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-red-600" />
            )}
            <span>
              Reconciliation Checked {reconciliation.items.length} items —{" "}
              <strong>{reconciliation.discrepancy_count} discrepancies</strong>.
            </span>
          </CardContent>
        </Card>
      )}

      {/* Valuation Summary */}
      <div className="grid sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Raw Materials Value</div>
            <div className="text-xl font-bold mt-1">{formatINR(summary.valuation.raw_materials_value)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Packaging Materials Value</div>
            <div className="text-xl font-bold mt-1">{formatINR(summary.valuation.packaging_materials_value)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground">Finished Goods Value (Selling Price)</div>
            <div className="text-xl font-bold text-primary mt-1">{formatINR(summary.valuation.finished_goods_retail_value)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Finished Goods */}
      <Card>
        <CardHeader><CardTitle className="text-base">Finished Goods Inventory</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3">Product</th>
                <th className="py-2 pr-3 text-right">Physical</th>
                <th className="py-2 pr-3 text-right">Reserved</th>
                <th className="py-2 pr-3 text-right">Available</th>
                <th className="py-2 pr-3 text-right">Reorder</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {summary.finished_goods.map((p: any) => (
                <tr key={p.id} className="border-b border-border/50">
                  <td className="py-2 pr-3 font-medium">{p.name}</td>
                  <td className="py-2 pr-3 text-right">{Number(p.physical_stock)} {p.unit}</td>
                  <td className="py-2 pr-3 text-right">{Number(p.reserved_stock)} {p.unit}</td>
                  <td className="py-2 pr-3 text-right font-bold">{Number(p.available_stock)} {p.unit}</td>
                  <td className="py-2 pr-3 text-right">{Number(p.reorder_level)}</td>
                  <td className="py-2">
                    <Badge variant={p.is_low_stock ? "danger" : "success"}>{p.is_low_stock ? "Low Stock" : "OK"}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Raw & Packaging */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle className="text-base">Raw Materials</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3">Material</th>
                  <th className="py-2 pr-3 text-right">Stock</th>
                  <th className="py-2 pr-3 text-right">Avg Rate</th>
                  <th className="py-2 text-right">Value</th>
                </tr>
              </thead>
              <tbody>
                {summary.raw_materials.map((m: any) => (
                  <tr key={m.id} className="border-b border-border/50">
                    <td className="py-2 pr-3 font-medium">{m.name}</td>
                    <td className="py-2 pr-3 text-right">{Number(m.closing_stock)} {m.unit}</td>
                    <td className="py-2 pr-3 text-right">{formatINR(m.avg_rate, 3)}</td>
                    <td className="py-2 text-right font-semibold">{formatINR(m.stock_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Packaging Materials</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3">Material</th>
                  <th className="py-2 pr-3 text-right">Stock</th>
                  <th className="py-2 pr-3 text-right">Avg Rate</th>
                  <th className="py-2 text-right">Value</th>
                </tr>
              </thead>
              <tbody>
                {summary.packaging_materials.map((m: any) => (
                  <tr key={m.id} className="border-b border-border/50">
                    <td className="py-2 pr-3 font-medium">{m.name}</td>
                    <td className="py-2 pr-3 text-right">{Number(m.closing_stock)} {m.unit}</td>
                    <td className="py-2 pr-3 text-right">{formatINR(m.avg_rate)}</td>
                    <td className="py-2 text-right font-semibold">{formatINR(m.stock_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>

      {/* Stock Ledger */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base">Stock Movement Ledger ({ledger.length})</CardTitle>
            <div className="flex gap-2">
              <Select value={catFilter} onChange={(e) => setCatFilter(e.target.value)} className="w-40 h-9 text-xs">
                <option value="">All Categories</option>
                <option value="raw_material">Raw Material</option>
                <option value="packaging_material">Packaging</option>
                <option value="finished_good">Finished Good</option>
              </Select>
              <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="w-40 h-9 text-xs">
                <option value="">All Types</option>
                <option value="opening">Opening</option>
                <option value="purchase">Purchase</option>
                <option value="production_issue">Production Issue</option>
                <option value="production_output">Production Output</option>
                <option value="dispatch">Dispatch</option>
                <option value="sales_return">Sales Return</option>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-xs sm:text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3">ID</th>
                <th className="py-2 pr-3">Item</th>
                <th className="py-2 pr-3">Type</th>
                <th className="py-2 pr-3">Source Ref</th>
                <th className="py-2 pr-3 text-right">Signed Qty</th>
                <th className="py-2 pr-3 text-right">Rate</th>
                <th className="py-2 text-right">Date</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map((e) => (
                <tr key={e.id} className="border-b border-border/50">
                  <td className="py-2 pr-3 font-mono text-xs">#{e.id}</td>
                  <td className="py-2 pr-3 font-medium">{e.item_name}</td>
                  <td className="py-2 pr-3">
                    <Badge variant={e.direction === "IN" ? "success" : "warning"}>{e.transaction_type}</Badge>
                  </td>
                  <td className="py-2 pr-3 font-mono text-xs">{e.source_doc_ref || `${e.source_doc_type}#${e.source_doc_id}`}</td>
                  <td className={`py-2 pr-3 text-right font-semibold ${e.direction === "IN" ? "text-emerald-600" : "text-amber-700"}`}>
                    {Number(e.signed_quantity) > 0 ? `+${Number(e.signed_quantity)}` : Number(e.signed_quantity)} {e.unit}
                  </td>
                  <td className="py-2 pr-3 text-right">{formatINR(e.rate, 3)}</td>
                  <td className="py-2 text-right text-xs text-muted-foreground">{formatDateIN(e.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
