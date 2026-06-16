const BASE = import.meta.env.VITE_API_URL || ''

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  getUser: (uid: number) => request<any>('GET', `/user/${uid}`),
  getBalance: (uid: number) => request<{ balance: number }>('GET', `/user/${uid}/balance`),
  getRooms: () => request<any[]>('GET', '/rooms'),
  getRoom: (fee: number) => request<any>('GET', `/rooms/${fee}`),
  getGame: (gid: number) => request<any>('GET', `/game/${gid}`),
  getActiveGame: (fee: number) => request<any>('GET', `/rooms/${fee}/active-game`),
  getGameCards: (gid: number, uid: number) => request<any[]>('GET', `/game/${gid}/cards/${uid}`),
  getCalledNumbers: (gid: number) => request<number[]>('GET', `/game/${gid}/called`),
  getGamePlayers: (gid: number) => request<any[]>('GET', `/game/${gid}/players`),
  getTransactions: (uid: number) => request<any[]>('GET', `/user/${uid}/transactions`),
  getProfile: (uid: number) => request<any>('GET', `/user/${uid}/profile`),
  getAdminStats: () => request<any>('GET', '/admin/stats'),
  getAdminWithdrawals: () => request<any[]>('GET', '/admin/withdrawals'),
  getAdminAccounts: () => request<any[]>('GET', '/admin/accounts'),
  getAdminAnalytics: () => request<any[]>('GET', '/admin/analytics'),

  selectCards: (uid: number, fee: number, cardIndices: number[]) =>
    request<any>('POST', '/game/select-cards', { user_id: uid, room_fee: fee, card_indices: cardIndices }),
  confirmPurchase: (uid: number, fee: number) =>
    request<any>('POST', '/game/confirm', { user_id: uid, room_fee: fee }),
  checkCards: (gid: number, uid: number) =>
    request<any>('POST', `/game/${gid}/check`, { user_id: uid }),
  claimBingo: (gid: number, uid: number) =>
    request<any>('POST', `/game/${gid}/bingo`, { user_id: uid }),
  toggleAuto: (gid: number, uid: number) =>
    request<any>('POST', `/game/${gid}/toggle-auto`, { user_id: uid }),
  tapNumber: (gid: number, uid: number, cardIndex: number, number: number) =>
    request<any>('POST', `/game/${gid}/tap`, { user_id: uid, card_index: cardIndex, number }),

  submitDepositSms: (uid: number, sms: string, expectedAmount: number) =>
    request<any>('POST', '/deposit/sms', { user_id: uid, sms, expected_amount: expectedAmount }),
  requestWithdraw: (uid: number, amount: number) =>
    request<any>('POST', '/withdraw', { user_id: uid, amount }),
  transfer: (fromUid: number, toUid: number, amount: number) =>
    request<any>('POST', '/transfer', { from_uid: fromUid, to_uid: toUid, amount }),

  approveWithdrawal: (wid: number, adminId: number) =>
    request<any>('POST', `/admin/withdrawals/${wid}/approve`, { admin_id: adminId }),
  rejectWithdrawal: (wid: number, adminId: number) =>
    request<any>('POST', `/admin/withdrawals/${wid}/reject`, { admin_id: adminId }),
  addAccount: (name: string, phone: string, last4: string) =>
    request<any>('POST', '/admin/accounts', { name, phone, last4 }),
  removeAccount: (id: number) =>
    request<any>('DELETE', `/admin/accounts/${id}`),
  updateSetting: (key: string, value: string) =>
    request<any>('POST', '/admin/settings', { key, value }),
  broadcast: (adminId: number, text: string) =>
    request<any>('POST', '/admin/broadcast', { admin_id: adminId, text }),
}

export function getTelegramUser(): number | null {
  try {
    const tg = (window as any).Telegram?.WebApp
    if (tg?.initDataUnsafe?.user?.id) return tg.initDataUnsafe.user.id
  } catch {}
  return null
}
