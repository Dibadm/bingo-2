import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function CardSelection({ userId, lang, t }: Props) {
  const { fee: feeStr } = useParams()
  const fee = Number(feeStr)
  const navigate = useNavigate()
  const [taken, setTaken] = useState<Set<number>>(new Set())
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [balance, setBalance] = useState(0)
  const [pool, setPool] = useState(0)
  const [timer, setTimer] = useState(60)
  const [lastBuyer, setLastBuyer] = useState('None')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    try {
      const [roomData, userData] = await Promise.all([
        api.getRoom(fee),
        api.getBalance(userId),
      ])
      setBalance(userData.balance)
      if (roomData) {
        setPool(roomData.pool || 0)
        setTimer(roomData.timer ?? 60)
        setLastBuyer(roomData.last_buyer || 'None')
        setTaken(new Set(roomData.taken_cards || []))
      }
    } catch {}
  }, [fee, userId])

  useEffect(() => {
    fetchData()
    const iv = setInterval(fetchData, 3000)
    return () => clearInterval(iv)
  }, [fetchData])

  const toggleCard = (idx: number) => {
    if (taken.has(idx) && !selected.has(idx)) return
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else if (next.size < 5) next.add(idx)
      return next
    })
  }

  const selectRandom = (count: number) => {
    const avail: number[] = []
    for (let i = 0; i < 200; i++) {
      if (!taken.has(i) && !selected.has(i)) avail.push(i)
    }
    const picked = avail.sort(() => Math.random() - 0.5).slice(0, count)
    setSelected(prev => new Set([...prev, ...picked]))
  }

  const handleConfirm = async () => {
    if (selected.size === 0) { setError('Select at least 1 card!'); return }
    const total = selected.size * fee
    if (balance < total) { setError(`${t('Insufficient balance', 'በቂ ገንዘብ የለም')}! Need ${total} ETB`); return }
    setLoading(true)
    try {
      await api.selectCards(userId, fee, [...selected])
      await api.confirmPurchase(userId, fee)
      navigate(`/game/0?fee=${fee}`)
    } catch (e: any) {
      setError(e.message || 'Failed')
    }
    setLoading(false)
  }

  const cells: JSX.Element[] = []
  for (let i = 0; i < 200; i++) {
    const cls = selected.has(i) ? 'selected' : taken.has(i) ? 'taken' : 'available'
    cells.push(<div key={i} className={`card-cell ${cls}`} onClick={() => toggleCard(i)}>{i + 1}</div>)
  }

  return (
    <div>
      <div className="flex" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
        <div>💳 <span className="text-accent">{balance} ETB</span></div>
        <div>🏆 <span className="text-accent">{pool} ETB</span></div>
        <div>⏱ {timer}s</div>
      </div>
      <div className="text-sm text-muted mb-8">{t('Last buyer', 'የመጨረሻ ገዢ')}: {lastBuyer}</div>
      <div className="card-grid">{cells}</div>
      <div className="flex mt-8 mb-8" style={{ gap: 8 }}>
        <button className="btn btn-outline btn-sm" onClick={() => selectRandom(1)}>🎲 +1</button>
        <button className="btn btn-outline btn-sm" onClick={() => selectRandom(2)}>🎲 +2</button>
        <button className="btn btn-primary btn-sm" onClick={handleConfirm} disabled={loading}>
          {loading ? '...' : `🚀 ${t('Start', 'ጀምር')} (${selected.size} × ${fee} = ${selected.size * fee} ETB)`}
        </button>
      </div>
      {error && <div className="toast">{error}</div>}
    </div>
  )
}
