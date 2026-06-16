import { useNavigate } from 'react-router-dom'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function GamesMenu({ userId, t }: Props) {
  const navigate = useNavigate()
  return (
    <div>
      <div className="grid-2">
        <div className="card" onClick={() => navigate('/rooms')}>
          <div className="card-icon">🎱</div>
          <div className="card-label">Bingo</div>
          <div className="card-sub">Play now</div>
        </div>
        <div className="card" style={{ opacity: 0.5 }}>
          <div className="card-icon">🎲</div>
          <div className="card-label">Coming Soon</div>
        </div>
        <div className="card" style={{ opacity: 0.5 }}>
          <div className="card-icon">🎯</div>
          <div className="card-label">Coming Soon</div>
        </div>
        <div className="card" style={{ opacity: 0.5 }}>
          <div className="card-icon">🃏</div>
          <div className="card-label">Coming Soon</div>
        </div>
      </div>
    </div>
  )
}
