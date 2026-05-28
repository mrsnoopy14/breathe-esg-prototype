import React from 'react'

const CONFIG = {
  PENDING: {
    label: 'Pending',
    className: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  },
  FLAGGED: {
    label: 'Flagged',
    className: 'bg-orange-100 text-orange-800 border border-orange-200',
  },
  APPROVED: {
    label: 'Approved',
    className: 'bg-green-100 text-green-800 border border-green-200',
  },
  REJECTED: {
    label: 'Rejected',
    className: 'bg-red-100 text-red-800 border border-red-200',
  },
}

export default function StatusBadge({ status }) {
  const cfg = CONFIG[status] || {
    label: status || 'Unknown',
    className: 'bg-gray-100 text-gray-600 border border-gray-200',
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.className}`}
    >
      {cfg.label}
    </span>
  )
}
