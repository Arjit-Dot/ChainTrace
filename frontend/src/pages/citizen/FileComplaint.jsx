import { Loader2, Send, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fileComplaint } from '../../lib/api'
import { humanize } from '../../lib/format'
import { R } from '../../lib/routes'

// A demo shortcut: the agreed hero case (fictional).
const DEMO = {
  reporter_name: 'Asha Verma',
  reporter_mobile: '9876543210',
  wallet: 'TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo',
  amount: '12000',
  tx_hash: 'a1c8122e234c54956ae4a5d543e7506ca7b92f7ba6eb99794062aa90a4a35f83',
  fraud_type: 'investment',
  state: 'Karnataka',
  description: 'I paid into a fake trading app that promised daily returns.',
}

const CHAINS = ['tron', 'ethereum', 'bsc', 'polygon', 'bitcoin', 'solana']
const FRAUD_TYPES = ['investment', 'task', 'sextortion', 'ransomware', 'phishing', 'darknet', 'other']
const STATES = [
  'Andhra Pradesh', 'Delhi', 'Gujarat', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra',
  'Punjab', 'Rajasthan', 'Tamil Nadu', 'Telangana', 'Uttar Pradesh', 'West Bengal',
]

// Best guess from the address format; the officer's system re-checks it.
function detectChain(addr) {
  if (/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(addr)) return 'tron'
  if (/^0x[0-9a-fA-F]{40}$/.test(addr)) return 'ethereum'
  if (/^(bc1[0-9a-z]{25,59}|[13][1-9A-HJ-NP-Za-km-z]{25,34})$/.test(addr)) return 'bitcoin'
  if (/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(addr)) return 'solana'
  return null
}

const blank = () => ({
  reporter_name: '', reporter_mobile: '', chain: '', wallet: '', amount: '', tx_hash: '', fraud_type: '', state: '', description: '',
})

const input =
  'w-full rounded-md border border-line bg-bg px-3 py-2 text-sm text-ink placeholder:text-muted/60 focus:border-accent focus:outline-none'

function Field({ label, hint, children }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium tracking-wide text-muted uppercase">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted">{hint}</span>}
    </label>
  )
}

export default function FileComplaint() {
  const navigate = useNavigate()
  const [form, setForm] = useState(blank)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const wallet = form.wallet.trim()
  const detected = wallet && detectChain(wallet)
  const mobileOk = /^\d{10}$/.test(form.reporter_mobile)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const nz = (v) => (v.trim() === '' ? null : v.trim())
      const receipt = await fileComplaint({
        reporter_name: form.reporter_name.trim(),
        reporter_mobile: form.reporter_mobile.trim(),
        wallet,
        chain: form.chain || detected || null,
        amount: form.amount === '' ? null : Number(form.amount),
        tx_hash: nz(form.tx_hash),
        fraud_type: form.fraud_type || null,
        state: form.state || null,
        description: nz(form.description),
      })
      navigate(R.submitted(receipt.complaint_id))
    } catch (err) {
      setError(err)
      setBusy(false)
    }
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Report a crypto fraud</h1>
          <p className="mt-1 text-sm text-muted">Tell us where you sent the money. You will receive a complaint ID to follow progress.</p>
        </div>
        <button
          type="button"
          onClick={() => setForm((f) => ({ ...f, ...DEMO }))}
          className="inline-flex items-center gap-1.5 rounded-md border border-accent/50 px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent/10"
        >
          <Sparkles className="size-4" /> Fill demo example
        </button>
      </div>

      <form onSubmit={submit} className="max-w-3xl space-y-5">
        <div className="grid gap-5 rounded-lg border border-line bg-panel p-5 sm:grid-cols-2">
          <Field label="Your name">
            <input required maxLength={80} value={form.reporter_name} onChange={set('reporter_name')} autoComplete="name" className={input} />
          </Field>
          <Field label="Mobile number" hint={form.reporter_mobile && !mobileOk ? 'Enter a 10 digit mobile number.' : 'We use it only to contact you about this complaint.'}>
            <input
              required
              inputMode="numeric"
              maxLength={10}
              value={form.reporter_mobile}
              onChange={set('reporter_mobile')}
              autoComplete="tel"
              className={input}
            />
          </Field>

          <div className="sm:col-span-2">
            <Field
              label="Wallet you sent the money to"
              hint={wallet && !detected ? 'Address format not recognised. Check for typos.' : 'The wallet address from your payment record.'}
            >
              <input
                required
                value={form.wallet}
                onChange={set('wallet')}
                placeholder="e.g. T… (TRON) or 0x… (Ethereum)"
                spellCheck={false}
                className={`${input} font-mono`}
              />
            </Field>
          </div>

          <Field label="Network" hint={!form.chain && detected ? `Auto-detected: ${humanize(detected)}` : null}>
            <select value={form.chain} onChange={set('chain')} className={input}>
              <option value="">Auto-detect</option>
              {CHAINS.map((c) => (
                <option key={c} value={c}>
                  {humanize(c)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Amount lost (USDT)">
            <input type="number" min="0" step="any" value={form.amount} onChange={set('amount')} className={input} />
          </Field>
          <Field label="Type of fraud">
            <select value={form.fraud_type} onChange={set('fraud_type')} className={input}>
              <option value="">Not sure</option>
              {FRAUD_TYPES.map((t) => (
                <option key={t} value={t}>
                  {humanize(t)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="State">
            <select value={form.state} onChange={set('state')} className={input}>
              <option value="">Not sure</option>
              {STATES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>

          <div className="sm:col-span-2">
            <Field label="Transaction ID (optional)">
              <input value={form.tx_hash} onChange={set('tx_hash')} spellCheck={false} className={`${input} font-mono`} />
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="What happened (optional)">
              <textarea rows={4} maxLength={2000} value={form.description} onChange={set('description')} className={input} />
            </Field>
          </div>
        </div>

        {error && (
          <p role="alert" className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            Could not submit your complaint: {error.message}
          </p>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={busy || !wallet || !form.reporter_name.trim() || !mobileOk}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            {busy ? 'Submitting…' : 'Submit complaint'}
          </button>
          <span className="text-xs text-muted">You will get a complaint ID on the next page.</span>
        </div>
      </form>
    </>
  )
}
