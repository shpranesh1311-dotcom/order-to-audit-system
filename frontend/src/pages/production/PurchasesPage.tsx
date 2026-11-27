import React, { useCallback, useEffect, useState } from "react";
import { Truck } from "lucide-react";
import { api, getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { formatDateIN, formatINR } from "@/utils/format";

export default function PurchasesPage() {
  const { toast } = useToast();
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [materials, setMaterials] = useState<any[]>([]);
  const [purchases, setPurchases] = useState<any[]>([]);
  const [supplierId, setSupplierId] = useState<number | "">("");
  const [materialId, setMaterialId] = useState<number | "">("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [purchaseDate, setPurchaseDate] = useState(new Date().toISOString().slice(0, 10));
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("kg");
  const [rate, setRate] = useState("");

  const loadAll = useCallback(async () => {
    const [sRes, mRes, pRes] = await Promise.all([
      api.get("/suppliers"),
      api.get("/materials"),
      api.get("/purchases"),
    ]);
    setSuppliers(sRes.data);
    setMaterials(mRes.data);
    setPurchases(pRes.data);
    if (!supplierId && sRes.data.length > 0) setSupplierId(sRes.data[0].id);
    if (!materialId && mRes.data.length > 0) {
      setMaterialId(mRes.data[0].id);
      setUnit(mRes.data[0].base_unit);
    }
  }, [supplierId, materialId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleMaterialChange = (id: number) => {
    setMaterialId(id);
    const mat = materials.find((m) => m.id === id);
    if (mat) setUnit(mat.base_unit);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.post("/purchases", {
        supplier_id: Number(supplierId),
        material_id: Number(materialId),
        invoice_number: invoiceNumber,
        purchase_date: purchaseDate,
        quantity: Number(quantity),
        unit,
        unit_rate: Number(rate),
        idempotency_key: crypto.randomUUID(),
      });
      toast({
        title: `Purchase ${res.data.purchase_number} Recorded`,
        description: `Weighted-average valuation and stock ledger updated automatically.`,
        type: "success",
      });
      setInvoiceNumber("");
      setQuantity("");
      setRate("");
      loadAll();
    } catch (err) {
      toast({ title: "Purchase Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Material Purchases & Suppliers</h1>
        <p className="text-sm text-muted-foreground">
          Record raw & packaging material receipts. Automatically recalculates weighted-average rates and posts to the stock ledger.
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Truck className="h-4 w-4 text-primary" /> Record Purchase Receipt
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="text-xs font-medium">Supplier</label>
                <Select value={supplierId} onChange={(e) => setSupplierId(Number(e.target.value))} required>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.state})
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <label className="text-xs font-medium">Material</label>
                <Select value={materialId} onChange={(e) => handleMaterialChange(Number(e.target.value))} required>
                  {materials.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.material_type} • Avg: {formatINR(m.current_avg_rate)}/{m.base_unit})
                    </option>
                  ))}
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-medium">Supplier Invoice #</label>
                  <Input value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} placeholder="INV-101" required />
                </div>
                <div>
                  <label className="text-xs font-medium">Purchase Date</label>
                  <Input type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} required />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-xs font-medium">Quantity</label>
                  <Input type="number" step="0.001" min="0.001" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
                </div>
                <div>
                  <label className="text-xs font-medium">Unit</label>
                  <Select value={unit} onChange={(e) => setUnit(e.target.value)}>
                    <option value="kg">kg</option>
                    <option value="g">g</option>
                    <option value="litre">litre</option>
                    <option value="ml">ml</option>
                    <option value="piece">piece</option>
                  </Select>
                </div>
                <div>
                  <label className="text-xs font-medium">Rate (₹)</label>
                  <Input type="number" step="0.01" min="0.01" value={rate} onChange={(e) => setRate(e.target.value)} required />
                </div>
              </div>
              {quantity && rate && (
                <div className="text-xs font-semibold text-primary">
                  Total Purchase Value: {formatINR(Number(quantity) * Number(rate))}
                </div>
              )}
              <Button type="submit" className="w-full">Post Purchase & Update Stock</Button>
            </form>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader><CardTitle className="text-base">Purchase History ({purchases.length})</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3">Ref</th>
                  <th className="py-2 pr-3">Date</th>
                  <th className="py-2 pr-3">Supplier</th>
                  <th className="py-2 pr-3">Material</th>
                  <th className="py-2 pr-3 text-right">Qty</th>
                  <th className="py-2 pr-3 text-right">Rate</th>
                  <th className="py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {purchases.map((p) => (
                  <tr key={p.id} className="border-b border-border/50">
                    <td className="py-2 pr-3 font-medium">
                      <div>{p.purchase_number}</div>
                      <div className="text-xs text-muted-foreground">{p.invoice_number}</div>
                    </td>
                    <td className="py-2 pr-3">{formatDateIN(p.purchase_date)}</td>
                    <td className="py-2 pr-3">{p.supplier_name}</td>
                    <td className="py-2 pr-3">
                      {p.material_name} <Badge variant="outline" className="ml-1 capitalize">{p.material_type}</Badge>
                    </td>
                    <td className="py-2 pr-3 text-right">{Number(p.quantity)} {p.unit}</td>
                    <td className="py-2 pr-3 text-right">{formatINR(p.unit_rate)}</td>
                    <td className="py-2 text-right font-semibold">{formatINR(p.total_amount)}</td>
                  </tr>
                ))}
                {purchases.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-muted-foreground">No purchases recorded yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
