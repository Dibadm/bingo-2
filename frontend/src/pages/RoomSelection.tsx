import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

const ROOMS = [
  { fee: 10, label: '10 ETB' },
  { fee: 20, label: '20 ETB' },
  { fee: 50, label: '50 ETB' },
  { fee: 100, label: '100 ETB' },
]

export default function RoomSelection({ userId, lang, t }: Props) {
  const navigate = useNavigate()
  const [rooms, setRooms] = useState(ROOMS.map(r => ({ ...r, pool: 0, players: 0 })))

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await api.getRooms()
        if (data) setRooms(ROOMS.map(r => {
          const rd = data.find((d: any) => d.fee === r.fee)
          return { ...r, pool: rd?.pool || 0, players: rd?.players || 0 }
        }))
      } catch {}
    }
    fetch()
    const iv = setInterval(fetch, 5000)
    return () => clearInterval(iv)
  }, [])

  return (
    <div>
      <h2 className="mb-16">{t('Select Room', 'ክፍል ይምረጡ')}</h2>
      {rooms.map(r => (
        <div key={r.fee} className="room-card" onClick={() => navigate(`/rooms/${r.fee}/cards`)}>
          <div>
            <div className="room-fee">{r.label}</div>
            <div className="text-sm text-muted">👥 {r.players}</div>
          </div>
          <div className="room-info">
            <div className="amount">🏆 {r.pool} ETB</div>
            <div className="text-sm">{t('Prize Pool', 'ሽልማት')}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
