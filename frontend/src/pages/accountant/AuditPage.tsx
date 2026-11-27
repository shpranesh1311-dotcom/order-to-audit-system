import React, { useEffect, useState, useCallback } from 'react'
import { api as apiClient } from '../../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Input } from '../../components/ui/input'
import { Button } from '../../components/ui/button'
import { Badge } from '../../components/ui/badge'

interface AuditEntry {
  id: number
  user_id: number
  username: string
  role: string
  action: string
  entity_type: string
  entity_id: number | string | null
  previous_values: Record<string, unknown> | null
  updated_values: Record<string, unknown> | null
  remarks: string | null
  created_at: string
}

const ACTION_COLORS: Record<string, 'success' | 'warning' | 'danger' | 'default'> = {
  CREATE: 'success',
  UPDATE: 'warning',
  DELETE: 'danger',
  LOGIN: 'default',
  LOGOUT: 'default',
  APPROVE: 'success',
  REJECT: 'danger',
  DISPATCH: 'default',
  PAYMENT_RECORD: 'success',
  INVOICE_GENERATE: 'success',
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [filters, setFilters] = useState({
    entity_type: '',
    action: '',
    username: '',
  })

  const [expanded, setExpanded] = useState<number | null>(null)

  const pageSize = 25

  const fetchAudit = useCallback(async (pg = 1) => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        page: String(pg),
        page_size: String(pageSize),
      })

      if (filters.entity_type) {
        params.set('entity_type', filters.entity_type)
      }

      if (filters.action) {
        params.set('action', filters.action)
      }

      if (filters.username) {
        params.set('username', filters.username)
      }

      const response = await apiClient.get<AuditEntry[]>(
        `/audit?${params.toString()}`
      )

      const rows = Array.isArray(response.data) ? response.data : []

      setEntries(rows)
      setTotal(rows.length)
      setExpanded(null)
    } catch (err) {
      console.error('Failed to fetch audit records:', err)
      setEntries([])
      setTotal(0)
      setError('Failed to load audit log. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    fetchAudit(page)
  }, [page, fetchAudit])

  const formatTs = (ts: string) => {
    if (!ts) return '—'

    const date = new Date(ts)

    if (Number.isNaN(date.getTime())) return ts

    return date.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour12: false,
    })
  }

  const renderJSON = (obj: Record<string, unknown> | null) => {
    if (!obj) {
      return <span className="text-muted-foreground">—</span>
    }

    return (
      <pre className="text-xs bg-muted rounded p-2 overflow-x-auto max-h-48 whitespace-pre-wrap">
        {JSON.stringify(obj, null, 2)}
      </pre>
    )
  }

  const handleSearch = () => {
    setPage(1)
    fetchAudit(1)
  }

  const handleClear = () => {
    setFilters({
      entity_type: '',
      action: '',
      username: '',
    })
    setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="space-y-4 p-2">
      <Card>
        <CardHeader>
          <CardTitle>Audit Trail</CardTitle>
        </CardHeader>

        <CardContent>
          {/* Filters */}
          <div className="flex flex-wrap gap-3 items-end mb-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium">
                Entity Type
              </label>

              <Input
                placeholder="e.g. order, invoice"
                value={filters.entity_type}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    entity_type: e.target.value,
                  }))
                }
                className="w-36"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium">
                Action
              </label>

              <select
                className="border rounded px-3 py-2 text-sm bg-background w-40"
                value={filters.action}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    action: e.target.value,
                  }))
                }
              >
                <option value="">All</option>

                {[
                  'CREATE',
                  'UPDATE',
                  'DELETE',
                  'APPROVE',
                  'REJECT',
                  'LOGIN',
                  'LOGOUT',
                  'DISPATCH',
                  'PAYMENT_RECORD',
                  'INVOICE_GENERATE',
                ].map((action) => (
                  <option key={action} value={action}>
                    {action}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium">
                Username
              </label>

              <Input
                placeholder="username"
                value={filters.username}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    username: e.target.value,
                  }))
                }
                className="w-36"
              />
            </div>

            <Button onClick={handleSearch} disabled={loading}>
              {loading ? 'Loading...' : 'Search'}
            </Button>

            <Button
              variant="outline"
              onClick={handleClear}
              disabled={loading}
            >
              Clear
            </Button>
          </div>

          {/* Error */}
          {error && (
            <p className="text-red-600 text-sm mb-2">
              {error}
            </p>
          )}

          {/* Record count */}
          <div className="text-sm text-muted-foreground mb-2">
            {total} records
          </div>

          {/* Audit table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-muted">
                  <th className="text-left p-2 border-b">Timestamp</th>
                  <th className="text-left p-2 border-b">User</th>
                  <th className="text-left p-2 border-b">Role</th>
                  <th className="text-left p-2 border-b">Action</th>
                  <th className="text-left p-2 border-b">Entity</th>
                  <th className="text-left p-2 border-b">ID</th>
                  <th className="text-left p-2 border-b">Remarks</th>
                  <th className="p-2 border-b">Details</th>
                </tr>
              </thead>

              <tbody>
                {entries.length === 0 && !loading && (
                  <tr>
                    <td
                      colSpan={8}
                      className="text-center py-8 text-muted-foreground"
                    >
                      No audit entries found.
                    </td>
                  </tr>
                )}

                {entries.map((entry) => (
                  <React.Fragment key={entry.id}>
                    <tr className="border-b hover:bg-muted/50">
                      <td className="p-2 whitespace-nowrap font-mono text-xs">
                        {formatTs(entry.created_at)}
                      </td>

                      <td className="p-2 whitespace-nowrap">
                        {entry.username}
                      </td>

                      <td className="p-2 whitespace-nowrap text-xs text-muted-foreground">
                        {entry.role}
                      </td>

                      <td className="p-2">
                        <Badge
                          variant={
                            ACTION_COLORS[entry.action] ?? 'default'
                          }
                        >
                          {entry.action}
                        </Badge>
                      </td>

                      <td className="p-2 whitespace-nowrap">
                        {entry.entity_type}
                      </td>

                      <td className="p-2 text-muted-foreground">
                        {entry.entity_id ?? '—'}
                      </td>

                      <td className="p-2 text-xs text-muted-foreground max-w-[220px] truncate">
                        {entry.remarks ?? '—'}
                      </td>

                      <td className="p-2 text-center">
                        {(entry.previous_values ||
                          entry.updated_values) && (
                            <button
                              className="text-xs underline text-blue-600"
                              onClick={() =>
                                setExpanded(
                                  expanded === entry.id ? null : entry.id
                                )
                              }
                            >
                              {expanded === entry.id ? 'Hide' : 'Diff'}
                            </button>
                          )}
                      </td>
                    </tr>

                    {/* Before and after details */}
                    {expanded === entry.id && (
                      <tr className="bg-muted/30">
                        <td colSpan={8} className="p-3">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <p className="text-xs font-semibold mb-1 text-red-600">
                                Before
                              </p>

                              {renderJSON(entry.previous_values)}
                            </div>

                            <div>
                              <p className="text-xs font-semibold mb-1 text-green-600">
                                After
                              </p>

                              {renderJSON(entry.updated_values)}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center gap-2 mt-4 justify-center">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>

              <span className="text-sm">
                Page {page} of {totalPages}
              </span>

              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}