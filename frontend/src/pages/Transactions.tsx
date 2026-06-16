import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function Transactions({ userId, lang, t }: Props) {
  const [txns, setTxns] = useState<any[]>([])
  useEffect(() => { api.getTransactions(userId).then(setTxns).catch(() => {}) }, [userId])
  return (
    <div>
      <h2 className="mb-16">{t('Transactions', 'ግብይቶች')}</h2>
      {txns.length === 0 && <div className="text-center text-muted">{t('No transactions', 'ምንም ግብይቶች የሉም')}</div>}
      {txns.map(tx => (
        <div key={tx.id} className="card" style={{ cursor: 'default' }}>
          <div className="flex" style={{ justifyContent: 'space-between' }}>
            <div>
              <span className="text-sm text-muted">{tx.type}</span>
              <div className="text-sm">{tx.created_at?.slice(0, 10)}</div>
            </div>
            <div className={`font-bold ${tx.amount > 0 ? 'text-green' : 'text-red'}`}>
              {tx.amount > 0 ? '+' : ''}{tx.amount} ETB
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
