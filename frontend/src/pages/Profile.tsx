import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function Profile({ userId, lang, t }: Props) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.getProfile(userId).then(setData).catch(() => {}) }, [userId])
  if (!data) return <div className="text-center text-muted">{t('Loading...', 'በመጫን ላይ...')}</div>
  return (
    <div>
      <div className="card" style={{ cursor: 'default' }}>
        <div className="text-sm text-muted">🆔 ID</div>
        <div className="font-bold">{userId}</div>
      </div>
      <div className="card" style={{ cursor: 'default' }}>
        <div className="text-sm text-muted">📱 {t('Phone', 'ስልክ')}</div>
        <div className="font-bold">{data.phone || 'N/A'}</div>
      </div>
      <div className="card" style={{ cursor: 'default' }}>
        <div className="text-sm text-muted">💰 {t('Balance', 'ቀሪ')}</div>
        <div className="amount">{data.balance || 0} ETB</div>
      </div>
      <div className="card" style={{ cursor: 'default' }}>
        <div className="text-sm text-muted">🎮 {t('Games Played', 'የተጫወቱት ጨዋታ')}</div>
        <div className="font-bold">{data.total_games_played || 0}</div>
      </div>
      <div className="card" style={{ cursor: 'default' }}>
        <div className="text-sm text-muted">🏆 {t('Games Won', 'ያሸነፉት ጨዋታ')}</div>
        <div className="font-bold text-accent">{data.total_games_won || 0}</div>
      </div>
      <div className="card" style={{ cursor: 'default' }}>
        <div className="text-sm text-muted">🔗 {t('Referral Code', 'የጥቆማ ኮድ')}</div>
        <div className="font-bold">{data.referral_code || 'N/A'}</div>
      </div>
    </div>
  )
}
