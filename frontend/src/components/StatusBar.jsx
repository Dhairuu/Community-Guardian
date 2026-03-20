function StatusBar({ health, isFallback }) {
  const provider = health?.llm_provider || 'unknown'
  const isAiActive = provider !== 'fallback' && provider !== 'unknown'
  const aiLabel = isAiActive ? `AI: ${provider}` : 'AI: Fallback Mode'
  const dataMode = health?.data_mode || 'unknown'

  return (
    <div className="flex flex-wrap gap-2 text-xs">
      <span className={`px-2 py-1 rounded border font-medium ${
        isAiActive
          ? 'bg-gray-50 text-black border-gray-300'
          : 'bg-gray-100 text-gray-500 border-gray-200'
      }`}>
        {aiLabel}
      </span>
      <span className="px-2 py-1 rounded border border-gray-200 text-gray-500 font-medium">
        Data: {dataMode}
      </span>
      {isFallback && (
        <span className="px-2 py-1 rounded border border-gray-300 text-gray-500 font-medium">
          Using keyword classification — LLM was unavailable for this digest
        </span>
      )}
    </div>
  )
}

export default StatusBar
