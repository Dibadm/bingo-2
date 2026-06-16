import { useNavigate } from 'react-router-dom'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function MainMenu({ userId, t }: Props) {
  const navigate = useNavigate()
  const items = [
    { icon: '🎮', label: 'Play Games', path: '/games' },
    { icon: '💰', label: 'Deposit', path: '/deposit' },
    { icon: '💸', label: 'Withdraw', path: '/withdraw' },
    { icon: '🔄', label: 'Transfer', path: '/transfer' },
    { icon: '💳', label: 'Balance', path: '/balance' },
    { icon: '👤', label: 'Profile', path: '/profile' },
    { icon: '📋', label: 'Transactions', path: '/transactions' },
    { icon: '🔗', label: 'Refer & Earn', path: '/refer' },
  ]
  return (
    <div>
      <div className="grid-2">
        {items.map(item => (
          <div key={item.path} className="card" onClick={() => navigate(item.path)}>
            <div className="card-icon">{item.icon}</div>
            <div className="card-label">{item.label}</div>
          </div>
        ))}
      </div>
      <div className="mt-16 text-center text-sm text-muted">
        🆔 {userId}
      </div>
    </div>
  )
}
