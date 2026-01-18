import Link from 'next/link'
import { useSession } from 'next-auth/react'

export default function Home() {
  const { data: session } = useSession()

  return (
    <div className="min-h-screen text-white">
      {/* Nav */}
      <nav className="flex justify-between items-center p-6 max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold">✈️ TrackRoth</h1>
        <div>
          {session ? (
            <Link href="/dashboard" className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg">
              Dashboard
            </Link>
          ) : (
            <Link href="/login" className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg">
              Sign In
            </Link>
          )}
        </div>
      </nav>

      {/* Hero */}
      <main className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center">
          <h2 className="text-5xl md:text-7xl font-bold mb-6">
            Never Miss a<br />
            <span className="text-blue-400">Cheap Flight</span> Again
          </h2>
          <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
            Track flight prices and get instant alerts when they drop. 
            Set your target price and we'll notify you the moment it hits.
          </p>
          <Link
            href={session ? '/dashboard' : '/login'}
            className="inline-block bg-blue-600 hover:bg-blue-700 text-lg px-8 py-4 rounded-lg font-semibold transition"
          >
            Start Tracking for Free →
          </Link>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-8 mt-32">
          <div className="bg-slate-800/50 p-6 rounded-xl">
            <div className="text-3xl mb-4">🎯</div>
            <h3 className="text-xl font-semibold mb-2">Set Your Price</h3>
            <p className="text-gray-400">
              Tell us your target price and we'll alert you the moment flights drop to your budget.
            </p>
          </div>
          <div className="bg-slate-800/50 p-6 rounded-xl">
            <div className="text-3xl mb-4">📉</div>
            <h3 className="text-xl font-semibold mb-2">Price Drop Alerts</h3>
            <p className="text-gray-400">
              Get notified automatically when prices drop more than 5% from the last check.
            </p>
          </div>
          <div className="bg-slate-800/50 p-6 rounded-xl">
            <div className="text-3xl mb-4">✉️</div>
            <h3 className="text-xl font-semibold mb-2">Email Notifications</h3>
            <p className="text-gray-400">
              Receive instant email alerts so you never miss a deal, even when you're away.
            </p>
          </div>
        </div>

        {/* How it works */}
        <div className="mt-32 text-center">
          <h3 className="text-3xl font-bold mb-12">How It Works</h3>
          <div className="grid md:grid-cols-3 gap-8">
            <div>
              <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                1
              </div>
              <h4 className="font-semibold mb-2">Add Your Flight</h4>
              <p className="text-gray-400">Enter your origin, destination, and travel date</p>
            </div>
            <div>
              <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                2
              </div>
              <h4 className="font-semibold mb-2">Set Target Price</h4>
              <p className="text-gray-400">Optionally set a target price you want to hit</p>
            </div>
            <div>
              <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                3
              </div>
              <h4 className="font-semibold mb-2">Get Alerted</h4>
              <p className="text-gray-400">We'll email you when the price drops</p>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="mt-32 text-center bg-slate-800/50 rounded-2xl p-12">
          <h3 className="text-3xl font-bold mb-4">Ready to Save on Flights?</h3>
          <p className="text-gray-400 mb-8">Join TrackRoth and start tracking your first flight in seconds.</p>
          <Link
            href={session ? '/dashboard' : '/login'}
            className="inline-block bg-blue-600 hover:bg-blue-700 text-lg px-8 py-4 rounded-lg font-semibold transition"
          >
            Get Started Free →
          </Link>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center text-gray-500 py-12">
        <p>© 2026 TrackRoth. Track smarter, fly cheaper.</p>
      </footer>
    </div>
  )
}
