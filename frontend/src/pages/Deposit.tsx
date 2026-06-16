import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

interface Props { userId: number; lang: 'en' | 'am'; t: (en: string, am: string) => string }

export default function Deposit({ userId, lang, t }: Props) {
  const navigate = useNavigate()
  const [amount, setAmount] = useState<number | null>(null)
  const [customAmount, setCustomAmount] = useState('')
  const [showCustom, setShowCustom] = useState(false)
  const [sms, setSms] = useState('')
  const [step, setStep] = useState<'amount' | 'sms' | 'done'>('amount')
  const [msg, setMsg] = useState('')

  const presets = [50, 100, 200, 500, 1000]

  const handleSelectAmount = (val: number) => {
    setAmount(val)
    setStep('sms')
    setMsg(`${t('Send to Telebirr:', 'ወደ ቴሌቢር ይላኩ:')} 0911000001 (Abebe K.) — ${val} ETB`)
  }

  const handleSubmitSms = async () => {
    if (!amount || !sms.trim()) return
    try {
      const res = await api.submitDepositSms(userId, sms.trim(), amount)
      setMsg(`${t('Deposit successful!', 'ገንዘብ ተሳክቷል!')} +${res.amount || amount} ETB`)
      setStep('done')
    } catch (e: any) {
      setMsg(e.message || t('Invalid SMS', 'የተሳሳተ ኤስኤምኤስ'))
    }
  }

  if (step === 'done') {
    return (
      <div className="text-center">
        <div style={{ fontSize: 64, marginBottom: 16 }}>✅</div>
        <div className="amount mb-16">{msg}</div>
        <button className="btn btn-primary" onClick={() => navigate('/')}>{t('Back', 'ተመለስ')}</button>
      </div>
    )
  }

  return (
    <div>
      <h2 className="mb-16">{t('Deposit', 'ገንዘብ አስገባ')}</h2>
      {step === 'amount' ? (
        <>
          <div className="flex flex-wrap gap-4 mb-16">
            {presets.map(v => (
              <button key={v} className="btn btn-accent btn-sm" style={{ width: '30%' }} onClick={() => handleSelectAmount(v)}>
                {v} ETB
              </button>
            ))}
          </div>
          <button className="btn btn-outline" onClick={() => setShowCustom(!showCustom)}>
            {t('Custom Amount', 'የራስዎ መጠን')}
          </button>
          {showCustom && (
            <div className="mt-8">
              <input className="input" type="number" placeholder="Amount (min 20)" value={customAmount} onChange={e => setCustomAmount(e.target.value)} />
              <button className="btn btn-primary" onClick={() => { const v = parseInt(customAmount); if (v >= 20) handleSelectAmount(v) }}>
                {t('Continue', 'ቀጥል')}
              </button>
            </div>
          )}
        </>
      ) : (
        <>
          <div className="card mb-16" style={{ cursor: 'default' }}>
            <div className="text-sm text-muted">{msg}</div>
          </div>
          <input className="input" placeholder={t('Paste Telebirr SMS here...', 'የቴሌቢር ኤስኤምኤስ ይለጥፉ...')} value={sms} onChange={e => setSms(e.target.value)} />
          <button className="btn btn-primary" onClick={handleSubmitSms} disabled={!sms.trim()}>
            {t('Verify & Deposit', 'አረጋግጥ እና አስገባ')}
          </button>
        </>
      )}
    </div>
  )
}
