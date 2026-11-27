import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import { AppLayout } from './layouts/AppLayout'

// Auth
import LoginPage from './pages/auth/LoginPage'

// Salesman
import SalesmanOrderPage from './pages/salesman/SalesmanOrderPage'
import SalesmanHistoryPage from './pages/salesman/SalesmanHistoryPage'

// Admin
import AdminOrdersPage from './pages/admin/AdminOrdersPage'
import AdminInvoicesPage from './pages/admin/AdminInvoicesPage'
import AdminPaymentsPage from './pages/admin/AdminPaymentsPage'
import AdminMastersPage from './pages/admin/AdminMastersPage'

// Production
import ProductionPage from './pages/production/ProductionPage'
import PurchasesPage from './pages/production/PurchasesPage'
import InventoryPage from './pages/production/InventoryPage'
import CostingPage from './pages/production/CostingPage'

// Owner
import OwnerDashboardPage from './pages/owner/OwnerDashboardPage'

// Accountant
import ReportsPage from './pages/accountant/ReportsPage'
import AuditPage from './pages/accountant/AuditPage'

/** Returns the default landing path for a given role */
function roleHomePath(role: string): string {
  switch (role) {
    case 'salesman': return '/salesman'
    case 'admin': return '/admin/orders'
    case 'production': return '/production'
    case 'accountant': return '/reports'
    case 'owner': return '/owner'
    default: return '/login'
  }
}

/** Wraps routes that require authentication */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <AppLayout>{children}</AppLayout>
}

export default function App() {
  const { user } = useAuth()

  return (
    <Routes>
      {/* Public */}
      <Route
        path="/login"
        element={user ? <Navigate to={roleHomePath(user.role)} replace /> : <LoginPage />}
      />

      {/* Root redirect */}
      <Route
        path="/"
        element={<Navigate to={user ? roleHomePath(user.role) : '/login'} replace />}
      />

      {/* Salesman */}
      <Route path="/salesman" element={<ProtectedRoute><SalesmanOrderPage /></ProtectedRoute>} />
      <Route path="/salesman/history" element={<ProtectedRoute><SalesmanHistoryPage /></ProtectedRoute>} />

      {/* Admin */}
      <Route path="/admin/orders" element={<ProtectedRoute><AdminOrdersPage /></ProtectedRoute>} />
      <Route path="/admin/invoices" element={<ProtectedRoute><AdminInvoicesPage /></ProtectedRoute>} />
      <Route path="/admin/payments" element={<ProtectedRoute><AdminPaymentsPage /></ProtectedRoute>} />
      <Route path="/admin/masters" element={<ProtectedRoute><AdminMastersPage /></ProtectedRoute>} />

      {/* Production */}
      <Route path="/production" element={<ProtectedRoute><ProductionPage /></ProtectedRoute>} />
      <Route path="/production/purchases" element={<ProtectedRoute><PurchasesPage /></ProtectedRoute>} />

      {/* Inventory (shared by admin & production) */}
      <Route path="/inventory" element={<ProtectedRoute><InventoryPage /></ProtectedRoute>} />

      {/* Costing */}
      <Route path="/costing" element={<ProtectedRoute><CostingPage /></ProtectedRoute>} />

      {/* Owner */}
      <Route path="/owner" element={<ProtectedRoute><OwnerDashboardPage /></ProtectedRoute>} />

      {/* Accountant */}
      <Route path="/reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
      <Route path="/audit" element={<ProtectedRoute><AuditPage /></ProtectedRoute>} />

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
