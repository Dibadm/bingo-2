import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function Balance({ userId, lang, t }: Props) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.getBalance(userId).then(setData).catch(() => {}) }, [userId])
  return (
    <div className="text-center">
      <div style={{ fontSize: 48, marginBottom: 8 }}>💳</div>
      <div className="amount">{data?.balance || 0} ETB</div>
      <div className="text-sm text-muted mt-16">
        <div>{t('Total Deposited', 'ጠቅላላ ያስገቡ')}: {data?.total_deposited || 0} ETB</div>
        <div>{t('Total Withdrawn', 'ጠቅላላ ያወጡ')}: {data?.total_withdrawn || 0} ETB</div>
      </div>
    </div>
  )
}
