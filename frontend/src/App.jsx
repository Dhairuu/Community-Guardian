import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import StatusBar from './components/StatusBar'
import DailyTip from './components/DailyTip'
import Digest from './components/Digest'
import ChatPanel from './components/ChatPanel'
import GmailScanner from './components/GmailScanner'
import { fetchDigest, checkHealth } from './api'

const PAGE_TITLES = {
  home: 'Daily Digest',
  chat: 'AI Assistant',
  gmail: 'Gmail Scanner',
}

function App() {
  const [activePage, setActivePage] = useState('home')
  const [city, setCity] = useState('Bengaluru')
  const [simpleMode, setSimpleMode] = useState(false)
  const [digest, setDigest] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [healthStatus, setHealthStatus] = useState(null)

  useEffect(() => {
    if (simpleMode) {
      document.body.classList.add('simple-mode')
    } else {
      document.body.classList.remove('simple-mode')
    }
  }, [simpleMode])

  useEffect(() => {
    checkHealth()
      .then(setHealthStatus)
      .catch(() => setHealthStatus({ status: 'offline', data_mode: 'unknown' }))
  }, [])

  useEffect(() => {
    loadDigest()
  }, [city])

  async function loadDigest() {
    setLoading(true)
    setError(null)
    setDigest(null)
    try {
      const data = await fetchDigest(city, simpleMode)
      setDigest(data)
    } catch (err) {
      setError('Could not load safety data. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  function handleReportDismiss(reportId) {
    if (!digest) return
    setDigest({
      ...digest,
      reports: digest.reports.filter(r => r.report.id !== reportId),
    })
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        activePage={activePage}
        onPageChange={setActivePage}
        health={healthStatus}
        isFallback={digest?.is_fallback}
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <TopBar
          pageTitle={PAGE_TITLES[activePage]}
          city={city}
          onCityChange={setCity}
          simpleMode={simpleMode}
          onSimpleModeChange={setSimpleMode}
        />

        {/* Content */}
        <main className="flex-1 overflow-y-auto">
          {activePage === 'home' && (
            <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">
              <StatusBar health={healthStatus} isFallback={digest?.is_fallback} />
              <DailyTip tip={digest?.daily_tip} loading={loading} />
              <Digest
                city={city}
                reports={digest?.reports || []}
                loading={loading}
                error={error}
                simpleMode={simpleMode}
                onDismiss={handleReportDismiss}
              />
            </div>
          )}

          {/* Chat: always mounted to preserve state, hidden when not active */}
          <div style={{ display: activePage === 'chat' ? 'flex' : 'none' }} className="flex-1 flex flex-col h-full">
            <ChatPanel city={city} simpleMode={simpleMode} />
          </div>

          {activePage === 'gmail' && (
            <GmailScanner />
          )}
        </main>

        {/* Footer — only on home page */}
        {activePage === 'home' && (
          <footer className="border-t border-gray-200 text-gray-500 text-center py-3 text-xs space-y-1">
            <p>Community Guardian uses AI to filter safety information. Always verify critical alerts through official sources.</p>
            <p className="font-semibold text-black">Emergency: 112 | Cyber Crime: 1930 | cybercrime.gov.in</p>
            <p className="text-gray-400">Prototype using synthetic data for demonstration purposes.</p>
          </footer>
        )}
      </div>
    </div>
  )
}

export default App
