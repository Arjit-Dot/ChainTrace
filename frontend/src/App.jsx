import { BrowserRouter, Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import CitizenLayout from './components/citizen/CitizenLayout'
import OfficerLayout from './components/officer/OfficerLayout'
import Gateway from './pages/Gateway'
import FileComplaint from './pages/citizen/FileComplaint'
import Submitted from './pages/citizen/Submitted'
import TrackComplaint from './pages/citizen/TrackComplaint'
import CaseView from './pages/officer/CaseView'
import ComplaintDetail from './pages/officer/ComplaintDetail'
import Inbox from './pages/officer/Inbox'
import Dashboard from './pages/officer/Dashboard'
import NetworkView from './pages/officer/NetworkView'
import { R } from './lib/routes'

function NotFound() {
  return (
    <div className="p-6 text-sm text-muted">
      Page not found.{' '}
      <Link to={R.gateway} className="text-accent hover:underline">
        Back to the start
      </Link>
    </div>
  )
}

// Links from the first version of the app keep working.
function LegacyCase() {
  const { id } = useParams()
  return <Navigate to={R.officerCase(id)} replace />
}

export function AppRoutes() {
  return (
    <Routes>
      <Route index element={<Gateway />} />

      <Route path="citizen" element={<CitizenLayout />}>
        <Route index element={<Navigate to={R.file} replace />} />
        <Route path="file" element={<FileComplaint />} />
        <Route path="submitted/:id" element={<Submitted />} />
        <Route path="track" element={<TrackComplaint />} />
      </Route>

      <Route path="officer" element={<OfficerLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="inbox" element={<Inbox />} />
        <Route path="complaints/:id" element={<ComplaintDetail />} />
        <Route path="cases/:id" element={<CaseView />} />
        <Route path="networks" element={<NetworkView />} />
      </Route>

      <Route path="complaint/new" element={<Navigate to={R.file} replace />} />
      <Route path="cases/:id" element={<LegacyCase />} />
      <Route path="network" element={<Navigate to={R.officerNetworks} replace />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
