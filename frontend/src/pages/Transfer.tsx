import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function Transfer({ userId, lang, t }: Props) {
  const navigate = useNavigate()
  const [targetUid, setTargetUid] = useState('')
  const [amount, setAmount] = useState('')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    const to = parseInt(targetUid)
    const val = parseFloat(amount)
    if (!to || !val || val < 10) { setMsg(t('Invalid input', 'የተሳሳተ ግብዓት')); return }
    setLoading(true)
    try {
      await api.transfer(userId, to, val)
      setMsg(`${t('Transferred', 'ተላክቷል')} ${val} ETB → ${to}`)
    } catch (e: any) {
      setMsg(e.message || t('Failed', 'አልተሳካም'))
    }
    setLoading(false)
  }

  return (
    <div>
      <h2 className="mb-16">{t('Transfer', 'ዝውውር')}</h2>
      <input className="input" type="number" placeholder={t('Recipient User ID', 'የተቀባይ መለያ')} value={targetUid} onChange={e => setTargetUid(e.target.value)} />
      <input className="input" type="number" placeholder={t('Amount (min 10 ETB)', 'መጠን (ቢያንስ 10 ብር)')} value={amount} onChange={e => setAmount(e.target.value)} />
      <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
        {loading ? '...' : t('Send', 'ላክ')}
      </button>
      {msg && <div className="toast">{msg}</div>}
    </div>
  )
}
