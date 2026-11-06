import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import AdminLayout from './pages/admin/AdminLayout'
import BookingDetail from './pages/admin/BookingDetail'
import BookingList from './pages/admin/BookingList'
import Calendar from './pages/admin/Calendar'
import Dashboard from './pages/admin/Dashboard'
import Settings from './pages/admin/Settings'
import ZonesVenues from './pages/admin/ZonesVenues'
import BookingWizard from './pages/book/BookingWizard'
import ComingSoon from './pages/ComingSoon'
import Home from './pages/Home'
import Login from './pages/Login'
import Track from './pages/Track'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="login" element={<Login />} />
            <Route path="book" element={<BookingWizard />} />
            <Route path="track" element={<Track />} />
            <Route path="*" element={<ComingSoon />} />
          </Route>
          <Route path="admin" element={<AdminLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="bookings" element={<BookingList />} />
            <Route path="bookings/:id" element={<BookingDetail />} />
            <Route path="calendar" element={<Calendar />} />
            <Route path="zones" element={<ZonesVenues />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<ComingSoon />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
