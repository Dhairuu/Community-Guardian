const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'PHISHING', label: 'Phishing' },
  { key: 'SCAM', label: 'Scam' },
  { key: 'BREACH', label: 'Breach' },
  { key: 'PHYSICAL', label: 'Physical' },
]

function FilterBar({ activeFilter, onFilterChange }) {
  return (
    <div className="flex flex-wrap gap-2">
      {FILTERS.map((f) => (
        <button
          key={f.key}
          onClick={() => onFilterChange(f.key)}
          className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
            activeFilter === f.key
              ? 'bg-black text-white'
              : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
          }`}
        >
          {f.label}
        </button>
      ))}
    </div>
  )
}

export default FilterBar
