function DailyTip({ tip, loading }) {
  return (
    <section className="bg-gray-50 border border-gray-200 rounded p-4">
      <h2 className="text-sm font-headline font-bold text-black mb-1">Today's Security Tip</h2>
      {loading ? (
        <p className="text-gray-400 animate-pulse">Loading tip...</p>
      ) : (
        <p className="text-gray-700 text-sm">{tip || 'Stay alert and stay safe.'}</p>
      )}
    </section>
  )
}

export default DailyTip
