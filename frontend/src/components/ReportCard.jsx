import { updateReportStatus } from '../api'

const SEVERITY_TOP_BORDER = {
  CRITICAL: 'border-t-2 border-t-black',
  HIGH: 'border-t-2 border-t-gray-700',
  MEDIUM: 'border-t-2 border-t-gray-400',
  LOW: 'border-t-2 border-t-gray-200',
}

const SEVERITY_BADGE = {
  CRITICAL: 'bg-black text-white',
  HIGH: 'bg-gray-200 text-black',
  MEDIUM: 'bg-gray-100 text-gray-700',
  LOW: 'bg-gray-50 text-gray-500 border border-gray-200',
}

function formatDate(dateStr) {
  if (!dateStr) return null
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return null
  }
}

function ReportCard({ report, checklist, simple_checklist, helpline, simpleMode, onDismiss }) {
  const r = report
  const meta = r.metadata || {}
  const newsSource = meta.news_source || r.source
  const imageUrl = meta.image_url
  const pubDate = formatDate(r.published_at)

  async function handleAction(status) {
    if (r.id) {
      await updateReportStatus(r.id, status)
    }
    onDismiss(r.id)
  }

  return (
    <div className={`report-card bg-white border border-gray-200 rounded p-5 ${SEVERITY_TOP_BORDER[r.severity] || ''}`}>
      {/* Source + Date row */}
      <div className="flex items-center gap-2 mb-3 text-xs text-gray-400">
        {imageUrl && (
          <img
            src={imageUrl}
            alt=""
            className="w-4 h-4 rounded-sm object-cover"
            onError={(e) => { e.target.style.display = 'none' }}
          />
        )}
        <span className="font-medium text-gray-600">{newsSource}</span>
        {pubDate && (
          <>
            <span>·</span>
            <span>{pubDate}</span>
          </>
        )}
        {r.confidence && (
          <>
            <span>·</span>
            <span>{Math.round(r.confidence * 100)}% confidence</span>
          </>
        )}
      </div>

      {/* Title */}
      <h3 className="font-headline font-bold text-black text-lg leading-tight mb-2">{r.title}</h3>

      {/* Badges */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        <span className="text-xs px-2 py-0.5 rounded border border-gray-300 text-black font-medium">
          {r.category}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${SEVERITY_BADGE[r.severity] || ''}`}>
          {r.severity}
        </span>
      </div>

      {/* Pattern match */}
      {r.similar_pattern && (
        <div className="text-xs bg-gray-50 border border-gray-200 rounded px-3 py-1.5 mb-3 text-gray-700">
          Matches known pattern: <strong className="text-black">{r.similar_pattern}</strong>
        </div>
      )}

      {/* Content preview */}
      <p className="text-sm text-gray-600 mb-3 line-clamp-2">{r.content}</p>

      {/* Checklist */}
      <div className="mb-3">
        <h4 className="text-sm font-semibold text-black mb-1">
          {simpleMode ? 'What to do:' : 'Action Checklist:'}
        </h4>
        {simpleMode ? (
          <p className="text-gray-700 font-medium">{simple_checklist}</p>
        ) : (
          <ol className="list-decimal list-inside text-sm text-gray-600 space-y-1">
            {(checklist || []).map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        )}
      </div>

      {/* Helpline */}
      {helpline && (
        <div className="helpline-text text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded px-3 py-2 mb-3">
          {helpline}
        </div>
      )}

      {/* URL */}
      {r.url && (
        <a
          href={r.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-gray-400 hover:text-black underline mb-3 inline-block"
        >
          Read original article
        </a>
      )}

      {/* Actions */}
      <div className="flex gap-2 mt-2">
        <button
          onClick={() => handleAction('resolved')}
          className="text-xs px-3 py-1.5 rounded bg-black text-white hover:bg-gray-800 transition-colors font-medium"
        >
          Resolved
        </button>
        <button
          onClick={() => handleAction('dismissed')}
          className="text-xs px-3 py-1.5 rounded bg-white text-gray-600 border border-gray-300 hover:bg-gray-50 transition-colors font-medium"
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}

export default ReportCard
