import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function Withdraw({ userId, lang, t }: Props) {
  const navigate = useNavigate()
  const [amount, setAmount] = useState('')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    const val = parseFloat(amount)
    if (!val || val < 30) { setMsg(`${t('Minimum', 'ዝቅተኛ')}: 30 ETB`); return }
    setLoading(true)
    try {
      await api.requestWithdraw(userId, val)
      setMsg(`${t('Request submitted!', 'ጥያቄ ቀርቧል!')} ${val} ETB`)
    } catch (e: any) {
      setMsg(e.message || t('Failed', 'አልተሳካም'))
    }
    setLoading(false)
  }

  return (
    <div>
      <h2 className="mb-16">{t('Withdraw', 'ገንዘብ አውጣ')}</h2>
      <input className="input" type="number" placeholder={t('Amount (min 30 ETB)', 'መጠን (ቢያንስ 30 ብር)')} value={amount} onChange={e => setAmount(e.target.value)} />
      <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
        {loading ? '...' : t('Request Withdrawal', 'ማውጣት ይጠይቁ')}
      </button>
      {msg && <div className="toast">{msg}</div>}
    </div>
  )
}
