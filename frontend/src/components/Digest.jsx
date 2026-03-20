import { useState } from 'react'
import FilterBar from './FilterBar'
import ReportCard from './ReportCard'

function Digest({ city, reports, loading, error, simpleMode, onDismiss }) {
  const [filter, setFilter] = useState('all')

  const filtered = filter === 'all'
    ? reports
    : reports.filter(r => r.report.category === filter)

  return (
    <section>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h2 className="text-xl font-headline font-bold text-black">
          Safety Digest — {city}
        </h2>
        <FilterBar activeFilter={filter} onFilterChange={setFilter} />
      </div>

      {loading && (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <div className="spinner"></div>
          <p className="text-gray-400 text-sm">Analyzing safety data for {city}...</p>
        </div>
      )}

      {error && (
        <div className="bg-gray-50 border border-gray-300 rounded p-4 text-gray-800 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded p-6 text-center text-gray-600">
          No safety concerns found for your area. That's good news!
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.map((ar, i) => (
          <ReportCard
            key={ar.report.id || i}
            report={ar.report}
            checklist={ar.checklist}
            simple_checklist={ar.simple_checklist}
            helpline={ar.helpline}
            simpleMode={simpleMode}
            onDismiss={onDismiss}
          />
        ))}
      </div>
    </section>
  )
}

export default Digest
