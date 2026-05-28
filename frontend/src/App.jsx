import React, { createContext, useContext, useState, useEffect } from 'react'
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom'
import { getMe } from './api'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import UploadPage from './pages/UploadPage'
import ReviewPage from './pages/ReviewPage'

export const AuthContext = createContext(null)

export function useAuth() {
  return useContext(AuthContext)
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500 text-sm animate-pulse">Loading session…</div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}

function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('esg_token')
    if (!token) {
      setLoading(false)
      return
    }
    getMe()
      .then((res) => setUser(res.data))
      .catch(() => {
        localStorage.removeItem('esg_token')
      })
      .finally(() => setLoading(false))
  }, [])

  function handleLogin(token, userData) {
    localStorage.setItem('esg_token', token)
    setUser(userData)
  }

  function handleLogout() {
    localStorage.removeItem('esg_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, login: handleLogin, logout: handleLogout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/upload"
            element={
              <ProtectedRoute>
                <UploadPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/review"
            element={
              <ProtectedRoute>
                <ReviewPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
