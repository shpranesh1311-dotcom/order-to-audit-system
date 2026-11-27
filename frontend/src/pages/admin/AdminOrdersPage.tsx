import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, Pencil, XCircle } from "lucide-react";
import { api, getApiErrorMessage } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { formatDateIN, formatINR } from "@/utils/format";
import { orderStatusVariant } from "@/pages/salesman/SalesmanHistoryPage";

interface OrderItem {
  id: number;
  product_id: number;
  product_name: string;
  quantity: string;
  unit_price: string;
  gst_rate: string;
  line_subtotal: string;
  available_stock: string | null;
  shortage_qty: string | null;
}

interface Order {
  id: number;
  order_number: string;
  customer_id: number;
  customer_name: string;
  customer_state: string;
  salesman_name: string;
  order_date: string;
  status: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  notes: string | null;
  rejection_reason: string | null;
  invoice_id: number | null;
  invoice_number: string | null;
  items: OrderItem[];
}

export default function AdminOrdersPage() {
  const { toast } = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [editingOrderId, setEditingOrderId] = useState<number | null>(null);
  const [editItems, setEditItems] = useState<{ product_id: number; quantity: number; unit_price: number }[]>([]);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<Order[]>(`/orders${statusFilter ? `?status=${statusFilter}` : ""}`);
      setOrders(res.data);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  const handleApprove = async (ord: Order) => {
    try {
      await api.post(`/orders/${ord.id}/approve`);
      toast({ title: `Order ${ord.order_number} Approved`, description: "Stock reserved successfully.", type: "success" });
      loadOrders();
    } catch (err) {
      toast({ title: "Approval Blocked", description: getApiErrorMessage(err), type: "error" });
    }
  };

  const handleGenerateInvoice = async (ord: Order) => {
    try {
      const res = await api.post(`/invoices/from-order/${ord.id}`);
      toast({
        title: `Invoice ${res.data.invoice_number} Generated`,
        description: `Tax Type: ${res.data.tax_type.replace("_", " + ")} • Total: ${formatINR(res.data.grand_total)}`,
        type: "success",
      });
      loadOrders();
    } catch (err) {
      toast({ title: "Invoice Error", description: getApiErrorMessage(err), type: "error" });
    }
  };

  const startEdit = (ord: Order) => {
    setEditingOrderId(ord.id);
    setEditItems(
      ord.items.map((it) => ({
        product_id: it.product_id,
        quantity: Number(it.quantity),
        unit_price: Number(it.unit_price),
      }))
    );
  };

  const saveEdit = async (orderId: number) => {
    try {
      await api.patch(`/orders/${orderId}`, { items: editItems });
      toast({ title: "Order Updated", type: "success" });
      setEditingOrderId(null);
      loadOrders();
    } catch (err) {
      toast({ title: "Update Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  const submitReject = async (orderId: number) => {
    if (!rejectReason.trim()) {
      toast({ title: "Provide a rejection reason", type: "error" });
      return;
    }
    try {
      await api.post(`/orders/${orderId}/reject`, { reason: rejectReason.trim() });
      toast({ title: "Order Rejected", type: "success" });
      setRejectingId(null);
      setRejectReason("");
      loadOrders();
    } catch (err) {
      toast({ title: "Reject Failed", description: getApiErrorMessage(err), type: "error" });
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Incoming Orders & Verification</h1>
          <p className="text-sm text-muted-foreground">
            Verify quantities, inspect available finished goods, approve orders, and generate GST invoices.
          </p>
        </div>
        <div className="w-48">
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All Statuses</option>
            <option value="submitted">Submitted</option>
            <option value="approved">Approved</option>
            <option value="invoiced">Invoiced</option>
            <option value="dispatched">Dispatched</option>
            <option value="rejected">Rejected</option>
          </Select>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading orders...</div>
      ) : orders.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            No orders matching filter.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {orders.map((ord) => {
            const hasShortage = ord.items.some((i) => Number(i.shortage_qty || 0) > 0);
            const isEditing = editingOrderId === ord.id;
            return (
              <Card key={ord.id}>
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <CardTitle>{ord.order_number}</CardTitle>
                        <Badge variant={orderStatusVariant(ord.status)} className="capitalize">
                          {ord.status}
                        </Badge>
                        {ord.status === "submitted" && (
                          hasShortage ? (
                            <Badge variant="danger" className="gap-1">
                              <AlertTriangle className="h-3 w-3" /> Stock Shortage
                            </Badge>
                          ) : (
                            <Badge variant="success" className="gap-1">
                              <CheckCircle2 className="h-3 w-3" /> Stock Sufficient
                            </Badge>
                          )
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        Customer: <strong className="text-foreground">{ord.customer_name}</strong> ({ord.customer_state}) •
                        Salesman: {ord.salesman_name} • {formatDateIN(ord.order_date)}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold">{formatINR(ord.total_amount)}</div>
                      <div className="text-xs text-muted-foreground">
                        Taxable {formatINR(ord.subtotal)} + GST {formatINR(ord.tax_amount)}
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-xs text-muted-foreground">
                          <th className="py-2 pr-3">Product</th>
                          <th className="py-2 pr-3 text-right">Requested</th>
                          <th className="py-2 pr-3 text-right">Unit Price</th>
                          <th className="py-2 pr-3 text-right">Available FG</th>
                          <th className="py-2 pr-3 text-right">Shortage</th>
                          <th className="py-2 text-right">Line Subtotal</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ord.items.map((it, idx) => {
                          const shortage = Number(it.shortage_qty || 0);
                          return (
                            <tr key={it.id} className="border-b border-border/50">
                              <td className="py-2.5 pr-3 font-medium">{it.product_name}</td>
                              <td className="py-2.5 pr-3 text-right">
                                {isEditing ? (
                                  <Input
                                    type="number"
                                    className="w-24 ml-auto h-8 text-right"
                                    value={editItems[idx]?.quantity ?? 0}
                                    onChange={(e) => {
                                      const copy = [...editItems];
                                      copy[idx] = { ...copy[idx], quantity: Number(e.target.value) };
                                      setEditItems(copy);
                                    }}
                                  />
                                ) : (
                                  `${Number(it.quantity)} pkts`
                                )}
                              </td>
                              <td className="py-2.5 pr-3 text-right">
                                {isEditing ? (
                                  <Input
                                    type="number"
                                    step="0.01"
                                    className="w-24 ml-auto h-8 text-right"
                                    value={editItems[idx]?.unit_price ?? 0}
                                    onChange={(e) => {
                                      const copy = [...editItems];
                                      copy[idx] = { ...copy[idx], unit_price: Number(e.target.value) };
                                      setEditItems(copy);
                                    }}
                                  />
                                ) : (
                                  formatINR(it.unit_price)
                                )}
                              </td>
                              <td className="py-2.5 pr-3 text-right">
                                {it.available_stock !== null ? `${Number(it.available_stock)} pkts` : "-"}
                              </td>
                              <td className="py-2.5 pr-3 text-right">
                                {shortage > 0 ? (
                                  <span className="font-semibold text-red-600 dark:text-red-400">
                                    {shortage} pkts
                                  </span>
                                ) : (
                                  <span className="text-emerald-600 dark:text-emerald-400">0</span>
                                )}
                              </td>
                              <td className="py-2.5 text-right font-medium">{formatINR(it.line_subtotal)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {rejectingId === ord.id && (
                    <div className="flex flex-wrap gap-2 items-center bg-red-50/60 dark:bg-red-950/30 p-3 rounded-lg border border-red-500/30">
                      <Input
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        placeholder="Reason for rejecting order..."
                        className="flex-1 min-w-[200px]"
                      />
                      <Button variant="destructive" size="sm" onClick={() => submitReject(ord.id)}>
                        Confirm Reject
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => setRejectingId(null)}>
                        Cancel
                      </Button>
                    </div>
                  )}

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                    <div className="text-xs text-muted-foreground">
                      {ord.invoice_number && <span>Invoice: <strong>{ord.invoice_number}</strong></span>}
                      {ord.rejection_reason && (
                        <span className="text-red-600 dark:text-red-400">Reason: {ord.rejection_reason}</span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {ord.status === "submitted" && !isEditing && (
                        <>
                          <Button variant="outline" size="sm" onClick={() => startEdit(ord)}>
                            <Pencil className="h-3.5 w-3.5" /> Edit
                          </Button>
                          <Button variant="destructive" size="sm" onClick={() => setRejectingId(ord.id)}>
                            <XCircle className="h-3.5 w-3.5" /> Reject
                          </Button>
                          <Button size="sm" onClick={() => handleApprove(ord)}>
                            <CheckCircle2 className="h-3.5 w-3.5" /> Approve Order
                          </Button>
                        </>
                      )}
                      {isEditing && (
                        <>
                          <Button variant="outline" size="sm" onClick={() => setEditingOrderId(null)}>
                            Cancel
                          </Button>
                          <Button size="sm" onClick={() => saveEdit(ord.id)}>
                            Save Changes
                          </Button>
                        </>
                      )}
                      {ord.status === "approved" && !ord.invoice_id && (
                        <>
                          <Button variant="destructive" size="sm" onClick={() => setRejectingId(ord.id)}>
                            Cancel & Release Stock
                          </Button>
                          <Button size="sm" onClick={() => handleGenerateInvoice(ord)}>
                            <FileText className="h-3.5 w-3.5" /> Generate GST Invoice
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
