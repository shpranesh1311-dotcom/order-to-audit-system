import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Minus, Plus, RefreshCw, Search, Send, Wifi, WifiOff } from "lucide-react";
import { api, getApiErrorMessage } from "@/api/client";
import {
  cacheMasterData,
  getCachedMasterData,
  getPendingOfflineOrders,
  queueOfflineOrder,
  removeOfflineOrder,
} from "@/offline/offlineOrders";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { formatINR } from "@/utils/format";

interface Customer {
  id: number;
  name: string;
  customer_type: string;
  state: string;
}

interface Product {
  id: number;
  code: string;
  name: string;
  category: string;
  pack_size: string;
  pack_unit: string;
  selling_price: string;
  gst_rate: string;
  available_stock: string;
}

export default function SalesmanOrderPage() {
  const { toast } = useToast();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | "">("");
  const [customerSearch, setCustomerSearch] = useState("");
  const [productSearch, setProductSearch] = useState("");
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [notes, setNotes] = useState("");
  const [online, setOnline] = useState<boolean>(navigator.onLine);
  const [pendingCount, setPendingCount] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const refreshPendingCount = useCallback(async () => {
    const items = await getPendingOfflineOrders();
    setPendingCount(items.length);
  }, []);

  const syncOfflineQueue = useCallback(async () => {
    if (!navigator.onLine) return;
    const pending = await getPendingOfflineOrders();
    if (pending.length === 0) return;
    setSyncing(true);
    let synced = 0;
    for (const ord of pending) {
      try {
        await api.post("/orders", {
          customer_id: ord.customer_id,
          order_date: ord.order_date,
          notes: ord.notes,
          idempotency_key: ord.idempotency_key,
          offline_created_at: ord.offline_created_at,
          items: ord.items.map((i) => ({ product_id: i.product_id, quantity: i.quantity })),
        });
        await removeOfflineOrder(ord.idempotency_key);
        synced++;
      } catch (err) {
        toast({
          title: `Sync failed for ${ord.customer_name}`,
          description: getApiErrorMessage(err),
          type: "error",
        });
      }
    }
    setSyncing(false);
    await refreshPendingCount();
    if (synced > 0) {
      toast({
        title: `Synced ${synced} offline order${synced > 1 ? "s" : ""}`,
        description: "Idempotency keys ensured zero duplicate orders.",
        type: "success",
      });
    }
  }, [refreshPendingCount, toast]);

  useEffect(() => {
    const handleOnline = () => {
      setOnline(true);
      syncOfflineQueue();
    };
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    refreshPendingCount();
    if (navigator.onLine) syncOfflineQueue();
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [refreshPendingCount, syncOfflineQueue]);

  useEffect(() => {
    const loadMaster = async () => {
      try {
        const [cRes, pRes] = await Promise.all([
          api.get<Customer[]>("/customers"),
          api.get<Product[]>(
            `/products?active_only=true${selectedCustomerId ? `&customer_id=${selectedCustomerId}` : ""}`
          ),
        ]);
        setCustomers(cRes.data);
        setProducts(pRes.data);
        await cacheMasterData("customers", cRes.data);
        await cacheMasterData("products", pRes.data);
        if (!selectedCustomerId && cRes.data.length > 0) {
          setSelectedCustomerId(cRes.data[0].id);
        }
      } catch {
        const cachedC = await getCachedMasterData<Customer[]>("customers");
        const cachedP = await getCachedMasterData<Product[]>("products");
        if (cachedC) {
          setCustomers(cachedC);
          if (!selectedCustomerId && cachedC.length > 0) setSelectedCustomerId(cachedC[0].id);
        }
        if (cachedP) setProducts(cachedP);
      }
    };
    loadMaster();
  }, [selectedCustomerId]);

  const filteredCustomers = useMemo(() => {
    const q = customerSearch.trim().toLowerCase();
    return customers.filter((c) => !q || c.name.toLowerCase().includes(q) || c.state.toLowerCase().includes(q));
  }, [customers, customerSearch]);

  const filteredProducts = useMemo(() => {
    const q = productSearch.trim().toLowerCase();
    return products.filter(
      (p) => !q || p.name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q)
    );
  }, [products, productSearch]);

  const selectedItems = useMemo(() => {
    return products
      .filter((p) => (quantities[p.id] || 0) > 0)
      .map((p) => ({
        product_id: p.id,
        product_name: p.name,
        quantity: quantities[p.id],
        unit_price: Number(p.selling_price),
        gst_rate: Number(p.gst_rate),
      }));
  }, [products, quantities]);

  const subtotal = useMemo(
    () => selectedItems.reduce((acc, it) => acc + it.quantity * it.unit_price, 0),
    [selectedItems]
  );
  const estimatedTax = useMemo(
    () => selectedItems.reduce((acc, it) => acc + (it.quantity * it.unit_price * it.gst_rate) / 100, 0),
    [selectedItems]
  );

  const adjustQty = (productId: number, delta: number) => {
    setQuantities((prev) => {
      const next = Math.max(0, (prev[productId] || 0) + delta);
      return { ...prev, [productId]: next };
    });
  };

  const handleSubmitOrder = async () => {
    if (!selectedCustomerId) {
      toast({ title: "Select a customer first", type: "error" });
      return;
    }
    if (selectedItems.length === 0) {
      toast({ title: "Add at least one product", type: "error" });
      return;
    }

    const customer = customers.find((c) => c.id === Number(selectedCustomerId));
    const idempotencyKey =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `ord-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const nowIso = new Date().toISOString();
    const todayStr = nowIso.slice(0, 10);

    setSubmitting(true);
    try {
      if (!navigator.onLine) {
        await queueOfflineOrder({
          idempotency_key: idempotencyKey,
          customer_id: Number(selectedCustomerId),
          customer_name: customer?.name || `Customer #${selectedCustomerId}`,
          order_date: todayStr,
          offline_created_at: nowIso,
          notes: notes || undefined,
          items: selectedItems.map((i) => ({
            product_id: i.product_id,
            product_name: i.product_name,
            quantity: i.quantity,
            unit_price: i.unit_price,
          })),
          total_estimated: subtotal + estimatedTax,
          status: "pending",
        });
        await refreshPendingCount();
        setQuantities({});
        setNotes("");
        toast({
          title: "Saved Offline (IndexedDB)",
          description: "Order queued safely and will auto-sync when connectivity returns.",
          type: "success",
        });
        return;
      }

      const res = await api.post("/orders", {
        customer_id: Number(selectedCustomerId),
        order_date: todayStr,
        notes: notes || undefined,
        idempotency_key: idempotencyKey,
        items: selectedItems.map((i) => ({ product_id: i.product_id, quantity: i.quantity })),
      });
      setQuantities({});
      setNotes("");
      toast({
        title: `Order ${res.data.order_number} Submitted`,
        description: `Total: ${formatINR(res.data.total_amount)}`,
        type: "success",
      });
    } catch (err) {
      // Network failure fallback to IndexedDB
      if (!navigator.onLine || getApiErrorMessage(err).includes("Network Error")) {
        await queueOfflineOrder({
          idempotency_key: idempotencyKey,
          customer_id: Number(selectedCustomerId),
          customer_name: customer?.name || `Customer #${selectedCustomerId}`,
          order_date: todayStr,
          offline_created_at: nowIso,
          notes: notes || undefined,
          items: selectedItems.map((i) => ({
            product_id: i.product_id,
            product_name: i.product_name,
            quantity: i.quantity,
            unit_price: i.unit_price,
          })),
          total_estimated: subtotal + estimatedTax,
          status: "pending",
        });
        await refreshPendingCount();
        setQuantities({});
        toast({ title: "Saved Offline", description: "Connection lost — queued locally.", type: "success" });
      } else {
        toast({ title: "Order Failed", description: getApiErrorMessage(err), type: "error" });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4 pb-28">
      {/* Status Banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card p-3">
        <div className="flex items-center gap-2">
          {online ? (
            <Badge variant="success" className="gap-1.5">
              <Wifi className="h-3.5 w-3.5" /> Online
            </Badge>
          ) : (
            <Badge variant="warning" className="gap-1.5">
              <WifiOff className="h-3.5 w-3.5" /> Offline Mode
            </Badge>
          )}
          <span className="text-xs text-muted-foreground">
            Pending Sync: <strong className="text-foreground">{pendingCount}</strong>
          </span>
        </div>
        {pendingCount > 0 && online && (
          <Button size="sm" variant="outline" onClick={syncOfflineQueue} disabled={syncing}>
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} />
            <span>{syncing ? "Syncing..." : "Sync Now"}</span>
          </Button>
        )}
      </div>

      {/* Customer Selector */}
      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <label className="text-sm font-semibold">1. Select Customer</label>
            <div className="relative w-44">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-3 text-muted-foreground" />
              <Input
                value={customerSearch}
                onChange={(e) => setCustomerSearch(e.target.value)}
                placeholder="Filter customer..."
                className="h-9 pl-8 text-xs"
              />
            </div>
          </div>
          <Select
            value={selectedCustomerId}
            onChange={(e) => setSelectedCustomerId(Number(e.target.value))}
            className="h-11 text-base"
          >
            <option value="">-- Choose customer --</option>
            {filteredCustomers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.customer_type} • {c.state})
              </option>
            ))}
          </Select>
        </CardContent>
      </Card>

      {/* Product Search */}
      <div className="relative">
        <Search className="h-4 w-4 absolute left-3.5 top-3.5 text-muted-foreground" />
        <Input
          value={productSearch}
          onChange={(e) => setProductSearch(e.target.value)}
          placeholder="Search snacks (Murukku, Mixture...)"
          className="pl-10 h-11"
        />
      </div>

      {/* Product Cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {filteredProducts.map((prod) => {
          const qty = quantities[prod.id] || 0;
          return (
            <Card
              key={prod.id}
              className={`transition-colors ${qty > 0 ? "border-primary ring-1 ring-primary/30" : ""}`}
            >
              <CardContent className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold text-base">{prod.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {prod.code} • {Number(prod.pack_size)} {prod.pack_unit}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-primary">{formatINR(prod.selling_price)}</div>
                    <div className="text-[11px] text-muted-foreground">+ {prod.gst_rate}% GST</div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs text-muted-foreground">
                    Avail: <strong>{Number(prod.available_stock)}</strong> pkts
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-11 w-11 rounded-xl"
                      onClick={() => adjustQty(prod.id, -10)}
                      aria-label="Decrease 10"
                    >
                      <Minus className="h-4 w-4" />
                    </Button>
                    <Input
                      type="number"
                      min={0}
                      value={qty || ""}
                      placeholder="0"
                      onChange={(e) =>
                        setQuantities((prev) => ({
                          ...prev,
                          [prod.id]: Math.max(0, Number(e.target.value) || 0),
                        }))
                      }
                      className="w-20 h-11 text-center font-semibold text-base"
                    />
                    <Button
                      type="button"
                      variant="default"
                      size="icon"
                      className="h-11 w-11 rounded-xl"
                      onClick={() => adjustQty(prod.id, 10)}
                      aria-label="Increase 10"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                {qty > 0 && (
                  <div className="text-xs font-medium text-right text-primary">
                    Line Subtotal: {formatINR(qty * Number(prod.selling_price))}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Notes */}
      <Input
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Optional delivery note for Factory Admin..."
      />

      {/* Sticky Order Summary Bar */}
      <div className="fixed bottom-16 md:bottom-0 left-0 md:left-64 right-0 z-30 border-t border-border bg-card/95 backdrop-blur px-4 py-3 shadow-lg">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div>
            <div className="text-xs text-muted-foreground">
              {selectedItems.length} item{selectedItems.length === 1 ? "" : "s"} • Subtotal{" "}
              {formatINR(subtotal)}
            </div>
            <div className="text-base sm:text-lg font-bold">
              Est. Total: {formatINR(subtotal + estimatedTax)}
            </div>
          </div>
          <Button
            size="lg"
            onClick={handleSubmitOrder}
            disabled={submitting || selectedItems.length === 0}
            className="shrink-0"
          >
            <Send className="h-4 w-4" />
            <span>{submitting ? "Submitting..." : online ? "Submit Order" : "Save Offline"}</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
