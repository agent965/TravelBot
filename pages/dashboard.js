import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/router'
import { useState, useEffect } from 'react'

export default function Dashboard() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formLoading, setFormLoading] = useState(false)
  
  // Form state
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [departureDate, setDepartureDate] = useState('')
  const [maxPrice, setMaxPrice] = useState('')

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login')
    }
  }, [status, router])

  useEffect(() => {
    if (session) {
      fetchAlerts()
    }
  }, [session])

  const fetchAlerts = async () => {
    const res = await fetch('/api/alerts')
    const data = await res.json()
    setAlerts(data)
    setLoading(false)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setFormLoading(true)

    const res = await fetch('/api/alerts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin,
        destination,
        departureDate,
        maxPrice: maxPrice || null,
      }),
    })

    if (res.ok) {
      setOrigin('')
      setDestination('')
      setDepartureDate('')
      setMaxPrice('')
      setShowForm(false)
      fetchAlerts()
    }

    setFormLoading(false)
  }

  const deleteAlert = async (id) => {
    await fetch('/api/alerts', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    })
    fetchAlerts()
  }

  if (status === 'loading' || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-white">
        <div className="text-xl">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen text-white">
      {/* Nav */}
      <nav className="flex justify-between items-center p-6 max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold">✈️ TrackRoth</h1>
        <div className="flex items-center gap-4">
          <span className="text-gray-400">{session?.user?.email}</span>
          <button
            onClick={() => signOut({ callbackUrl: '/' })}
            className="text-gray-400 hover:text-white"
          >
            Sign Out
          </button>
        </div>
      </nav>

      {/* Main */}
      <main className="max-w-4xl mx-auto px-6 py-10">
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-3xl font-bold">Your Flight Alerts</h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-semibold transition"
          >
            + Add Alert
          </button>
        </div>

        {/* Add Alert Form */}
        {showForm && (
          <div className="bg-slate-800 p-6 rounded-xl mb-8">
            <h3 className="text-xl font-semibold mb-4">New Flight Alert</h3>
            <form onSubmit={handleSubmit}>
              <div className="grid md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-gray-400 text-sm mb-1">From (Airport Code)</label>
                  <input
                    type="text"
                    placeholder="e.g. JFK"
                    value={origin}
                    onChange={(e) => setOrigin(e.target.value.toUpperCase())}
                    maxLength={3}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 uppercase"
                    required
                  />
                </div>
                <div>
                  <label className="block text-gray-400 text-sm mb-1">To (Airport Code)</label>
                  <input
                    type="text"
                    placeholder="e.g. LAX"
                    value={destination}
                    onChange={(e) => setDestination(e.target.value.toUpperCase())}
                    maxLength={3}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 uppercase"
                    required
                  />
                </div>
              </div>
              <div className="grid md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-gray-400 text-sm mb-1">Departure Date</label>
                  <input
                    type="date"
                    value={departureDate}
                    onChange={(e) => setDepartureDate(e.target.value)}
                    min={new Date().toISOString().split('T')[0]}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-gray-400 text-sm mb-1">Target Price (optional)</label>
                  <input
                    type="number"
                    placeholder="e.g. 300"
                    value={maxPrice}
                    onChange={(e) => setMaxPrice(e.target.value)}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
              <div className="flex gap-4">
                <button
                  type="submit"
                  disabled={formLoading}
                  className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg font-semibold transition disabled:opacity-50"
                >
                  {formLoading ? 'Creating...' : 'Create Alert'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="text-gray-400 hover:text-white"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Alerts List */}
        {alerts.length === 0 ? (
          <div className="bg-slate-800/50 rounded-xl p-12 text-center">
            <div className="text-5xl mb-4">✈️</div>
            <h3 className="text-xl font-semibold mb-2">No alerts yet</h3>
            <p className="text-gray-400 mb-6">Add your first flight alert to start tracking prices</p>
            <button
              onClick={() => setShowForm(true)}
              className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg font-semibold transition"
            >
              + Add Your First Alert
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {alerts.map((alert) => (
              <div key={alert.id} className="bg-slate-800 rounded-xl p-6 flex justify-between items-center">
                <div>
                  <div className="text-xl font-semibold">
                    {alert.origin} → {alert.destination}
                  </div>
                  <div className="text-gray-400">
                    {new Date(alert.departureDate).toLocaleDateString('en-US', {
                      weekday: 'short',
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </div>
                  {alert.maxPrice && (
                    <div className="text-sm text-blue-400 mt-1">
                      Target: ${alert.maxPrice.toFixed(2)}
                    </div>
                  )}
                </div>
                <div className="text-right">
                  {alert.lastPrice ? (
                    <div className="text-2xl font-bold text-green-400">
                      ${alert.lastPrice.toFixed(2)}
                    </div>
                  ) : (
                    <div className="text-gray-500">Checking...</div>
                  )}
                  <button
                    onClick={() => deleteAlert(alert.id)}
                    className="text-red-400 hover:text-red-300 text-sm mt-2"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Info */}
        <div className="mt-12 bg-slate-800/30 rounded-xl p-6">
          <h3 className="font-semibold mb-2">How alerts work</h3>
          <ul className="text-gray-400 text-sm space-y-1">
            <li>• We check prices every 6 hours</li>
            <li>• You'll get an email when prices drop more than 5%</li>
            <li>• If you set a target price, we'll alert you when it's reached</li>
          </ul>
        </div>
      </main>
    </div>
  )
}
