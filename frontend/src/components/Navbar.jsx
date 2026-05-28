import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../App'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  const linkClass = ({ isActive }) =>
    isActive
      ? 'px-3 py-1 text-sm font-medium border-b-2 border-green-300 text-white'
      : 'px-3 py-1 text-sm font-medium text-green-200 hover:text-white transition-colors'

  return (
    <nav className="bg-green-900 text-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <svg
                className="w-6 h-6 text-green-300"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z" />
                <path d="M12 2a10 10 0 100 20A10 10 0 0012 2zm0 18a8 8 0 110-16 8 8 0 010 16z" />
                <path d="M11 7h2v2h-2zM11 11h2v6h-2z" />
              </svg>
              <span className="font-bold text-base tracking-tight">Breathe ESG</span>
            </div>
            {user?.company?.name && (
              <>
                <span className="text-green-600 select-none">|</span>
                <span className="text-green-300 text-xs font-medium">
                  {user.company.name}
                </span>
              </>
            )}
          </div>

          {/* Nav links */}
          <div className="flex items-center gap-1">
            <NavLink to="/dashboard" className={linkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/upload" className={linkClass}>
              Upload
            </NavLink>
            <NavLink to="/review" className={linkClass}>
              Review
            </NavLink>
          </div>

          {/* User + logout */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-green-700 flex items-center justify-center text-xs font-semibold text-green-100 uppercase">
                {user?.username?.[0] || '?'}
              </div>
              <span className="text-sm text-green-100">{user?.username}</span>
              {user?.role && (
                <span className="text-xs text-green-400 bg-green-800 px-2 py-0.5 rounded-full">
                  {user.role}
                </span>
              )}
            </div>
            <button
              onClick={handleLogout}
              className="text-xs text-green-300 hover:text-white border border-green-700 hover:border-green-400 px-3 py-1 rounded transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}
