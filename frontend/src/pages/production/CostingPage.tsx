import React, { useEffect, useState } from "react";
import { api } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatINR } from "@/utils/format";

export default function CostingPage() {
  const [products, setProducts] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedRun, setSelectedRun] = useState<any>(null);

  useEffect(() => {
    const load = async () => {
      const [pRes, rRes] = await Promise.all([api.get("/costing/products"), api.get("/production/runs")]);
      setProducts(pRes.data);
      setRuns(rRes.data);
      if (rRes.data.length > 0) {
        const det = await api.get(`/costing/runs/${rRes.data[0].id}`);
        setSelectedRun(det.data);
      }
    };
    load();
  }, []);

  const selectRun = async (runId: number) => {
    const det = await api.get(`/costing/runs/${runId}`);
    setSelectedRun(det.data);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Product Costing & Margin Analysis</h1>
        <p className="text-sm text-muted-foreground">
          Weighted-average material valuation + actual packaging + labour & overheads allocated across good packets produced.
        </p>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Product-wise Cost & Margin</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3">Product</th>
                <th className="py-2 pr-3 text-right">Selling Price (Excl. GST)</th>
                <th className="py-2 pr-3 text-right">Latest Cost / Packet</th>
                <th className="py-2 pr-3 text-right">Avg Cost / Packet</th>
                <th className="py-2 pr-3 text-right">Profit / Packet</th>
                <th className="py-2 text-right">Margin %</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.product_id} className="border-b border-border/50">
                  <td className="py-2.5 pr-3 font-medium">{p.product_name}</td>
                  <td className="py-2.5 pr-3 text-right">{formatINR(p.selling_price_excl_gst)}</td>
                  <td className="py-2.5 pr-3 text-right font-bold text-primary">
                    {p.latest_cost_per_packet ? formatINR(p.latest_cost_per_packet) : "-"}
                  </td>
                  <td className="py-2.5 pr-3 text-right">
                    {p.avg_cost_per_packet ? formatINR(p.avg_cost_per_packet) : "-"}
                  </td>
                  <td className="py-2.5 pr-3 text-right text-emerald-600 dark:text-emerald-400 font-semibold">
                    {p.profit_per_packet ? formatINR(p.profit_per_packet) : "-"}
                  </td>
                  <td className="py-2.5 text-right">
                    {p.profit_margin_pct ? <Badge variant="success">{p.profit_margin_pct}%</Badge> : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {runs.length > 0 && (
        <div className="grid lg:grid-cols-3 gap-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Select Production Run</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {runs.map((r) => (
                <button
                  key={r.id}
                  onClick={() => selectRun(r.id)}
                  className={`w-full text-left rounded-lg border p-3 text-sm transition-colors ${
                    selectedRun?.run_id === r.id ? "border-primary bg-primary/5" : "border-border hover:bg-secondary/50"
                  }`}
                >
                  <div className="font-semibold">{r.run_number}</div>
                  <div className="text-xs text-muted-foreground">
                    {r.product_name} • {Number(r.actual_good_packets)} pkts • {formatINR(r.cost_per_packet)}/pkt
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>

          {selectedRun && (
            <Card className="lg:col-span-2">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    Cost Breakdown: {selectedRun.run_number} ({selectedRun.product_name})
                  </CardTitle>
                  <Badge variant="default">{formatINR(selectedRun.cost_per_packet)} / packet</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-muted-foreground">
                      <th className="py-2 pr-3">Component</th>
                      <th className="py-2 pr-3 text-right">Actual Qty</th>
                      <th className="py-2 pr-3 text-right">Weighted Avg Rate</th>
                      <th className="py-2 text-right">Total Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRun.lines.map((l: any, idx: number) => (
                      <tr key={idx} className="border-b border-border/50">
                        <td className="py-2 pr-3">{l.material_name}</td>
                        <td className="py-2 pr-3 text-right">{Number(l.actual_qty)} {l.unit}</td>
                        <td className="py-2 pr-3 text-right">{formatINR(l.unit_cost, 3)}</td>
                        <td className="py-2 text-right font-medium">{formatINR(l.total_cost)}</td>
                      </tr>
                    ))}
                    <tr className="border-b border-border/50">
                      <td className="py-2 pr-3" colSpan={3}>Labour Expense</td>
                      <td className="py-2 text-right font-medium">{formatINR(selectedRun.labour_cost)}</td>
                    </tr>
                    <tr className="border-b border-border/50">
                      <td className="py-2 pr-3" colSpan={3}>Gas / Power / Overheads</td>
                      <td className="py-2 text-right font-medium">
                        {formatINR(
                          Number(selectedRun.gas_cost) +
                            Number(selectedRun.power_cost) +
                            Number(selectedRun.other_overhead_cost)
                        )}
                      </td>
                    </tr>
                    <tr className="bg-secondary/40 font-bold">
                      <td className="py-2.5 pr-3" colSpan={3}>
                        Total Production Cost ({Number(selectedRun.good_packets_produced)} good packets)
                      </td>
                      <td className="py-2.5 text-right text-primary">{formatINR(selectedRun.total_production_cost)}</td>
                    </tr>
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
