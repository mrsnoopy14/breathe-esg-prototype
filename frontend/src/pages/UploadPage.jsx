import React, { useState, useRef, useCallback } from 'react'
import Navbar from '../components/Navbar'
import { uploadFile } from '../api'

// ── Upload card config ────────────────────────────────────────────────────────

const UPLOAD_SOURCES = [
  {
    sourceType: 'SAP_FUEL',
    title: 'SAP Fuel',
    subtitle: 'MB51 Material Document Export',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18a3.75 3.75 0 00.495-7.468 5.99 5.99 0 00-1.925 3.547 5.975 5.975 0 01-2.133-1A3.75 3.75 0 0012 18z" />
      </svg>
    ),
    color: 'blue',
    description:
      'Upload the MB51 material document list export from SAP. Tab-separated or comma-separated CSV with columns: BUDAT, WERKS, MATNR, MAKTX, BWART, MENGE, MEINS, KOSTL.',
    columns: ['BUDAT', 'WERKS', 'MATNR', 'MAKTX', 'BWART', 'MENGE', 'MEINS', 'KOSTL'],
  },
  {
    sourceType: 'SAP_PROCUREMENT',
    title: 'SAP Procurement',
    subtitle: 'ME2N Purchase Orders Export',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 00-3 3h15.75m-12.75-3h11.218c1.121-2.3 2.1-4.684 2.924-7.138a60.114 60.114 0 00-16.536-1.84M7.5 14.25L5.106 5.272M6 20.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm12.75 0a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
      </svg>
    ),
    color: 'indigo',
    description:
      'Upload the ME2N purchase orders by material export. Columns: BEDAT, EBELN, MATNR, TXZ01, MENGE, MEINS, NETPR, WAERS, NAME1, WERKS.',
    columns: ['BEDAT', 'EBELN', 'MATNR', 'TXZ01', 'MENGE', 'MEINS', 'NETPR', 'WAERS', 'NAME1', 'WERKS'],
  },
  {
    sourceType: 'UTILITY_ELECTRICITY',
    title: 'Utility Electricity',
    subtitle: 'Green Button Data CSV',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
      </svg>
    ),
    color: 'yellow',
    description:
      'Upload a Green Button Data CSV export from your utility portal. Columns: Service Point ID, Meter Number, Start Time, End Time, Duration (Hours), Consumption (kWh).',
    columns: ['Service Point ID', 'Meter Number', 'Start Time', 'End Time', 'Duration (Hours)', 'Consumption (kWh)'],
  },
  {
    sourceType: 'TRAVEL',
    title: 'Corporate Travel',
    subtitle: 'Concur Expense Export',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
      </svg>
    ),
    color: 'green',
    description:
      'Upload a Concur expense export CSV. Columns: Transaction Date, Expense Type, Vendor Name, City From, City To, Amount, Currency, Quantity.',
    columns: ['Transaction Date', 'Expense Type', 'Vendor Name', 'City From', 'City To', 'Amount', 'Currency', 'Quantity'],
  },
]

const COLOR_MAP = {
  blue: {
    header: 'bg-blue-50 border-blue-100',
    icon: 'bg-blue-100 text-blue-700',
    badge: 'bg-blue-50 text-blue-700 border border-blue-200',
    dropzone: 'border-blue-300 bg-blue-50 hover:bg-blue-100',
    btn: 'bg-blue-700 hover:bg-blue-800',
    progress: 'bg-blue-500',
  },
  indigo: {
    header: 'bg-indigo-50 border-indigo-100',
    icon: 'bg-indigo-100 text-indigo-700',
    badge: 'bg-indigo-50 text-indigo-700 border border-indigo-200',
    dropzone: 'border-indigo-300 bg-indigo-50 hover:bg-indigo-100',
    btn: 'bg-indigo-700 hover:bg-indigo-800',
    progress: 'bg-indigo-500',
  },
  yellow: {
    header: 'bg-yellow-50 border-yellow-100',
    icon: 'bg-yellow-100 text-yellow-700',
    badge: 'bg-yellow-50 text-yellow-700 border border-yellow-200',
    dropzone: 'border-yellow-300 bg-yellow-50 hover:bg-yellow-100',
    btn: 'bg-yellow-600 hover:bg-yellow-700',
    progress: 'bg-yellow-500',
  },
  green: {
    header: 'bg-green-50 border-green-100',
    icon: 'bg-green-100 text-green-700',
    badge: 'bg-green-50 text-green-700 border border-green-200',
    dropzone: 'border-green-300 bg-green-50 hover:bg-green-100',
    btn: 'bg-green-700 hover:bg-green-800',
    progress: 'bg-green-500',
  },
}

// ── single upload card ────────────────────────────────────────────────────────

function UploadCard({ sourceType, title, subtitle, icon, color, description, columns }) {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState(null) // { records_created, errors }
  const [error, setError] = useState('')

  const inputRef = useRef(null)
  const colors = COLOR_MAP[color]

  function handleFileSelect(selectedFile) {
    if (!selectedFile) return
    if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
      setError('Please select a CSV file.')
      return
    }
    setFile(selectedFile)
    setResult(null)
    setError('')
    setProgress(0)
  }

  const onDrop = useCallback(
    (e) => {
      e.preventDefault()
      setDragging(false)
      const dropped = e.dataTransfer.files[0]
      handleFileSelect(dropped)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  )

  function onDragOver(e) {
    e.preventDefault()
    setDragging(true)
  }

  function onDragLeave() {
    setDragging(false)
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setProgress(0)
    setError('')
    setResult(null)
    try {
      const res = await uploadFile(sourceType, file, setProgress)
      setResult(res.data)
      setFile(null)
      setProgress(100)
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        (typeof err?.response?.data === 'string' ? err.response.data : null) ||
        'Upload failed. Please check the file format and try again.'
      setError(msg)
    } finally {
      setUploading(false)
    }
  }

  function reset() {
    setFile(null)
    setResult(null)
    setError('')
    setProgress(0)
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
      {/* Card header */}
      <div className={`px-5 py-4 border-b flex items-start gap-3 ${colors.header}`}>
        <div className={`p-2 rounded-lg shrink-0 ${colors.icon}`}>{icon}</div>
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
          <p className="text-xs text-gray-500">{subtitle}</p>
        </div>
      </div>

      {/* Body */}
      <div className="p-5 flex flex-col gap-4 flex-1">
        <p className="text-xs text-gray-600 leading-relaxed">{description}</p>

        {/* Expected columns */}
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1.5">Expected columns:</p>
          <div className="flex flex-wrap gap-1">
            {columns.map((col) => (
              <span
                key={col}
                className={`text-xs px-1.5 py-0.5 rounded font-mono ${colors.badge}`}
              >
                {col}
              </span>
            ))}
          </div>
        </div>

        {/* Dropzone */}
        {!result && (
          <div
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              dragging ? `${colors.dropzone} border-opacity-100` : `border-gray-300 hover:bg-gray-50`
            } ${file ? 'border-opacity-50' : ''}`}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onClick={() => !uploading && inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => handleFileSelect(e.target.files[0])}
              disabled={uploading}
            />
            {file ? (
              <div className="flex items-center justify-center gap-2">
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                <span className="text-sm text-gray-700 font-medium truncate max-w-xs">{file.name}</span>
                {!uploading && (
                  <button
                    onClick={(e) => { e.stopPropagation(); reset() }}
                    className="text-gray-400 hover:text-gray-600 ml-1"
                    title="Remove file"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            ) : (
              <div>
                <svg className="mx-auto w-8 h-8 text-gray-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
                <p className="text-sm text-gray-500">
                  <span className="font-medium text-gray-700">Click to browse</span> or drag &amp; drop
                </p>
                <p className="text-xs text-gray-400 mt-0.5">CSV files only</p>
              </div>
            )}
          </div>
        )}

        {/* Progress bar */}
        {uploading && (
          <div>
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>Uploading…</span>
              <span>{progress}%</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${colors.progress}`}
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="px-3 py-2 rounded-md bg-red-50 border border-red-200 text-red-700 text-xs">
            {error}
          </div>
        )}

        {/* Success result */}
        {result && (
          <div className="px-3 py-3 rounded-lg bg-green-50 border border-green-200">
            <div className="flex items-start gap-2">
              <svg className="w-4 h-4 text-green-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <div>
                <p className="text-sm font-medium text-green-800">Upload complete</p>
                <p className="text-xs text-green-700 mt-0.5">
                  {result.records_created ?? result.created ?? '?'} records ingested
                  {result.errors != null && result.errors > 0
                    ? ` — ${result.errors} row${result.errors !== 1 ? 's' : ''} skipped`
                    : ''}
                </p>
              </div>
            </div>
            <button
              onClick={reset}
              className="mt-2 text-xs text-green-700 hover:text-green-900 underline"
            >
              Upload another file
            </button>
          </div>
        )}

        {/* Upload button */}
        {!result && (
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className={`mt-auto w-full py-2.5 text-sm font-semibold text-white rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 ${colors.btn}`}
          >
            {uploading ? 'Uploading…' : 'Upload File'}
          </button>
        )}
      </div>
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function UploadPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900">Upload Emissions Data</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Select the appropriate source type and upload your CSV export. Records will be
            parsed and queued for review.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-2 gap-5">
          {UPLOAD_SOURCES.map((src) => (
            <UploadCard key={src.sourceType} {...src} />
          ))}
        </div>
      </main>
    </div>
  )
}
