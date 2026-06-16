import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function AdminPanel({ userId, lang, t }: Props) {
  const [tab, setTab] = useState('dashboard')
  const [stats, setStats] = useState<any>(null)
  const [withdrawals, setWithdrawals] = useState<any[]>([])
  const [accounts, setAccounts] = useState<any[]>([])
  const [analytics, setAnalytics] = useState<any[]>([])
  const [newAcct, setNewAcct] = useState({ name: '', phone: '', last4: '' })
  const [bcText, setBcText] = useState('')
  const [msg, setMsg] = useState('')

  const fetchTab = async (t: string) => {
    setTab(t)
    try {
      if (t === 'dashboard') setStats(await api.getAdminStats())
      if (t === 'withdrawals') setWithdrawals(await api.getAdminWithdrawals())
      if (t === 'accounts') setAccounts(await api.getAdminAccounts())
      if (t === 'analytics') setAnalytics(await api.getAdminAnalytics())
    } catch {}
  }

  useEffect(() => { fetchTab('dashboard') }, [])

  const handleApprove = async (wid: number) => {
    try { await api.approveWithdrawal(wid, userId); setMsg(`Approved #${wid}`); fetchTab('withdrawals') } catch (e: any) { setMsg(e.message) }
  }
  const handleReject = async (wid: number) => {
    try { await api.rejectWithdrawal(wid, userId); setMsg(`Rejected #${wid}`); fetchTab('withdrawals') } catch (e: any) { setMsg(e.message) }
  }
  const handleAddAccount = async () => {
    if (!newAcct.name || !newAcct.phone || !newAcct.last4) return
    try { await api.addAccount(newAcct.name, newAcct.phone, newAcct.last4); setMsg('Account added!'); setNewAcct({ name: '', phone: '', last4: '' }); fetchTab('accounts') } catch (e: any) { setMsg(e.message) }
  }
  const handleRemoveAccount = async (id: number) => {
    try { await api.removeAccount(id); setMsg('Removed!'); fetchTab('accounts') } catch (e: any) { setMsg(e.message) }
  }
  const handleBroadcast = async () => {
    if (!bcText.trim()) return
    try { await api.broadcast(userId, bcText); setMsg(`Broadcast sent!`); setBcText('') } catch (e: any) { setMsg(e.message) }
  }

  return (
    <div>
      <div className="tab-bar">
        {['dashboard', 'withdrawals', 'accounts', 'broadcast', 'analytics'].map(t => (
          <div key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => fetchTab(t)}>{t}</div>
        ))}
      </div>

      {tab === 'dashboard' && stats && (
        <div className="grid-2">
          <div className="admin-card"><div className="text-sm text-muted">Games</div><div className="admin-stat">{stats.total_games}</div></div>
          <div className="admin-card"><div className="text-sm text-muted">Collected</div><div className="admin-stat">{stats.total_collected} ETB</div></div>
          <div className="admin-card"><div className="text-sm text-muted">Profit</div><div className="admin-stat text-green">{stats.total_profit} ETB</div></div>
          <div className="admin-card"><div className="text-sm text-muted">Players</div><div className="admin-stat">{stats.total_players}</div></div>
        </div>
      )}

      {tab === 'withdrawals' && (
        <div>
          {withdrawals.length === 0 && <div className="text-muted">No pending withdrawals</div>}
          {withdrawals.map(w => (
            <div key={w.id} className="admin-card">
              <div className="flex" style={{ justifyContent: 'space-between' }}>
                <div>
                  <div className="font-bold">#{w.id} — {w.amount} ETB</div>
                  <div className="text-sm text-muted">User: {w.user_id} | {w.phone}</div>
                  <div className="text-sm text-muted">{w.created_at}</div>
                </div>
                <div className="flex" style={{ alignItems: 'center' }}>
                  <button className="btn btn-green btn-sm" onClick={() => handleApprove(w.id)}>✅</button>
                  <button className="btn btn-primary btn-sm" onClick={() => handleReject(w.id)}>❌</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'accounts' && (
        <div>
          {accounts.map(a => (
            <div key={a.id} className="admin-card">
              <div className="flex" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div className="font-bold">{a.name}</div>
                  <div className="text-sm text-muted">{a.phone} ({a.last4})</div>
                </div>
                <button className="btn btn-sm btn-primary" onClick={() => handleRemoveAccount(a.id)}>{t('Remove', 'አስወግድ')}</button>
              </div>
            </div>
          ))}
          <div className="admin-card">
            <input className="input" placeholder="Name" value={newAcct.name} onChange={e => setNewAcct(p => ({ ...p, name: e.target.value }))} />
            <input className="input" placeholder="Phone" value={newAcct.phone} onChange={e => setNewAcct(p => ({ ...p, phone: e.target.value }))} />
            <input className="input" placeholder="Last 4 digits" value={newAcct.last4} onChange={e => setNewAcct(p => ({ ...p, last4: e.target.value }))} />
            <button className="btn btn-green" onClick={handleAddAccount}>+ Add Account</button>
          </div>
        </div>
      )}

      {tab === 'broadcast' && (
        <div>
          <textarea className="input" rows={4} placeholder={t('Type message to broadcast...', 'ለማሰራጨት መልእክት ይጻፉ...')} value={bcText} onChange={e => setBcText(e.target.value)} />
          <button className="btn btn-primary" onClick={handleBroadcast}>{t('Send Broadcast', 'ማሰራጫ ላክ')}</button>
        </div>
      )}

      {tab === 'analytics' && (
        <div>
          <h3 className="mb-8">{t('Peak Hours (7 days)', 'ከፍተኛ ሰዓቶች (7 ቀናት)')}</h3>
          {analytics.map(h => (
            <div key={h.hour} className="admin-card" style={{ cursor: 'default' }}>
              <div className="flex" style={{ justifyContent: 'space-between' }}>
                <span>{h.hour}:00</span>
                <span className="font-bold">{h.cnt} games</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {msg && <div className="toast" onClick={() => setMsg('')}>{msg}</div>}
    </div>
  )
}
