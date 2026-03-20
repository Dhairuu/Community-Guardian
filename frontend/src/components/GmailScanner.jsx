import { useState } from 'react'

const MOCK_EMAILS = [
  {
    sender: 'support@bank-secure-verify.com',
    subject: 'URGENT: Your account has been compromised. Verify now.',
    date: 'Mar 18',
    threat: 'Phishing Detected',
    level: 'danger',
  },
  {
    sender: 'noreply@payment-update.net',
    subject: 'Your UPI payment of ₹49,999 is pending. Click to confirm.',
    date: 'Mar 17',
    threat: 'Scam Link',
    level: 'danger',
  },
  {
    sender: 'admin@gov-refund-portal.in',
    subject: 'Income Tax Refund: ₹12,450 ready for processing',
    date: 'Mar 17',
    threat: 'Suspicious',
    level: 'warning',
  },
  {
    sender: 'hr@techcorp.com',
    subject: 'Monthly payslip — March 2026',
    date: 'Mar 16',
    threat: 'Safe',
    level: 'safe',
  },
  {
    sender: 'delivery@flipkart.com',
    subject: 'Your order #FK829301 has been shipped',
    date: 'Mar 15',
    threat: 'Safe',
    level: 'safe',
  },
  {
    sender: 'no-reply@insurance-claim.co',
    subject: 'Claim your free insurance policy — limited time offer!',
    date: 'Mar 15',
    threat: 'Suspicious',
    level: 'warning',
  },
  {
    sender: 'kyc-update@sbi-online-verify.com',
    subject: 'SBI KYC Update Required — Account will be frozen in 24 hours',
    date: 'Mar 14',
    threat: 'Phishing Detected',
    level: 'danger',
  },
]

const BADGE_STYLES = {
  danger: 'bg-black text-white',
  warning: 'border border-black text-black',
  safe: 'border border-gray-300 text-gray-400',
}

function GmailScanner() {
  const [showBanner, setShowBanner] = useState(false)

  return (
    <div className="max-w-4xl mx-auto px-6 py-6">
      {/* Coming Soon */}
      <div className="bg-gray-50 border border-gray-200 rounded px-4 py-3 mb-6">
        <p className="text-sm text-gray-600">
          <span className="font-semibold text-black">Coming Soon</span> — Gmail Scanner will connect to your inbox with read-only access to detect phishing and scam emails. All analysis happens locally — no email content is stored on our servers.
        </p>
      </div>

      {showBanner && (
        <div className="bg-gray-100 border border-gray-300 rounded px-4 py-3 mb-4 text-sm text-gray-700 flex items-center justify-between">
          <span>Gmail Scanner is a planned feature. This is a preview of the interface.</span>
          <button onClick={() => setShowBanner(false)} className="text-gray-400 hover:text-black ml-4">✕</button>
        </div>
      )}

      {/* Email list */}
      <div className="border border-gray-200 rounded overflow-hidden">
        {/* Header row */}
        <div className="flex items-center px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs text-gray-500 font-semibold">
          <span className="w-52 shrink-0">Sender</span>
          <span className="flex-1">Subject</span>
          <span className="w-20 text-right">Date</span>
          <span className="w-36 text-right">Status</span>
        </div>

        {MOCK_EMAILS.map((email, i) => (
          <button
            key={i}
            onClick={() => setShowBanner(true)}
            className={`flex items-center w-full px-4 py-3 text-left text-sm border-b border-gray-100 hover:bg-gray-50 transition-colors ${
              email.level === 'danger' ? 'bg-gray-50/50' : ''
            }`}
          >
            <span className="w-52 shrink-0 truncate text-gray-700 font-medium">
              {email.sender}
            </span>
            <span className={`flex-1 truncate ${email.level === 'safe' ? 'text-gray-500' : 'text-black'}`}>
              {email.subject}
            </span>
            <span className="w-20 text-right text-xs text-gray-400">
              {email.date}
            </span>
            <span className="w-36 text-right">
              <span className={`inline-block text-xs px-2 py-0.5 rounded ${BADGE_STYLES[email.level]}`}>
                {email.threat}
              </span>
            </span>
          </button>
        ))}
      </div>

      <p className="text-xs text-gray-400 mt-4 text-center">
        Preview data — not connected to a real inbox
      </p>
    </div>
  )
}

export default GmailScanner
