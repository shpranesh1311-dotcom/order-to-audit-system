import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Factory, PlusCircle } from "lucide-react";
import { api, getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { formatDateIN, formatINR } from "@/utils/format";

interface Bom {
  id: number;
  product_id: number;
  product_name: string;
  version: number;
  name: string;
  expected_output_qty: string;
}

interface PlannedLine {
  material_id: number;
  material_name: string;
  material_type: string;
  planned_qty: string;
  unit: string;
  available_stock: string;
  avg_rate: string;
}

interface BomPlan {
  bom_id: number;
  product_id: number;
  product_name: string;
  version: number;
  batches: string;
  expected_output_qty: string;
  items: PlannedLine[];
}

interface ProductionRun {
  id: number;
  run_number: string;
  product_name: string;
  bom_version: number;
  run_date: string;
  batches: string;
  expected_output: string;
  actual_good_packets: string;
  damaged_pouches: string;
  wastage_qty: string;
  actual_cartons_used: string;
  yield_variance_pct: string;
  yield_flagged: boolean;
  raw_material_cost: string;
  packaging_cost: string;
  labour_cost: string;
  gas_cost: string;
  power_cost: string;
  other_overhead_cost: string;
  total_cost: string;
  cost_per_packet: string;
  consumptions: {
    id: number;
    material_name: string;
    material_type: string;
    planned_qty: string;
    actual_qty: string;
    unit: string;
    variance_pct: string;
    is_flagged: boolean;
    total_cost: string;
  }[];
}

export default function ProductionPage() {
  const { toast } = useToast();
  const [boms, setBoms] = useState<Bom[]>([]);
  const [runs, setRuns] = useState<ProductionRun[]>([]);
  const [selectedBomId, setSelectedBomId] = useState<number | "">("");
  const [batches, setBatches] = useState("1");
  const [plan, setPlan] = useState<BomPlan | null>(null);
  const [actualRaw, setActualRaw] = useState<Record<number, string>>({});
  const [goodPackets, setGoodPackets] = useState("");
  const [damagedPouches, setDamagedPouches] = useState("0");
  const [wastageQty, setWastageQty] = useState("0");
  const [actualCartons, setActualCartons] = useState("");
  const [labourCost, setLabourCost] = useState("0");
  const [gasCost, setGasCost] = useState("0");
  const [powerCost, setPowerCost] = useState("0");
  const [otherOverhead, setOtherOverhead] = useState("0");
  const [submitting, setSubmitting] = useState(false);

  // Inline overhead editor for existing run
  const [editingOvhId, setEditingOvhId] = useState<number | null>(null);
  const [ovhLabour, setOvhLabour] = useState("0");
  const [ovhGas, setOvhGas] = useState("0");
  const [ovhPower, setOvhPower] = useState("0");

  const loadRunsAndBoms = useCallback(async () => {
    const [bRes, rRes] = await Promise.all([api.get<Bom[]>("/bom"), api.get<ProductionRun[]>("/production/runs")]);
    setBoms(bRes.data);
    setRuns(rRes.data);
    if (!selectedBomId && bRes.data.length > 0) {
      setSelectedBomId(bRes.data[0].id);
    }
  }, [selectedBomId]);

  useEffect(() => {
    loadRunsAndBoms();
  }, [loadRunsAndBoms]);

  useEffect(() => {
    const fetchPlan = async () => {
      if (!selectedBomId || Number(batches) <= 0) return;
      try {
        const res = await api.get<BomPlan>(`/bom/${selectedBomId}/plan?batches=${batches}`);
        setPlan(res.data);
        const defaults: Record<number, string> = {};
        res.data.items
          .filter((i) => i.material_type === "raw")
          .forEach((i) => {
            defaults[i.material_id] = String(Number(i.planned_qty));
          });
        setActualRaw(defaults);
        setGoodPackets(String(Number(res.data.expected_output_qty)));
        const cartonLine = res.data.items.find((i) => i.material_name.toLowerCase().includes("carton"));
        if (cartonLine) setActualCartons(String(Number(cartonLine.planned_qty)));
      } catch {
        setPlan(null);
      }
    };
    fetchPlan();
  }, [selectedBomId, batches]);

  const handleSubmitRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!plan) return;
    setSubmitting(true);
    try {
      const rawItems = plan.items
        .filter((i) => i.material_type === "raw")
        .map((i) => ({
          material_id: i.material_id,
          actual_qty: Number(actualRaw[i.material_id] ?? i.planned_qty),
        }));
      const res = await api.post<ProductionRun>("/production/runs", {
        product_id: plan.product_id,
        bom_id: plan.bom_id,
        batches: Number(batches),
        raw_consumptions: rawItems,
        actual_good_packets: Number(goodPackets),
        damaged_pouches: Number(damagedPouches || 0),
        wastage_qty: Number(wastageQty || 0),
        actual_cartons_used: Number(actualCartons || 0),
        labour_cost: Number(labourCost || 0),
        gas_cost: Number(gasCost || 0),
        power_cost: Number(powerCost || 0),
        other_overhead_cost: Number(otherOverhead || 0),
      });
      toast({
        title: `Production Run ${res.data.run_number} Posted`,
        description: `Good Output: ${Number(res.data.actual_good_packets)} pkts • Cost/pkt: ${formatINR(res.data.cost_per_packet)}`,
        type: "success",
      });
      loadRunsAndBoms();
    } catch (err) {
      toast({ title: "Production Blocked", description: getApiErrorMessage(err), type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  const saveOverheads = async (runId: number) => {
    try {
      await api.patch(`/production/runs/${runId}/overheads`, {
        labour_cost: Number(ovhLabour),
        gas_cost: Number(ovhGas),
        power_cost: Number(ovhPower),
      });
      toast({ title: "Overheads & Cost Per Packet Updated", type: "success" });
      setEditingOvhId(null);
      loadRunsAndBoms();
    } catch (err) {
      toast({ title: "Update Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  const liveYieldPct =
    plan && Number(plan.expected_output_qty) > 0 && goodPackets
      ? ((Number(goodPackets) - Number(plan.expected_output_qty)) / Number(plan.expected_output_qty)) * 100
      : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">BOM & Production Run Management</h1>
        <p className="text-sm text-muted-foreground">
          Execute BOM-driven production runs with automatic raw & packaging deductions, live variance flags (3% tolerance), and packet costing.
        </p>
      </div>

      {/* Create Production Run */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Factory className="h-4 w-4 text-primary" /> Record New Production Run
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmitRun} className="space-y-5">
            <div className="grid sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                <label className="text-xs font-medium">Product & Active BOM</label>
                <Select value={selectedBomId} onChange={(e) => setSelectedBomId(Number(e.target.value))} required>
                  {boms.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.product_name} — {b.name} (v{b.version}, Expected: {Number(b.expected_output_qty)} pkts/batch)
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <label className="text-xs font-medium">Number of Batches</label>
                <Input
                  type="number"
                  step="0.5"
                  min="0.5"
                  value={batches}
                  onChange={(e) => setBatches(e.target.value)}
                  required
                />
              </div>
            </div>

            {plan && (
              <>
                {/* Planned vs Actual Materials Table */}
                <div className="rounded-xl border border-border overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-secondary/50 border-b border-border text-left text-xs text-muted-foreground">
                        <th className="p-3">Material</th>
                        <th className="p-3">Type</th>
                        <th className="p-3 text-right">Planned Qty</th>
                        <th className="p-3 text-right">Avail Stock</th>
                        <th className="p-3 text-right">Actual Issued / Used</th>
                        <th className="p-3 text-right">Live Variance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plan.items.map((item) => {
                        const isRaw = item.material_type === "raw";
                        const isPouch = item.material_name.toLowerCase().includes("pouch");
                        const isCarton = item.material_name.toLowerCase().includes("carton");
                        const actualVal = isRaw
                          ? Number(actualRaw[item.material_id] ?? item.planned_qty)
                          : isPouch
                            ? Number(goodPackets || 0) + Number(damagedPouches || 0)
                            : isCarton
                              ? Number(actualCartons || 0)
                              : Number(item.planned_qty);
                        const plannedVal = Number(item.planned_qty);
                        const varPct = plannedVal > 0 ? ((actualVal - plannedVal) / plannedVal) * 100 : 0;
                        const flagged = Math.abs(varPct) > 3;

                        return (
                          <tr key={item.material_id} className="border-b border-border/50">
                            <td className="p-3 font-medium">{item.material_name}</td>
                            <td className="p-3">
                              <Badge variant="outline" className="capitalize">{item.material_type}</Badge>
                            </td>
                            <td className="p-3 text-right">
                              {plannedVal} {item.unit}
                            </td>
                            <td className="p-3 text-right">
                              {Number(item.available_stock)} {item.unit}
                            </td>
                            <td className="p-3 text-right">
                              {isRaw ? (
                                <Input
                                  type="number"
                                  step="0.001"
                                  min="0"
                                  className="w-28 ml-auto h-9 text-right"
                                  value={actualRaw[item.material_id] ?? ""}
                                  onChange={(e) =>
                                    setActualRaw((prev) => ({ ...prev, [item.material_id]: e.target.value }))
                                  }
                                />
                              ) : (
                                <span className="font-medium">
                                  {actualVal} {item.unit} {isPouch ? "(Good + Damaged)" : ""}
                                </span>
                              )}
                            </td>
                            <td className="p-3 text-right">
                              <Badge variant={flagged ? "danger" : "success"}>
                                {varPct > 0 ? "+" : ""}
                                {varPct.toFixed(2)}%
                              </Badge>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Output, Damaged Packaging, Cartons, Overheads */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <label className="text-xs font-medium">
                      Good Packets (Exp: {Number(plan.expected_output_qty)})
                    </label>
                    <Input
                      type="number"
                      min="1"
                      value={goodPackets}
                      onChange={(e) => setGoodPackets(e.target.value)}
                      required
                    />
                    <div className="mt-1">
                      <Badge variant={Math.abs(liveYieldPct) > 3 ? "danger" : "success"}>
                        Yield Var: {liveYieldPct > 0 ? "+" : ""}
                        {liveYieldPct.toFixed(2)}%
                      </Badge>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-medium">Damaged Pouches</label>
                    <Input
                      type="number"
                      min="0"
                      value={damagedPouches}
                      onChange={(e) => setDamagedPouches(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium">Actual Cartons Used</label>
                    <Input
                      type="number"
                      min="0"
                      value={actualCartons}
                      onChange={(e) => setActualCartons(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium">Wastage / Scrap (kg)</label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={wastageQty}
                      onChange={(e) => setWastageQty(e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <label className="text-xs font-medium">Labour Expense (₹)</label>
                    <Input type="number" step="0.01" min="0" value={labourCost} onChange={(e) => setLabourCost(e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs font-medium">Gas Expense (₹)</label>
                    <Input type="number" step="0.01" min="0" value={gasCost} onChange={(e) => setGasCost(e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs font-medium">Power / Electricity (₹)</label>
                    <Input type="number" step="0.01" min="0" value={powerCost} onChange={(e) => setPowerCost(e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs font-medium">Other Overheads (₹)</label>
                    <Input type="number" step="0.01" min="0" value={otherOverhead} onChange={(e) => setOtherOverhead(e.target.value)} />
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button type="submit" disabled={submitting} size="lg">
                    <PlusCircle className="h-4 w-4" />
                    <span>{submitting ? "Posting Run..." : "Complete & Post Production Run"}</span>
                  </Button>
                </div>
              </>
            )}
          </form>
        </CardContent>
      </Card>

      {/* Production History */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Production History & Variance ({runs.length})</h2>
        {runs.map((run) => (
          <Card key={run.id}>
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <CardTitle>{run.run_number}</CardTitle>
                    <Badge variant="outline">{run.product_name} (BOM v{run.bom_version})</Badge>
                    <Badge variant={run.yield_flagged ? "danger" : "success"} className="gap-1">
                      {run.yield_flagged ? <AlertTriangle className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
                      Yield {run.yield_variance_pct}%
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Date: {formatDateIN(run.run_date)} • Batches: {Number(run.batches)} • Expected: {Number(run.expected_output)} •
                    Good: {Number(run.actual_good_packets)} • Damaged Pouches: {Number(run.damaged_pouches)} • Cartons: {Number(run.actual_cartons_used)}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-primary">
                    {formatINR(run.cost_per_packet)} / packet
                  </div>
                  <div className="text-xs text-muted-foreground">Total Cost: {formatINR(run.total_cost)}</div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-2">
                {run.consumptions.map((c) => (
                  <div key={c.id} className="rounded-lg border border-border p-2.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">{c.material_name}</span>
                      <Badge variant={c.is_flagged ? "danger" : "success"}>{c.variance_pct}%</Badge>
                    </div>
                    <div className="text-muted-foreground mt-1">
                      Plan: {Number(c.planned_qty)} | Act: {Number(c.actual_qty)} {c.unit}
                    </div>
                    <div className="font-medium mt-0.5">Cost: {formatINR(c.total_cost)}</div>
                  </div>
                ))}
              </div>

              {editingOvhId === run.id ? (
                <div className="flex flex-wrap items-end gap-3 bg-secondary/50 p-3 rounded-lg">
                  <div>
                    <label className="text-xs">Labour (₹)</label>
                    <Input type="number" className="w-28 h-8" value={ovhLabour} onChange={(e) => setOvhLabour(e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs">Gas (₹)</label>
                    <Input type="number" className="w-28 h-8" value={ovhGas} onChange={(e) => setOvhGas(e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs">Power (₹)</label>
                    <Input type="number" className="w-28 h-8" value={ovhPower} onChange={(e) => setOvhPower(e.target.value)} />
                  </div>
                  <Button size="sm" onClick={() => saveOverheads(run.id)}>Save Overheads</Button>
                  <Button size="sm" variant="outline" onClick={() => setEditingOvhId(null)}>Cancel</Button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between text-xs text-muted-foreground pt-1">
                  <span>
                    RM: {formatINR(run.raw_material_cost)} | PM: {formatINR(run.packaging_cost)} | Labour:{" "}
                    {formatINR(run.labour_cost)} | Gas/Power:{" "}
                    {formatINR(Number(run.gas_cost) + Number(run.power_cost))}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setEditingOvhId(run.id);
                      setOvhLabour(String(Number(run.labour_cost)));
                      setOvhGas(String(Number(run.gas_cost)));
                      setOvhPower(String(Number(run.power_cost)));
                    }}
                  >
                    Update Overheads
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
