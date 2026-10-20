import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import Layout from './components/common/Layout'
import CaseView from './pages/CaseView'
import Dashboard from './pages/Dashboard'
import NetworkView from './pages/NetworkView'
import NewComplaint from './pages/NewComplaint'

function NotFound() {
  return (
    <div className="p-6 text-sm text-muted">
      Page not found.{' '}
      <Link to="/" className="text-accent hover:underline">
        Back to dashboard
      </Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="complaint/new" element={<NewComplaint />} />
          <Route path="cases/:id" element={<CaseView />} />
          <Route path="network" element={<NetworkView />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
