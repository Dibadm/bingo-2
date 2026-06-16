import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function ReferEarn({ userId, lang, t }: Props) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.getProfile(userId).then(setData).catch(() => {}) }, [userId])
  const code = data?.referral_code || 'N/A'
  const link = `https://t.me/HabeshaBetBot?start=ref_${userId}`
  return (
    <div className="text-center">
      <div style={{ fontSize: 48, marginBottom: 8 }}>🔗</div>
      <h2 className="mb-8">{t('Refer & Earn', 'ጋብዝ እና ገቢ አግኝ')}</h2>
      <div className="text-sm text-muted mb-16">
        {t('Earn 5 ETB per referral!', 'በእያንዳንዱ ጥቆማ 5 ብር ያግኙ!')}
      </div>
      <div className="card" style={{ cursor: 'default' }}>
        <div className="text-sm text-muted">{t('Your Referral Code', 'የጥቆማ ኮድዎ')}</div>
        <div className="amount" style={{ fontSize: 20 }}>{code}</div>
      </div>
      <div className="card mt-8" style={{ cursor: 'pointer' }} onClick={() => navigator.clipboard?.writeText(link)}>
        <div className="text-sm text-muted">{t('Tap to copy link', 'አገናኝ ለመቅዳት ይንኩ')}</div>
        <div className="text-sm truncate">{link}</div>
      </div>
      <div className="card mt-8" style={{ cursor: 'default' }}>
        <div className="text-sm text-muted">{t('Total Referrals', 'ጠቅላላ ጥቆማዎች')}</div>
        <div className="font-bold text-accent">{data?.referral_count || 0}</div>
      </div>
    </div>
  )
}
