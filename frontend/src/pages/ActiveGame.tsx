import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function ActiveGame({ userId, lang, t }: Props) {
  const { gid: gidStr } = useParams()
  const [searchParams] = useSearchParams()
  const fee = Number(searchParams.get('fee') || '10')
  const navigate = useNavigate()
  const [game, setGame] = useState<any>(null)
  const [called, setCalled] = useState<number[]>([])
  const [cards, setCards] = useState<any[]>([])
  const [autoWin, setAutoWin] = useState(false)
  const [players, setPlayers] = useState<any[]>([])
  const currentNum = called.length > 0 ? called[called.length - 1] : 0
  const prevNum = called.length > 1 ? called[called.length - 2] : 0

  const fetchAll = useCallback(async () => {
    try {
      const room = await api.getActiveGame(fee)
      if (!room) return
      const gid = room.id
      const [g, c, cds, pl] = await Promise.all([
        api.getGame(gid),
        api.getCalledNumbers(gid),
        api.getGameCards(gid, userId),
        api.getGamePlayers(gid),
      ])
      setGame(g)
      setCalled(c)
      setCards(cds)
      setPlayers(pl)
      const me = pl.find((p: any) => p.user_id === userId)
      if (me) setAutoWin(!!me.auto_win)

      if (g.status === 'ended' || g.status === 'refunded') {
        navigate(`/game/${gid}/end?fee=${fee}`)
      }
    } catch {}
  }, [fee, userId, navigate])

  useEffect(() => {
    const iv = setInterval(fetchAll, 1500)
    fetchAll()
    return () => clearInterval(iv)
  }, [fetchAll])

  const handleCheck = async () => {
    if (!game) return
    try { await api.checkCards(game.id, userId) } catch {}
  }
  const handleBingo = async () => {
    if (!game) return
    try { await api.claimBingo(game.id, userId) } catch {}
  }
  const handleToggleAuto = async () => {
    if (!game) return
    try {
      await api.toggleAuto(game.id, userId)
      setAutoWin(!autoWin)
    } catch {}
  }
  const handleTap = async (cardIndex: number, num: number) => {
    if (!game) return
    try { await api.tapNumber(game.id, userId, cardIndex, num) } catch {}
  }

  const calledSet = new Set(called)
  const progress = game ? (called.length / 75) * 100 : 0

  const callGrid: JSX.Element[] = []
  for (let i = 1; i <= 75; i++) {
    callGrid.push(<div key={i} className={`num-cell ${calledSet.has(i) ? 'called' : ''}`}>{i}</div>)
  }

  return (
    <div>
      <div className="progress-bar"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>
      <div className="text-center text-sm text-muted mb-8">{t('Call', 'ጥሪ')} {called.length}/75</div>
      <div className="flex" style={{ justifyContent: 'center', alignItems: 'center', gap: 16, marginBottom: 12 }}>
        {prevNum > 0 && <div className="ball-small">{prevNum}</div>}
        <div className="ball-large">{currentNum || '🎱'}</div>
      </div>
      <div className="num-grid">{callGrid}</div>

      <div className="flex mt-16 mb-8" style={{ gap: 8 }}>
        <button className={`btn btn-sm ${autoWin ? 'btn-green' : 'btn-outline'}`} onClick={handleToggleAuto}>
          🤖 {autoWin ? t('Auto ON', 'አውቶ በርቷል') : t('Auto OFF', 'አውቶ ጠፍቷል')}
        </button>
        <button className="btn btn-sm btn-outline" onClick={handleCheck}>🔍 {t('Check', 'አረጋግጥ')}</button>
        <button className="btn btn-sm btn-primary" onClick={handleBingo}>🎯 BINGO!</button>
      </div>

      <h3 className="mb-8">{t('Your Cards', 'ካርዶችዎ')}</h3>
      {cards.map(card => {
        const nums = (card.numbers || '').split(',').map(Number)
        return (
          <div key={card.card_index} className="bingo-card">
            <div className="text-sm text-muted mb-8">#{card.card_index + 1}</div>
            <table>
              <tbody>
                {[0, 1, 2, 3, 4].map(row => (
                  <tr key={row}>
                    {[0, 1, 2, 3, 4].map(col => {
                      const idx = col * 5 + row
                      const n = nums[idx] || 0
                      const isCalled = calledSet.has(n)
                      const marked = (card.marked || '').split(',').map(Number).includes(n)
                      const cls = marked ? 'marked' : isCalled ? 'called' : ''
                      return <td key={col} className={cls} onClick={() => handleTap(card.card_index, n)}>{n}</td>
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      })}

      <div className="text-sm text-muted text-center mt-8">
        👥 {t('Players', 'ተጫዋቾች')}: {players.length} | 🏆 {game?.prize_pool || 0} ETB
      </div>
    </div>
  )
}
