import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import StatusBadge from '../components/StatusBadge'
import { getStats } from '../api'

// ── helpers ─────────────────────────────────────────────────────────────────

function fmt(num, decimals = 1) {
  if (num == null || isNaN(num)) return '—'
  return Number(num).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function fmtInt(num) {
  if (num == null || isNaN(num)) return '—'
  return Number(num).toLocaleString('en-IN')
}

const SOURCE_COLORS = {
  SAP_FUEL: 'bg-blue-100 text-blue-800',
  SAP_PROCUREMENT: 'bg-indigo-100 text-indigo-800',
  UTILITY_ELECTRICITY: 'bg-yellow-100 text-yellow-800',
  TRAVEL: 'bg-green-100 text-green-800',
}

const SOURCE_LABELS = {
  SAP_FUEL: 'SAP Fuel',
  SAP_PROCUREMENT: 'SAP Procurement',
  UTILITY_ELECTRICITY: 'Utility',
  TRAVEL: 'Travel',
}

// ── skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className = '' }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className}`} />
}

// ── stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, unit, sub, to, loading }) {
  const inner = (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      {loading ? (
        <>
          <Skeleton className="h-8 w-32 mb-1" />
          <Skeleton className="h-3 w-16" />
        </>
      ) : (
        <>
          <p className="text-2xl font-bold text-gray-900">
            {value}
            {unit && <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>}
          </p>
          {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
        </>
      )}
    </div>
  )

  return to ? (
    <Link to={to} className="block">
      {inner}
    </Link>
  ) : (
    inner
  )
}

// ── bar chart row ─────────────────────────────────────────────────────────────

function BarRow({ label, value, max, color, badge }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="w-36 shrink-0 text-xs text-gray-600 truncate" title={label}>
        {label}
      </div>
      <div className="flex-1 bg-gray-100 rounded-full h-4 relative overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="w-16 text-right shrink-0">
        {badge ? (
          badge
        ) : (
          <span className="text-xs font-semibold text-gray-700">{fmtInt(value)}</span>
        )}
      </div>
    </div>
  )
}

// ── ingestion source label ────────────────────────────────────────────────────

function SourceLabel({ sourceType }) {
  const cls = SOURCE_COLORS[sourceType] || 'bg-gray-100 text-gray-700'
  const label = SOURCE_LABELS[sourceType] || sourceType
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    getStats()
      .then((res) => setStats(res.data))
      .catch(() => setError('Failed to load dashboard data. Is the backend running?'))
      .finally(() => setLoading(false))
  }, [])

  // Derived values ──────────────────────────────────────────────────────────

  const scope1 = stats?.total_co2e_by_scope?.['1'] ?? stats?.total_co2e_by_scope?.scope_1 ?? null
  const scope2 = stats?.total_co2e_by_scope?.['2'] ?? stats?.total_co2e_by_scope?.scope_2 ?? null
  const scope3 = stats?.total_co2e_by_scope?.['3'] ?? stats?.total_co2e_by_scope?.scope_3 ?? null

  const recordsByStatus = stats?.records_by_status || {}
  const pendingCount = recordsByStatus.PENDING ?? 0

  const co2eByCategory = stats?.co2e_by_category
    ? Object.entries(stats.co2e_by_category)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
    : []

  const categoryMax = co2eByCategory.length > 0 ? co2eByCategory[0][1] : 1

  const statusOrder = ['PENDING', 'FLAGGED', 'APPROVED', 'REJECTED']
  const statusColors = {
    PENDING: 'bg-yellow-400',
    FLAGGED: 'bg-orange-400',
    APPROVED: 'bg-green-500',
    REJECTED: 'bg-red-400',
  }
  const statusMax = Math.max(1, ...Object.values(recordsByStatus).map(Number))

  const recentIngestions = stats?.recent_ingestions || []

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Carbon Emissions Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Overview of your organisation's GHG inventory
          </p>
        </div>

        {error && (
          <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Row 1 — Scope stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total CO₂e — Scope 1"
            value={loading ? null : fmt(scope1)}
            unit="tCO₂e"
            sub="Direct emissions"
            loading={loading}
          />
          <StatCard
            label="Total CO₂e — Scope 2"
            value={loading ? null : fmt(scope2)}
            unit="tCO₂e"
            sub="Purchased electricity"
            loading={loading}
          />
          <StatCard
            label="Total CO₂e — Scope 3"
            value={loading ? null : fmt(scope3)}
            unit="tCO₂e"
            sub="Value chain"
            loading={loading}
          />
          <StatCard
            label="Pending Review"
            value={loading ? null : fmtInt(pendingCount)}
            unit="records"
            sub="Awaiting analyst action"
            to="/review?status=PENDING"
            loading={loading}
          />
        </div>

        {/* Row 2 — Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Records by Status */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-800 mb-4">Records by Status</h2>
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-3 w-28" />
                    <Skeleton className="h-4 flex-1" />
                    <Skeleton className="h-3 w-10" />
                  </div>
                ))}
              </div>
            ) : Object.keys(recordsByStatus).length === 0 ? (
              <p className="text-sm text-gray-400 py-4 text-center">No data yet</p>
            ) : (
              <div className="space-y-1">
                {statusOrder
                  .filter((s) => recordsByStatus[s] != null)
                  .map((s) => (
                    <BarRow
                      key={s}
                      label={s.charAt(0) + s.slice(1).toLowerCase()}
                      value={Number(recordsByStatus[s])}
                      max={statusMax}
                      color={statusColors[s] || 'bg-gray-400'}
                      badge={<StatusBadge status={s} />}
                    />
                  ))}
              </div>
            )}
          </div>

          {/* CO2e by Category */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-800 mb-4">
              CO₂e by Category{' '}
              <span className="font-normal text-gray-400 text-xs">(top 5)</span>
            </h2>
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-3 w-28" />
                    <Skeleton className="h-4 flex-1" />
                    <Skeleton className="h-3 w-12" />
                  </div>
                ))}
              </div>
            ) : co2eByCategory.length === 0 ? (
              <p className="text-sm text-gray-400 py-4 text-center">No data yet</p>
            ) : (
              <div className="space-y-1">
                {co2eByCategory.map(([cat, val]) => (
                  <BarRow
                    key={cat}
                    label={cat}
                    value={val}
                    max={categoryMax}
                    color="bg-green-500"
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Row 3 — Recent Ingestions */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-800">Recent Ingestions</h2>
            <Link
              to="/upload"
              className="text-xs text-green-700 hover:text-green-900 font-medium transition-colors"
            >
              Upload new &rarr;
            </Link>
          </div>

          {loading ? (
            <div className="p-5 space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : error ? null : recentIngestions.length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-gray-400">
              No ingestions yet. Upload a file to get started.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    <th className="px-5 py-3 bg-gray-50 rounded-tl">Source Type</th>
                    <th className="px-4 py-3 bg-gray-50">File</th>
                    <th className="px-4 py-3 bg-gray-50">Uploaded By</th>
                    <th className="px-4 py-3 bg-gray-50">Date</th>
                    <th className="px-4 py-3 bg-gray-50">Status</th>
                    <th className="px-4 py-3 bg-gray-50 rounded-tr text-right">Records</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {recentIngestions.map((ing) => (
                    <tr key={ing.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-5 py-3">
                        <SourceLabel sourceType={ing.source_type} />
                      </td>
                      <td className="px-4 py-3 text-gray-700 max-w-xs truncate" title={ing.file_name}>
                        {ing.file_name || '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {ing.uploaded_by?.username || ing.uploaded_by || '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                        {ing.created_at
                          ? new Date(ing.created_at).toLocaleDateString('en-IN', {
                              day: '2-digit',
                              month: 'short',
                              year: 'numeric',
                            })
                          : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={ing.status} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          to={`/review?source_type=${ing.source_type}`}
                          className="text-green-700 hover:text-green-900 font-medium"
                          title="View records from this ingestion"
                        >
                          {fmtInt(ing.record_count ?? ing.records_count ?? 0)}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
