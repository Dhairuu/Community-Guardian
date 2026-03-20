import { useState, useRef, useEffect } from 'react'
import { sendChat } from '../api'

function ChatPanel({ city, simpleMode }) {
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: `Hi! I'm Community Guardian. Ask me about safety concerns in ${city}. For example: "Any UPI scams in ${city}?"`,
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEnd = useRef(null)

  // Reset chat when city changes
  useEffect(() => {
    setMessages([
      {
        role: 'bot',
        text: `Hi! I'm Community Guardian. Ask me about safety concerns in ${city}. For example: "Any UPI scams in ${city}?"`,
      },
    ])
    setInput('')
    setSending(false)
  }, [city])

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    const msg = input.trim()
    if (!msg || sending) return

    const updatedMessages = [...messages, { role: 'user', text: msg }]
    setMessages(updatedMessages)
    setInput('')
    setSending(true)

    try {
      const history = updatedMessages
        .filter((m, i) => !(i === 0 && m.role === 'bot'))
        .map((m) => ({ role: m.role === 'user' ? 'user' : 'bot', text: m.text }))
      const resp = await sendChat(msg, city, simpleMode, history)
      setMessages((prev) => [
        ...prev,
        { role: 'bot', text: resp.reply, sources: resp.sources },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'bot', text: 'Sorry, I\'m having trouble right now. For emergencies, call 112.' },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-2xl mx-auto space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                  msg.role === 'user'
                    ? 'bg-gray-100 text-black'
                    : 'bg-white text-black'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.text}</p>
                {msg.sources && msg.sources.length > 0 && (
                  <p className="text-xs mt-2 text-gray-400">
                    Sources: {msg.sources.join(', ')}
                  </p>
                )}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="rounded-2xl px-4 py-3 text-sm text-gray-400 italic">
                Analyzing...
              </div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4">
        <div className="max-w-2xl mx-auto flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask about safety in your city..."
            maxLength={500}
            disabled={sending}
            className="flex-1 px-4 py-3 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-1 focus:ring-black disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            className="px-5 py-3 bg-black text-white rounded-xl text-sm font-medium hover:bg-gray-800 disabled:opacity-30 transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatPanel
