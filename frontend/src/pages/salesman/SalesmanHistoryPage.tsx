import React, { useEffect, useState } from "react";
import { api } from "@/api/client";
import { getPendingOfflineOrders, type OfflineOrderPayload } from "@/offline/offlineOrders";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateIN, formatINR } from "@/utils/format";

interface OrderItem {
  id: number;
  product_name: string;
  quantity: string;
  unit_price: string;
  line_subtotal: string;
}

interface Order {
  id: number;
  order_number: string;
  customer_name: string;
  customer_state: string;
  order_date: string;
  status: string;
  total_amount: string;
  rejection_reason: string | null;
  invoice_number: string | null;
  items: OrderItem[];
}

export function orderStatusVariant(status: string) {
  switch (status) {
    case "approved":
      return "default";
    case "invoiced":
      return "warning";
    case "dispatched":
      return "success";
    case "rejected":
      return "danger";
    default:
      return "secondary";
  }
}

export default function SalesmanHistoryPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [offlineOrders, setOfflineOrders] = useState<OfflineOrderPayload[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setOfflineOrders(await getPendingOfflineOrders());
      try {
        const res = await api.get<Order[]>("/orders");
        setOrders(res.data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">My Sales Orders & Status</h1>
        <Badge variant="outline">{orders.length} Submitted</Badge>
      </div>

      {offlineOrders.length > 0 && (
        <Card className="border-amber-500/40 bg-amber-50/40 dark:bg-amber-950/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Pending Offline Queue ({offlineOrders.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {offlineOrders.map((o) => (
              <div key={o.idempotency_key} className="flex justify-between text-sm border-b border-border/50 pb-2">
                <div>
                  <div className="font-medium">{o.customer_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {o.items.map((i) => `${i.product_name} × ${i.quantity}`).join(", ")}
                  </div>
                </div>
                <div className="text-right">
                  <Badge variant="warning">Pending Sync</Badge>
                  <div className="text-xs font-semibold mt-1">{formatINR(o.total_estimated)}</div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading orders...</div>
      ) : orders.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            No orders submitted yet. Place your first order from the Mobile Order screen.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {orders.map((ord) => (
            <Card key={ord.id}>
              <CardContent className="p-4 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold">{ord.order_number}</div>
                    <div className="text-sm text-muted-foreground">
                      {ord.customer_name} • {ord.customer_state} • {formatDateIN(ord.order_date)}
                    </div>
                  </div>
                  <div className="text-right">
                    <Badge variant={orderStatusVariant(ord.status)} className="capitalize">
                      {ord.status}
                    </Badge>
                    <div className="font-bold mt-1">{formatINR(ord.total_amount)}</div>
                  </div>
                </div>
                <div className="text-xs text-muted-foreground border-t border-border pt-2">
                  {ord.items.map((it) => (
                    <div key={it.id} className="flex justify-between">
                      <span>
                        {it.product_name} × {Number(it.quantity)}
                      </span>
                      <span>{formatINR(it.line_subtotal)}</span>
                    </div>
                  ))}
                </div>
                {ord.invoice_number && (
                  <div className="text-xs text-emerald-700 dark:text-emerald-300 font-medium">
                    Invoice: {ord.invoice_number}
                  </div>
                )}
                {ord.rejection_reason && (
                  <div className="text-xs text-red-600 dark:text-red-400">
                    Rejected: {ord.rejection_reason}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
