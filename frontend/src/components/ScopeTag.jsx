import React from 'react'

const CONFIG = {
  1: {
    label: 'Scope 1',
    title: 'Direct emissions',
    className: 'bg-blue-100 text-blue-800 border border-blue-200',
  },
  2: {
    label: 'Scope 2',
    title: 'Purchased electricity',
    className: 'bg-purple-100 text-purple-800 border border-purple-200',
  },
  3: {
    label: 'Scope 3',
    title: 'Value chain emissions',
    className: 'bg-gray-100 text-gray-700 border border-gray-200',
  },
}

export default function ScopeTag({ scope }) {
  const scopeNum = parseInt(scope, 10)
  const cfg = CONFIG[scopeNum] || {
    label: scope != null ? `Scope ${scope}` : '—',
    title: '',
    className: 'bg-gray-100 text-gray-500 border border-gray-200',
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cfg.className}`}
      title={cfg.title}
    >
      {cfg.label}
    </span>
  )
}
