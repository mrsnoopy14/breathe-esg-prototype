import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { login as apiLogin } from '../api'
import { useAuth } from '../App'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const from = location.state?.from?.pathname || '/dashboard'

  async function handleSubmit(e) {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('Please enter your username and password.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await apiLogin(username.trim(), password)
      const { token, user } = res.data
      login(token, user)
      navigate(from, { replace: true })
    } catch (err) {
      const detail =
        err?.response?.data?.non_field_errors?.[0] ||
        err?.response?.data?.detail ||
        'Invalid credentials. Please try again.'
      setError(detail)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-950 to-green-800 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo block */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-green-700 mb-4 shadow-lg">
            <svg className="w-8 h-8 text-green-200" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22l1-2.3A4.49 4.49 0 008 20C19 20 22 3 22 3c-1 2-8 2-8 2s3-4 7-4c0 0-4 2-4 8z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Breathe ESG</h1>
          <p className="text-green-300 text-sm mt-1">Carbon Data Review Platform</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl shadow-2xl p-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-6">Sign in to your account</h2>

          {error && (
            <div className="mb-4 px-3 py-2 rounded-md bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="username"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  autoFocus
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent transition"
                  placeholder="Enter username"
                  disabled={loading}
                />
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent transition"
                  placeholder="Enter password"
                  disabled={loading}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-6 w-full py-2.5 px-4 bg-green-800 hover:bg-green-700 disabled:bg-green-900 disabled:opacity-60 text-white text-sm font-semibold rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Signing in…
                </span>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-green-500 text-xs mt-6">
          &copy; {new Date().getFullYear()} Breathe ESG. All rights reserved.
        </p>
      </div>
    </div>
  )
}
