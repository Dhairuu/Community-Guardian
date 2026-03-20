const CITIES = ['Bengaluru', 'Delhi', 'Mumbai', 'Hyderabad', 'Chennai']

function TopBar({ pageTitle, city, onCityChange, simpleMode, onSimpleModeChange }) {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
      {/* Page title */}
      <h2 className="font-headline text-2xl font-bold">{pageTitle}</h2>

      {/* Controls */}
      <div className="flex items-center gap-5">
        {/* City selector */}
        <select
          value={city}
          onChange={(e) => onCityChange(e.target.value)}
          className="bg-white text-black border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-black"
        >
          {CITIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        {/* Pincode — future scope (requires paid API with region param) */}
        <div className="relative">
          <input
            type="text"
            placeholder="Pincode"
            disabled
            maxLength={6}
            className="w-24 px-3 py-1.5 text-sm border border-gray-200 rounded bg-gray-50 text-gray-400 cursor-not-allowed"
          />
          <span className="absolute -top-2 -right-2 text-[9px] bg-black text-white px-1.5 py-0.5 rounded font-semibold">
            PRO
          </span>
        </div>

        {/* Simple Mode toggle */}
        <label className="flex items-center gap-2 cursor-pointer">
          <div className="relative">
            <input
              type="checkbox"
              checked={simpleMode}
              onChange={(e) => onSimpleModeChange(e.target.checked)}
              className="sr-only"
            />
            <div className={`w-9 h-5 rounded-full transition-colors ${simpleMode ? 'bg-black' : 'bg-gray-300'}`}></div>
            <div className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${simpleMode ? 'translate-x-4' : ''}`}></div>
          </div>
          <span className="text-xs text-gray-600">Simple</span>
        </label>

        {/* User icon */}
        <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-semibold text-gray-600">
          U
        </div>
      </div>
    </header>
  )
}

export default TopBar
