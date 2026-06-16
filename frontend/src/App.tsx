import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { getTelegramUser } from './api/client'
import MainMenu from './pages/MainMenu'
import GamesMenu from './pages/GamesMenu'
import RoomSelection from './pages/RoomSelection'
import CardSelection from './pages/CardSelection'
import ActiveGame from './pages/ActiveGame'
import GameEnd from './pages/GameEnd'
import Deposit from './pages/Deposit'
import Withdraw from './pages/Withdraw'
import Transfer from './pages/Transfer'
import Balance from './pages/Balance'
import Profile from './pages/Profile'
import Transactions from './pages/Transactions'
import ReferEarn from './pages/ReferEarn'
import AdminPanel from './pages/AdminPanel'

export default function App() {
  const [userId, setUserId] = useState<number | null>(null)
  const [lang, setLang] = useState<'en' | 'am'>('en')
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp
    if (tg) {
      tg.expand()
      tg.ready()
      try { tg.MainButton.hide() } catch {}
    }
    const uid = getTelegramUser()
    if (uid) setUserId(uid)
    else setUserId(12345) // fallback for dev
  }, [])

  const t = (en: string, am: string) => lang === 'am' ? am : en

  if (!userId) return <div className="loading">Loading...</div>

  return (
    <div className="app">
      <div className="header">
        <button className="back-btn" onClick={() => navigate(-1)} hidden={location.pathname === '/'}>
          ←
        </button>
        <span className="title">🎱 Habesha Bet</span>
        <button className="lang-btn" onClick={() => setLang(l => l === 'en' ? 'am' : 'en')}>
          {t('🇪🇹 Am', '🇺🇸 En')}
        </button>
      </div>
      <div className="content">
        <Routes>
          <Route path="/" element={<MainMenu userId={userId} lang={lang} t={t} />} />
          <Route path="/games" element={<GamesMenu userId={userId} lang={lang} t={t} />} />
          <Route path="/rooms/:fee" element={<RoomSelection userId={userId} lang={lang} t={t} />} />
          <Route path="/rooms/:fee/cards" element={<CardSelection userId={userId} lang={lang} t={t} />} />
          <Route path="/game/:gid" element={<ActiveGame userId={userId} lang={lang} t={t} />} />
          <Route path="/game/:gid/end" element={<GameEnd userId={userId} lang={lang} t={t} />} />
          <Route path="/deposit" element={<Deposit userId={userId} lang={lang} t={t} />} />
          <Route path="/withdraw" element={<Withdraw userId={userId} lang={lang} t={t} />} />
          <Route path="/transfer" element={<Transfer userId={userId} lang={lang} t={t} />} />
          <Route path="/balance" element={<Balance userId={userId} lang={lang} t={t} />} />
          <Route path="/profile" element={<Profile userId={userId} lang={lang} t={t} />} />
          <Route path="/transactions" element={<Transactions userId={userId} lang={lang} t={t} />} />
          <Route path="/refer" element={<ReferEarn userId={userId} lang={lang} t={t} />} />
          <Route path="/admin" element={<AdminPanel userId={userId} lang={lang} t={t} />} />
        </Routes>
      </div>
    </div>
  )
}
