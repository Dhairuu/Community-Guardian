const NAV_ITEMS = [
  { key: 'home', label: 'Home', icon: '◉' },
  { key: 'chat', label: 'AI Chat', icon: '◎' },
  { key: 'gmail', label: 'Gmail Scanner', icon: '◈' },
]

function Sidebar({ activePage, onPageChange, health, isFallback }) {
  return (
    <aside className="w-60 h-screen flex flex-col border-r border-gray-200 bg-white shrink-0">
      {/* Masthead */}
      <div className="px-6 py-6 border-b border-gray-200">
        <h1 className="font-headline text-xl font-bold tracking-tight">
          Community<br />Guardian
        </h1>
        <p className="text-xs text-gray-400 mt-1">Safety & Digital Wellness</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            onClick={() => onPageChange(item.key)}
            className={`w-full text-left px-6 py-3 text-sm flex items-center gap-3 transition-colors ${
              activePage === item.key
                ? 'bg-gray-100 font-semibold text-black border-l-2 border-black'
                : 'text-gray-500 hover:bg-gray-50 hover:text-black border-l-2 border-transparent'
            }`}
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* Status */}
      <div className="px-5 py-4 border-t border-gray-200 space-y-2">
        <StatusIndicator health={health} isFallback={isFallback} />
        <p className="text-[10px] text-gray-400 leading-tight">
          Emergency: 112 | Cyber Crime: 1930
        </p>
      </div>
    </aside>
  )
}

function StatusIndicator({ health, isFallback }) {
  const provider = health?.llm_provider || 'unknown'
  const isAiActive = provider !== 'fallback' && provider !== 'unknown'
  const dataMode = health?.data_mode || 'unknown'

  return (
    <div className="flex flex-wrap gap-1.5 text-[10px]">
      <span className={`px-2 py-0.5 rounded border ${
        isAiActive
          ? 'bg-gray-50 text-black border-gray-300'
          : 'bg-gray-100 text-gray-500 border-gray-200'
      }`}>
        AI: {isAiActive ? provider : 'fallback'}
      </span>
      <span className="px-2 py-0.5 rounded border border-gray-200 text-gray-500">
        {dataMode}
      </span>
      {isFallback && (
        <span className="px-2 py-0.5 rounded border border-gray-300 text-gray-500">
          keyword mode
        </span>
      )}
    </div>
  )
}

export default Sidebar
