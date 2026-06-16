import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function GameEnd({ userId, lang, t }: Props) {
  const { gid } = useParams()
  const [searchParams] = useSearchParams()
  const fee = searchParams.get('fee') || '10'
  const navigate = useNavigate()
  const [game, setGame] = useState<any>(null)
  const [winners, setWinners] = useState<any[]>([])

  useEffect(() => {
    const fetch = async () => {
      try {
        if (gid && gid !== '0') {
          const g = await api.getGame(Number(gid))
          setGame(g)
          const winnerIds = (g.winner_ids || '').split(',').filter(Boolean).map(Number)
          const pl = await api.getGamePlayers(Number(gid))
          setWinners(pl.filter((p: any) => winnerIds.includes(p.user_id)))
        } else {
          setGame({ prize_pool: 0, status: 'ended', winner_ids: '' })
        }
      } catch {}
    }
    fetch()
  }, [gid])

  const isWinner = game && game.winner_ids?.split(',').map(Number).includes(userId)

  return (
    <div className="overlay">
      <div className="overlay-content">
        {isWinner ? (
          <>
            <div style={{ fontSize: 64 }}>🎉</div>
            <h2 style={{ color: '#f5c518' }}>{t('YOU WON!', 'አሸንፈዋል!')}</h2>
            <div className="prize">{game?.prize_pool || 0} ETB</div>
            <div className="text-sm text-muted mb-16">{t('Prize split among winners', 'ሽልማት በአሸናፊዎች ይከፈላል')}</div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 64 }}>😞</div>
            <h2>{t('Game Over', 'ጨዋታ አልቋል')}</h2>
            <div className="text-muted mb-16">
              {winners.length > 0
                ? `${t('Winner', 'አሸናፊ')}: @${winners[0]?.user_id || 'Unknown'}`
                : t('No winner this round', 'በዚህ ዙር አሸናፊ የለም')}
            </div>
          </>
        )}
        <button className="btn btn-accent" onClick={() => navigate(`/rooms/${fee}/cards`)}>
          🔄 {t('Play Again', 'እንደገና ይጫወቱ')}
        </button>
      </div>
    </div>
  )
}
