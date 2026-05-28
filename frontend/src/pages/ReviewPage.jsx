import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import Navbar from '../components/Navbar'
import StatusBadge from '../components/StatusBadge'
import ScopeTag from '../components/ScopeTag'
import { useAuth } from '../App'
import { getRecords, approveRecord, rejectRecord, bulkApprove } from '../api'

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtCO2e(val) {
  if (val == null || isNaN(val)) return '—'
  return Number(val).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function fmtDate(str) {
  if (!str) return '—'
  try {
    return new Date(str).toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return str
  }
}

const SOURCE_LABELS = {
  SAP_FUEL: 'SAP Fuel',
  SAP_PROCUREMENT: 'SAP Procurement',
  UTILITY_ELECTRICITY: 'Utility',
  TRAVEL: 'Travel',
}

const CAN_ACT_STATUSES = new Set(['PENDING', 'FLAGGED'])

// ── FlagsCell ─────────────────────────────────────────────────────────────────

function FlagsCell({ flags }) {
  const [show, setShow] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!show) return
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setShow(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [show])

  if (!flags || flags.length === 0) {
    return <span className="text-gray-300 text-xs">—</span>
  }

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        onClick={() => setShow((s) => !s)}
        title="View flags"
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-orange-50 border border-orange-200 text-orange-700 text-xs hover:bg-orange-100 transition-colors"
      >
        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        {flags.length}
      </button>
      {show && (
        <div className="absolute z-10 left-0 top-full mt-1 w-64 bg-white border border-orange-200 rounded-lg shadow-lg p-3">
          <p className="text-xs font-semibold text-orange-800 mb-2">Data Quality Flags</p>
          <ul className="space-y-1">
            {flags.map((f, i) => (
              <li key={i} className="text-xs text-orange-700 flex gap-1.5">
                <span className="shrink-0 mt-0.5">•</span>
                <span>{typeof f === 'string' ? f : f.message || f.reason || JSON.stringify(f)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── ActionModal ───────────────────────────────────────────────────────────────

function ActionModal({ record, action, onConfirm, onCancel, loading }) {
  const [note, setNote] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  function handleSubmit(e) {
    e.preventDefault()
    onConfirm(note)
  }

  const isApprove = action === 'approve'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && onCancel()}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div
          className={`px-5 py-4 border-b ${
            isApprove ? 'bg-green-50 border-green-100' : 'bg-red-50 border-red-100'
          }`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`p-2 rounded-full ${
                isApprove ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}
            >
              {isApprove ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-900">
                {isApprove ? 'Approve record' : 'Reject record'}
              </h3>
              {record && (
                <p className="text-xs text-gray-500">
                  {record.category || '—'} &bull; {fmtCO2e(record.co2e_kg)} kg CO₂e
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Review note{' '}
            <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <textarea
            ref={textareaRef}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder={
              isApprove
                ? 'e.g. Verified against purchase order #12345'
                : 'e.g. Duplicate entry — already captured in Q3 report'
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
            disabled={loading}
          />

          <div className="flex gap-3 mt-4">
            <button
              type="submit"
              disabled={loading}
              className={`flex-1 py-2 px-4 text-sm font-semibold text-white rounded-lg transition-colors disabled:opacity-50 ${
                isApprove
                  ? 'bg-green-700 hover:bg-green-800'
                  : 'bg-red-600 hover:bg-red-700'
              }`}
            >
              {loading
                ? 'Processing…'
                : isApprove
                ? 'Confirm Approve'
                : 'Confirm Reject'}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={loading}
              className="flex-1 py-2 px-4 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── BulkApproveBar ─────────────────────────────────────────────────────────────

function BulkApproveBar({ selected, total, onSelectAll, onClearAll, onBulkApprove, loading, canAct }) {
  return (
    <div className="flex items-center gap-4">
      <label className="flex items-center gap-2 cursor-pointer select-none">
        <input
          type="checkbox"
          className="w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
          checked={selected.size > 0 && selected.size === total}
          ref={(el) => {
            if (el) el.indeterminate = selected.size > 0 && selected.size < total
          }}
          onChange={(e) => (e.target.checked ? onSelectAll() : onClearAll())}
        />
        <span className="text-sm text-gray-600">
          {selected.size > 0 ? `${selected.size} selected` : 'Select all visible'}
        </span>
      </label>

      {selected.size > 0 && canAct && (
        <button
          onClick={onBulkApprove}
          disabled={loading}
          className="px-3 py-1.5 text-xs font-semibold bg-green-700 hover:bg-green-800 text-white rounded-lg transition-colors disabled:opacity-50"
        >
          {loading ? 'Approving…' : `Bulk Approve ${selected.size} record${selected.size !== 1 ? 's' : ''}`}
        </button>
      )}
    </div>
  )
}

// ── Pagination ────────────────────────────────────────────────────────────────

function Pagination({ page, totalPages, onPrev, onNext }) {
  return (
    <div className="flex items-center gap-3">
      <button
        onClick={onPrev}
        disabled={page <= 1}
        className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        &larr; Previous
      </button>
      <span className="text-xs text-gray-500">
        Page {page} of {totalPages || 1}
      </span>
      <button
        onClick={onNext}
        disabled={page >= totalPages}
        className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Next &rarr;
      </button>
    </div>
  )
}

// ── FilterBar ─────────────────────────────────────────────────────────────────

function FilterBar({ filters, onApply }) {
  const [local, setLocal] = useState(filters)

  useEffect(() => {
    setLocal(filters)
  }, [filters])

  function set(key, val) {
    setLocal((prev) => ({ ...prev, [key]: val }))
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4">
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
          <select
            value={local.status}
            onChange={(e) => set('status', e.target.value)}
            className="text-sm border border-gray-300 rounded-md px-2 py-1.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            <option value="">All</option>
            <option value="PENDING">Pending</option>
            <option value="FLAGGED">Flagged</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Scope</label>
          <select
            value={local.scope}
            onChange={(e) => set('scope', e.target.value)}
            className="text-sm border border-gray-300 rounded-md px-2 py-1.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            <option value="">All</option>
            <option value="1">Scope 1</option>
            <option value="2">Scope 2</option>
            <option value="3">Scope 3</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Source Type</label>
          <select
            value={local.source_type}
            onChange={(e) => set('source_type', e.target.value)}
            className="text-sm border border-gray-300 rounded-md px-2 py-1.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            <option value="">All</option>
            <option value="SAP_FUEL">SAP Fuel</option>
            <option value="SAP_PROCUREMENT">SAP Procurement</option>
            <option value="UTILITY_ELECTRICITY">Utility</option>
            <option value="TRAVEL">Travel</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">From</label>
          <input
            type="date"
            value={local.date_from}
            onChange={(e) => set('date_from', e.target.value)}
            className="text-sm border border-gray-300 rounded-md px-2 py-1.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-green-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">To</label>
          <input
            type="date"
            value={local.date_to}
            onChange={(e) => set('date_to', e.target.value)}
            className="text-sm border border-gray-300 rounded-md px-2 py-1.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-green-500"
          />
        </div>

        <button
          onClick={() => onApply(local)}
          className="px-4 py-1.5 bg-green-800 hover:bg-green-700 text-white text-sm font-medium rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-green-500"
        >
          Apply
        </button>

        <button
          onClick={() => {
            const empty = { status: '', scope: '', source_type: '', date_from: '', date_to: '' }
            setLocal(empty)
            onApply(empty)
          }}
          className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          Clear
        </button>
      </div>
    </div>
  )
}

// ── skeleton row ──────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <tr>
      {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-gray-200 rounded animate-pulse" />
        </td>
      ))}
    </tr>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

const EMPTY_FILTERS = {
  status: '',
  scope: '',
  source_type: '',
  date_from: '',
  date_to: '',
}

export default function ReviewPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()

  // Seed filters from URL params
  const initialFilters = {
    ...EMPTY_FILTERS,
    status: searchParams.get('status') || '',
    source_type: searchParams.get('source_type') || '',
  }

  const [filters, setFilters] = useState(initialFilters)
  const [appliedFilters, setAppliedFilters] = useState(initialFilters)
  const [page, setPage] = useState(1)
  const [records, setRecords] = useState([])
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Selection
  const [selected, setSelected] = useState(new Set())

  // Modal state
  const [modal, setModal] = useState(null) // { record, action: 'approve'|'reject' }
  const [modalLoading, setModalLoading] = useState(false)
  const [modalError, setModalError] = useState('')

  // Bulk approve state
  const [bulkLoading, setBulkLoading] = useState(false)

  const canAct = user?.role === 'ANALYST' || user?.role === 'ADMIN'

  // ── fetch records ─────────────────────────────────────────────────────────

  const fetchRecords = useCallback(
    async (currentFilters, currentPage) => {
      setLoading(true)
      setError('')
      try {
        const params = { page: currentPage }
        if (currentFilters.status) params.status = currentFilters.status
        if (currentFilters.scope) params.scope = currentFilters.scope
        if (currentFilters.source_type) params.source_type = currentFilters.source_type
        if (currentFilters.date_from) params.date_from = currentFilters.date_from
        if (currentFilters.date_to) params.date_to = currentFilters.date_to

        const res = await getRecords(params)
        const data = res.data

        // Support DRF pagination (results key) or flat array
        if (Array.isArray(data)) {
          setRecords(data)
          setTotalPages(1)
          setTotalCount(data.length)
        } else {
          setRecords(data.results || [])
          setTotalCount(data.count || 0)
          setTotalPages(data.count ? Math.ceil(data.count / (data.results?.length || 20)) : 1)
        }
        setSelected(new Set())
      } catch {
        setError('Failed to load records. Please try again.')
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    fetchRecords(appliedFilters, page)
  }, [appliedFilters, page, fetchRecords])

  // ── filter apply ──────────────────────────────────────────────────────────

  function handleApplyFilters(newFilters) {
    setAppliedFilters(newFilters)
    setFilters(newFilters)
    setPage(1)
  }

  // ── selection ─────────────────────────────────────────────────────────────

  function toggleRecord(id) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function selectAll() {
    // Only select actionable records for bulk ops
    const actionable = records.filter((r) => CAN_ACT_STATUSES.has(r.status) && !r.is_locked)
    setSelected(new Set(actionable.map((r) => r.id)))
  }

  function clearAll() {
    setSelected(new Set())
  }

  // ── modal actions ─────────────────────────────────────────────────────────

  function openModal(record, action) {
    setModal({ record, action })
    setModalError('')
  }

  function closeModal() {
    setModal(null)
    setModalError('')
  }

  async function handleModalConfirm(note) {
    if (!modal) return
    setModalLoading(true)
    setModalError('')
    try {
      if (modal.action === 'approve') {
        await approveRecord(modal.record.id, note)
      } else {
        await rejectRecord(modal.record.id, note)
      }
      closeModal()
      fetchRecords(appliedFilters, page)
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        'Action failed. Please try again.'
      setModalError(msg)
    } finally {
      setModalLoading(false)
    }
  }

  // ── bulk approve ──────────────────────────────────────────────────────────

  async function handleBulkApprove() {
    if (selected.size === 0) return
    setBulkLoading(true)
    try {
      await bulkApprove([...selected])
      setSelected(new Set())
      fetchRecords(appliedFilters, page)
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          'Bulk approve failed.'
      )
    } finally {
      setBulkLoading(false)
    }
  }

  // ── render ────────────────────────────────────────────────────────────────

  // Count of actionable visible records for "select all" checkbox total
  const actionableVisible = records.filter(
    (r) => CAN_ACT_STATUSES.has(r.status) && !r.is_locked
  ).length

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      {modal && (
        <ActionModal
          record={modal.record}
          action={modal.action}
          onConfirm={handleModalConfirm}
          onCancel={closeModal}
          loading={modalLoading}
          error={modalError}
        />
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-4">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Emissions Record Review</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Approve or reject ingested emissions records after data quality review.
          </p>
        </div>

        {/* Filter bar */}
        <FilterBar filters={filters} onApply={handleApplyFilters} />

        {error && (
          <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')} className="text-red-500 hover:text-red-700 ml-4">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Action bar */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <BulkApproveBar
            selected={selected}
            total={actionableVisible}
            onSelectAll={selectAll}
            onClearAll={clearAll}
            onBulkApprove={handleBulkApprove}
            loading={bulkLoading}
            canAct={canAct}
          />
          {!loading && (
            <span className="text-xs text-gray-400">
              {totalCount.toLocaleString('en-IN')} record{totalCount !== 1 ? 's' : ''} total
            </span>
          )}
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide bg-gray-50 border-b border-gray-100">
                  <th className="pl-4 pr-2 py-3 w-8">
                    <input
                      type="checkbox"
                      className="w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
                      checked={selected.size > 0 && selected.size === actionableVisible}
                      ref={(el) => {
                        if (el)
                          el.indeterminate =
                            selected.size > 0 && selected.size < actionableVisible
                      }}
                      onChange={(e) => (e.target.checked ? selectAll() : clearAll())}
                    />
                  </th>
                  <th className="px-3 py-3">Date</th>
                  <th className="px-3 py-3">Category</th>
                  <th className="px-3 py-3">Scope</th>
                  <th className="px-3 py-3">Quantity</th>
                  <th className="px-3 py-3 text-right">CO₂e (kg)</th>
                  <th className="px-3 py-3">Source / Plant</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Flags</th>
                  {canAct && <th className="px-3 py-3 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
                ) : records.length === 0 ? (
                  <tr>
                    <td
                      colSpan={canAct ? 10 : 9}
                      className="px-4 py-16 text-center text-sm text-gray-400"
                    >
                      <svg
                        className="mx-auto w-10 h-10 text-gray-200 mb-3"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1}
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                        />
                      </svg>
                      No records match your filters.
                    </td>
                  </tr>
                ) : (
                  records.map((record) => {
                    const isActionable =
                      CAN_ACT_STATUSES.has(record.status) && !record.is_locked
                    const isSelected = selected.has(record.id)

                    return (
                      <tr
                        key={record.id}
                        className={`transition-colors ${
                          isSelected ? 'bg-green-50' : 'hover:bg-gray-50'
                        }`}
                      >
                        {/* Checkbox */}
                        <td className="pl-4 pr-2 py-3">
                          {isActionable && (
                            <input
                              type="checkbox"
                              className="w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
                              checked={isSelected}
                              onChange={() => toggleRecord(record.id)}
                            />
                          )}
                        </td>

                        {/* Date */}
                        <td className="px-3 py-3 whitespace-nowrap text-gray-600">
                          {fmtDate(record.activity_date)}
                        </td>

                        {/* Category */}
                        <td className="px-3 py-3 text-gray-800 max-w-xs">
                          <span
                            className="block truncate"
                            title={record.category}
                          >
                            {record.category || '—'}
                          </span>
                        </td>

                        {/* Scope */}
                        <td className="px-3 py-3">
                          <ScopeTag scope={record.scope} />
                        </td>

                        {/* Quantity */}
                        <td className="px-3 py-3 text-gray-600 whitespace-nowrap">
                          {record.raw_quantity != null
                            ? `${Number(record.raw_quantity).toLocaleString('en-IN', { maximumFractionDigits: 2 })} ${record.raw_unit || ''}`
                            : '—'}
                        </td>

                        {/* CO2e */}
                        <td className="px-3 py-3 text-right font-mono text-gray-800 whitespace-nowrap">
                          {fmtCO2e(record.co2e_kg)}
                        </td>

                        {/* Source / Plant */}
                        <td className="px-3 py-3 text-gray-500 whitespace-nowrap">
                          <span
                            className="block text-xs truncate max-w-[120px]"
                            title={record.ingestion_source_type}
                          >
                            {SOURCE_LABELS[record.ingestion_source_type] || record.ingestion_source_type || '—'}
                          </span>
                          {record.source_plant_code && (
                            <span className="block text-xs text-gray-400">{record.source_plant_code}</span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="px-3 py-3">
                          <StatusBadge status={record.status} />
                        </td>

                        {/* Flags */}
                        <td className="px-3 py-3">
                          <FlagsCell flags={record.flag_reasons} />
                        </td>

                        {/* Actions */}
                        {canAct && (
                          <td className="px-3 py-3">
                            {isActionable ? (
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={() => openModal(record, 'approve')}
                                  className="px-2.5 py-1 text-xs font-medium bg-green-50 text-green-700 border border-green-200 rounded hover:bg-green-100 transition-colors"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => openModal(record, 'reject')}
                                  className="px-2.5 py-1 text-xs font-medium bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 transition-colors"
                                >
                                  Reject
                                </button>
                              </div>
                            ) : (
                              <span className="text-xs text-gray-300 block text-right">
                                {record.is_locked ? 'Locked' : '—'}
                              </span>
                            )}
                          </td>
                        )}
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Pagination */}
        {!loading && records.length > 0 && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">
              Showing page {page} of {totalPages}
            </span>
            <Pagination
              page={page}
              totalPages={totalPages}
              onPrev={() => setPage((p) => Math.max(1, p - 1))}
              onNext={() => setPage((p) => Math.min(totalPages, p + 1))}
            />
          </div>
        )}
      </main>
    </div>
  )
}
