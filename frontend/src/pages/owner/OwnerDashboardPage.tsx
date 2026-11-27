import React, { useEffect, useState } from 'react'
import { api as apiClient } from '../../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Badge } from '../../components/ui/badge'
import { formatINR } from '../../utils/format'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar
} from 'recharts'

interface KPIs {
  orders_today: number
  pending_approvals: number
  outstanding_dues: number | string
  total_sales: number | string
  finished_goods_available: number | string
}

interface SalesTrend {
  date: string
  sales: number | string
}

interface StockLevel {
  name: string
  physical: number
  reserved: number
  available: number
  reorder_level: number
}

interface VarianceAlert {
  run_number: string
  product: string
  metric: string
  planned: number | string
  actual: number | string
  variance_pct: number | string
}

interface MarginRow {
  product_name: string
  latest_cost_per_packet: number | string | null
  selling_price_excl_gst: number | string
  profit_margin_pct: number | string | null
  total_runs: number
  total_packets_produced: number | string
}

interface ProductionPerformance {
  run_number: string
  product: string
  expected: number
  actual: number
  damaged_pouches: number
  cost_per_packet: number
}

interface DashboardData {
  kpis: KPIs
  sales_trend: SalesTrend[]
  finished_goods_levels: StockLevel[]
  variance_alerts: VarianceAlert[]
  costing_margins: MarginRow[]
  production_performance: ProductionPerformance[]
}

const StatCard: React.FC<{
  title: string
  value: string | number
  sub?: string
  accent?: 'green' | 'red' | 'yellow' | 'blue'
}> = ({ title, value, sub, accent = 'blue' }) => {
  const colors: Record<string, string> = {
    green: 'border-l-emerald-500',
    red: 'border-l-red-500',
    yellow: 'border-l-amber-500',
    blue: 'border-l-blue-500',
  }

  return (
    <Card className={`border-l-4 ${colors[accent]}`}>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{title}</p>
        <p className="text-2xl font-bold mt-1">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </CardContent>
    </Card>
  )
}

export default function OwnerDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiClient.get('/dashboard/owner')
      .then((response: { data: DashboardData }) => setData(response.data))
      .catch((e: Error) => setError(e.message || 'Failed to load dashboard'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" />
      </div>
    )
  }

  if (error || !data) {
    return <div className="p-6 text-red-600">Error: {error || 'No data'}</div>
  }

  const {
    kpis,
    sales_trend = [],
    finished_goods_levels = [],
    variance_alerts = [],
    costing_margins = [],
    production_performance = [],
  } = data

  const trendData = sales_trend.map(item => ({
    date: item.date,
    sales: Number(item.sales),
  }))

  const stockData = finished_goods_levels.map(item => ({
    product: item.name,
    available: Number(item.available),
  }))

  const totalRuns = production_performance.length

  const totalGoodPackets = production_performance.reduce(
    (sum, item) => sum + Number(item.actual || 0),
    0
  )
  const totalDamagedPouches = production_performance.reduce(
    (sum, item) => sum + Number(item.damaged_pouches || 0),
  0
 )

  return (
    <div className="space-y-6 p-2">

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard
          title="Orders Today"
          value={kpis.orders_today}
        />

        <StatCard
          title="Pending Approvals"
          value={kpis.pending_approvals}
          accent={kpis.pending_approvals > 0 ? 'yellow' : 'green'}
        />

        <StatCard
          title="Sales This Month"
          value={formatINR(Number(kpis.total_sales))}
          accent="green"
        />

        <StatCard
          title="Outstanding Dues"
          value={formatINR(Number(kpis.outstanding_dues))}
          accent={Number(kpis.outstanding_dues) > 10000 ? 'red' : 'yellow'}
        />

        <StatCard
          title="FG Stock Available"
          value={`${Number(kpis.finished_goods_available).toLocaleString('en-IN')} packets`}
          accent="blue"
          sub="Across all finished products"
        />
      </div>

      {/* Production Summary */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard
          title="Production Runs"
          value={totalRuns}
          accent="blue"
        />

        <StatCard
          title="Good Packets Produced"
          value={totalGoodPackets.toLocaleString('en-IN')}
          accent="green"
        />

        <StatCard
          title="Damaged Pouches"
          value={totalDamagedPouches.toLocaleString('en-IN')}
          sub="Total damaged pouches in recent production runs"
          accent="yellow"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Sales Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Sales Trend (₹)</CardTitle>
          </CardHeader>

          <CardContent>
            {trendData.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No sales data yet
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={value => `₹${(value / 1000).toFixed(0)}k`}
                  />
                  <Tooltip formatter={(value: number) => formatINR(value)} />
                  <Line
                    type="monotone"
                    dataKey="sales"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot={false}
                    name="Sales"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Finished Goods Stock */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Finished Goods Stock (Packets)
            </CardTitle>
          </CardHeader>

          <CardContent>
            {stockData.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No stock data
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={stockData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="product" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar
                    dataKey="available"
                    fill="#10b981"
                    name="Available"
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Variance Alerts and Margins */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Variance Alerts */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              ⚠ Variance Alerts
            </CardTitle>
          </CardHeader>

          <CardContent>
            {variance_alerts.length === 0 ? (
              <p className="text-sm text-green-600 py-4 text-center">
                ✓ No variance alerts
              </p>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {variance_alerts.map((item, index) => (
                  <div
                    key={`${item.run_number}-${item.metric}-${index}`}
                    className="flex items-start justify-between p-2 rounded bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 text-sm"
                  >
                    <div>
                      <p className="font-medium">{item.product}</p>
                      <p className="text-xs text-muted-foreground">
                        Batch: {item.run_number} | {item.metric}
                      </p>
                      <p className="text-xs">
                        Planned: {item.planned} → Actual: {item.actual}
                      </p>
                      <p className="text-xs">
                        Variance: {item.variance_pct}%
                      </p>
                    </div>

                    <Badge variant="warning">
                      {item.metric}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Product Margins */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Product Margins</CardTitle>
          </CardHeader>

          <CardContent>
            {costing_margins.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No costing data
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left pb-2">Product</th>
                      <th className="text-right pb-2">Cost/Pkt</th>
                      <th className="text-right pb-2">Selling Price</th>
                      <th className="text-right pb-2">Margin%</th>
                    </tr>
                  </thead>

                  <tbody>
                    {costing_margins.map((item, index) => (
                      <tr key={item.product_name + index} className="border-b last:border-0">
                        <td className="py-1 pr-2">{item.product_name}</td>

                        <td className="text-right py-1">
                          {item.latest_cost_per_packet == null
                            ? '—'
                            : formatINR(Number(item.latest_cost_per_packet))}
                        </td>

                        <td className="text-right py-1">
                          {formatINR(Number(item.selling_price_excl_gst))}
                        </td>

                        <td className={`text-right py-1 font-semibold ${item.profit_margin_pct == null
                          ? 'text-muted-foreground'
                          : Number(item.profit_margin_pct) >= 20
                            ? 'text-green-600'
                            : Number(item.profit_margin_pct) >= 10
                              ? 'text-amber-600'
                              : 'text-red-600'
                          }`}>
                          {item.profit_margin_pct == null
                            ? '—'
                            : `${Number(item.profit_margin_pct).toFixed(1)}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}