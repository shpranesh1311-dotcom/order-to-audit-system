import React, { useState } from 'react'
import { api as apiClient } from '../../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'

const REPORT_TYPES = [
  { value: 'sales_register', label: 'Sales Register' },
  { value: 'purchase_register', label: 'Purchase Register' },
  { value: 'gst_summary', label: 'GST Summary' },
  { value: 'gst_sales_detail', label: 'GST Sales Detail' },
  { value: 'gst_purchase_detail', label: 'GST Purchase Detail' },
  { value: 'inventory_summary', label: 'Stock Summary' },
  { value: 'stock_ledger', label: 'Stock Ledger' },
  { value: 'production_report', label: 'Production Report' },
  { value: 'costing_report', label: 'Costing Report' },
  { value: 'payment_collection', label: 'Payment & Collection' },
  { value: 'outstanding_balances', label: 'Outstanding Balances' },
  { value: 'variance_analysis', label: 'Variance Analysis' },
  { value: 'profit_loss_summary', label: 'Profit & Loss Summary' },
]

interface ReportData {
  columns: string[]
  rows: Record<string, string | number | null>[]
  total_rows: number
  report_type: string
  period?: string
  note?: string
}

export default function ReportsPage() {
  const [reportType, setReportType] = useState('sales_register')

  const [startDate, setStartDate] = useState(() => {
    const d = new Date()
    d.setDate(1)
    return d.toISOString().split('T')[0]
  })

  const [endDate, setEndDate] = useState(
    () => new Date().toISOString().split('T')[0]
  )

  const [data, setData] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [materialId, setMaterialId] = useState('')

  const buildParams = (extra: Record<string, string> = {}) => {
    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      ...extra,
    })

    if (reportType === 'stock_ledger' && materialId.trim()) {
      params.set('material_id', materialId.trim())
    }

    return params.toString()
  }

  const validateDates = () => {
    if (!startDate || !endDate) {
      setError('Please select both From and To dates.')
      return false
    }

    if (startDate > endDate) {
      setError('The From date cannot be later than the To date.')
      return false
    }

    return true
  }

  // Generate selected report
  const fetchReport = async () => {
    if (!validateDates()) return

    setLoading(true)
    setError(null)
    setData(null)

    try {
      const response = await apiClient.get<ReportData>(
        `/reports/${reportType}?${buildParams()}`
      )

      if (
        !response.data ||
        !Array.isArray(response.data.columns) ||
        !Array.isArray(response.data.rows)
      ) {
        throw new Error('The server returned an unexpected report format.')
      }

      setData(response.data)
    } catch (e: unknown) {
      console.error('Report generation failed:', e)

      const msg =
        e instanceof Error ? e.message : 'Failed to load report.'

      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  // Download report as CSV, Excel or PDF
  const downloadFile = async (format: 'csv' | 'excel' | 'pdf') => {
    if (!validateDates()) return

    setExporting(true)
    setError(null)

    try {
      const response = await apiClient.get(
        `/reports/${reportType}?${buildParams({ export: format })}`,
        {
          responseType: 'blob',
        }
      )

      const ext = format === 'excel' ? 'xlsx' : format

      const mimeMap: Record<string, string> = {
        csv: 'text/csv',
        excel:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        pdf: 'application/pdf',
      }

      const blob = new Blob([response.data], {
        type: mimeMap[format],
      })

      const url = window.URL.createObjectURL(blob)
      const anchor = document.createElement('a')

      anchor.href = url
      anchor.download = `${reportType}_${startDate}_${endDate}.${ext}`

      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)

      window.URL.revokeObjectURL(url)
    } catch (e: unknown) {
      console.error('Report export failed:', e)
      setError('Export failed. Please try again.')
    } finally {
      setExporting(false)
    }
  }

  const formatCell = (value: string | number | null): string => {
    if (value === null || value === undefined) {
      return '—'
    }

    return String(value)
  }

  const colLabel = (col: string) =>
    col.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  return (
    <div className="space-y-4 p-2">

      {/* Report Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Reports & Exports</CardTitle>
        </CardHeader>

        <CardContent>
          <div className="flex flex-wrap gap-3 items-end">

            {/* Report Type */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium">
                Report Type
              </label>

              <select
                className="border rounded px-3 py-2 text-sm bg-background"
                value={reportType}
                onChange={(e) => {
                  setReportType(e.target.value)
                  setData(null)
                  setError(null)
                }}
              >
                {REPORT_TYPES.map((report) => (
                  <option key={report.value} value={report.value}>
                    {report.label}
                  </option>
                ))}
              </select>
            </div>

            {/* From Date */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium">
                From
              </label>

              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-36"
              />
            </div>

            {/* To Date */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium">
                To
              </label>

              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-36"
              />
            </div>

            {/* Material ID for Stock Ledger */}
            {reportType === 'stock_ledger' && (
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium">
                  Material ID
                </label>

                <Input
                  placeholder="e.g. 1"
                  value={materialId}
                  onChange={(e) => setMaterialId(e.target.value)}
                  className="w-24"
                />
              </div>
            )}

            {/* Run Report */}
            <Button
              onClick={fetchReport}
              disabled={loading || exporting}
            >
              {loading ? 'Loading...' : 'Run Report'}
            </Button>

            {/* Export Buttons */}
            {data && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={exporting}
                  onClick={() => downloadFile('csv')}
                >
                  {exporting ? 'Exporting...' : '⬇ CSV'}
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  disabled={exporting}
                  onClick={() => downloadFile('excel')}
                >
                  ⬇ Excel
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  disabled={exporting}
                  onClick={() => downloadFile('pdf')}
                >
                  ⬇ PDF
                </Button>
              </div>
            )}

          </div>
        </CardContent>
      </Card>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Report Results */}
      {data && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">
                {REPORT_TYPES.find(
                  (report) => report.value === reportType
                )?.label}

                {data.period && (
                  <span className="ml-2 text-sm font-normal text-muted-foreground">
                    ({data.period})
                  </span>
                )}
              </CardTitle>

              <span className="text-sm text-muted-foreground">
                {data.total_rows ?? data.rows.length} rows
              </span>
            </div>

            {data.note && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-1">
                {data.note}
              </p>
            )}
          </CardHeader>

          <CardContent>
            {data.rows.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">
                No records for the selected period.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">

                  <thead>
                    <tr className="bg-muted">
                      {data.columns.map((col) => (
                        <th
                          key={col}
                          className="text-left p-2 font-semibold border-b whitespace-nowrap"
                        >
                          {colLabel(col)}
                        </th>
                      ))}
                    </tr>
                  </thead>

                  <tbody>
                    {data.rows.map((row, index) => (
                      <tr
                        key={index}
                        className="border-b hover:bg-muted/50"
                      >
                        {data.columns.map((col) => (
                          <td
                            key={col}
                            className="p-2 whitespace-nowrap"
                          >
                            {formatCell(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>

                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Disclaimer */}
      <p className="text-xs text-muted-foreground px-1">
        ⚠ Disclaimer: This system assists with internal records. It does not file GST returns or replace a CA's review.
      </p>

    </div>
  )
}