import React, { useCallback, useEffect, useState } from "react";
import { api, getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { formatINR } from "@/utils/format";

export default function AdminMastersPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<"products" | "customers" | "suppliers">("products");
  const [products, setProducts] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);

  // Quick add states
  const [pCode, setPCode] = useState("");
  const [pName, setPName] = useState("");
  const [pPrice, setPPrice] = useState("");
  const [pPack, setPPack] = useState("200");
  const [cName, setCName] = useState("");
  const [cType, setCType] = useState("retailer");
  const [cState, setCState] = useState("Tamil Nadu");
  const [cAddr, setCAddr] = useState("");
  const [cPhone, setCPhone] = useState("");

  const loadAll = useCallback(async () => {
    const [p, c, s] = await Promise.all([
      api.get("/products"),
      api.get("/customers"),
      api.get("/suppliers"),
    ]);
    setProducts(p.data);
    setCustomers(c.data);
    setSuppliers(s.data);
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const addProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/products", {
        code: pCode,
        name: pName,
        category: "Traditional Savouries",
        pack_size: Number(pPack),
        pack_unit: "g",
        carton_capacity: 20,
        selling_price: Number(pPrice),
        hsn_code: "19059090",
        gst_rate: 5,
      });
      toast({ title: "Product Added", type: "success" });
      setPCode("");
      setPName("");
      setPPrice("");
      loadAll();
    } catch (err) {
      toast({ title: "Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  const addCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/customers", {
        name: cName,
        customer_type: cType,
        state: cState,
        address: cAddr,
        contact_number: cPhone,
      });
      toast({ title: "Customer Added", type: "success" });
      setCName("");
      setCAddr("");
      setCPhone("");
      loadAll();
    } catch (err) {
      toast({ title: "Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Master Data Management</h1>
          <p className="text-sm text-muted-foreground">Products, selling prices, customers, and suppliers.</p>
        </div>
        <div className="flex gap-2">
          {(["products", "customers", "suppliers"] as const).map((t) => (
            <Button key={t} variant={tab === t ? "default" : "outline"} size="sm" onClick={() => setTab(t)} className="capitalize">
              {t}
            </Button>
          ))}
        </div>
      </div>

      {tab === "products" && (
        <div className="grid lg:grid-cols-3 gap-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Add Product</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={addProduct} className="space-y-3">
                <Input value={pCode} onChange={(e) => setPCode(e.target.value)} placeholder="Code (e.g. FG-RIB-200)" required />
                <Input value={pName} onChange={(e) => setPName(e.target.value)} placeholder="Name (e.g. Ribbon Pakoda 200 g)" required />
                <div className="grid grid-cols-2 gap-2">
                  <Input type="number" value={pPack} onChange={(e) => setPPack(e.target.value)} placeholder="Pack g" required />
                  <Input type="number" step="0.01" value={pPrice} onChange={(e) => setPPrice(e.target.value)} placeholder="Price (₹)" required />
                </div>
                <Button type="submit" className="w-full">Save Product</Button>
              </form>
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle className="text-base">Product Catalog ({products.length})</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3">Code</th>
                    <th className="py-2 pr-3">Product</th>
                    <th className="py-2 pr-3">HSN</th>
                    <th className="py-2 pr-3 text-right">Price</th>
                    <th className="py-2 pr-3 text-right">GST</th>
                    <th className="py-2 text-right">Avail FG</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <tr key={p.id} className="border-b border-border/50">
                      <td className="py-2 pr-3 font-mono text-xs">{p.code}</td>
                      <td className="py-2 pr-3 font-medium">{p.name}</td>
                      <td className="py-2 pr-3">{p.hsn_code}</td>
                      <td className="py-2 pr-3 text-right">{formatINR(p.selling_price)}</td>
                      <td className="py-2 pr-3 text-right">{p.gst_rate}%</td>
                      <td className="py-2 text-right font-semibold">{Number(p.available_stock)} pkts</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "customers" && (
        <div className="grid lg:grid-cols-3 gap-6">
          <Card>
            <CardHeader><CardTitle className="text-base">Add Customer</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={addCustomer} className="space-y-3">
                <Input value={cName} onChange={(e) => setCName(e.target.value)} placeholder="Customer Name" required />
                <div className="grid grid-cols-2 gap-2">
                  <Select value={cType} onChange={(e) => setCType(e.target.value)}>
                    <option value="retailer">Retailer</option>
                    <option value="distributor">Distributor</option>
                  </Select>
                  <Input value={cState} onChange={(e) => setCState(e.target.value)} placeholder="State" required />
                </div>
                <Input value={cAddr} onChange={(e) => setCAddr(e.target.value)} placeholder="Full Address" required />
                <Input value={cPhone} onChange={(e) => setCPhone(e.target.value)} placeholder="Phone" required />
                <Button type="submit" className="w-full">Save Customer</Button>
              </form>
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle className="text-base">Customers ({customers.length})</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3">Name</th>
                    <th className="py-2 pr-3">Type</th>
                    <th className="py-2 pr-3">State</th>
                    <th className="py-2 pr-3">GSTIN</th>
                    <th className="py-2">Contact</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((c) => (
                    <tr key={c.id} className="border-b border-border/50">
                      <td className="py-2 pr-3 font-medium">{c.name}</td>
                      <td className="py-2 pr-3"><Badge variant="secondary" className="capitalize">{c.customer_type}</Badge></td>
                      <td className="py-2 pr-3">{c.state}</td>
                      <td className="py-2 pr-3 font-mono text-xs">{c.gstin || "-"}</td>
                      <td className="py-2 text-xs">{c.contact_number}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "suppliers" && (
        <Card>
          <CardHeader><CardTitle className="text-base">Registered Suppliers ({suppliers.length})</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3">Supplier</th>
                  <th className="py-2 pr-3">State</th>
                  <th className="py-2 pr-3">GSTIN</th>
                  <th className="py-2 pr-3">Address</th>
                  <th className="py-2">Contact</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((s) => (
                  <tr key={s.id} className="border-b border-border/50">
                    <td className="py-2 pr-3 font-medium">{s.name}</td>
                    <td className="py-2 pr-3">{s.state}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{s.gstin || "-"}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">{s.address}</td>
                    <td className="py-2 text-xs">{s.contact_number}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
