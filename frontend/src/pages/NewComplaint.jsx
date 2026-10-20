import { Loader2, Search, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import { trace } from '../lib/api'
import { humanize } from '../lib/format'

// The agreed hero case (C-001). The demo starts by clicking "Fill hero example".
const HERO = {
  wallet: 'TUNoHG2D7iRUtY6ra1ZubJtKe2vHqkM5jo',
  chain: 'tron',
  amount: '12000',
  tx_hash: 'a1c8122e234c54956ae4a5d543e7506ca7b92f7ba6eb99794062aa90a4a35f83',
  fraud_type: 'investment',
  state: 'Karnataka',
}

const CHAINS = ['tron', 'ethereum', 'bsc', 'polygon', 'bitcoin', 'solana']
const FRAUD_TYPES = ['investment', 'task', 'sextortion', 'ransomware', 'phishing', 'darknet', 'other']
const STATES = [
  'Andhra Pradesh', 'Delhi', 'Gujarat', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra',
  'Punjab', 'Rajasthan', 'Tamil Nadu', 'Telangana', 'Uttar Pradesh', 'West Bengal',
]

// Best guess from the address format; the engine re-checks it.
function detectChain(addr) {
  if (/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(addr)) return 'tron'
  if (/^0x[0-9a-fA-F]{40}$/.test(addr)) return 'ethereum'
  if (/^(bc1[0-9a-z]{25,59}|[13][1-9A-HJ-NP-Za-km-z]{25,34})$/.test(addr)) return 'bitcoin'
  if (/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(addr)) return 'solana'
  return null
}

const newComplaintId = () => `NCRP-2026-${String(Math.floor(1000 + Math.random() * 9000))}`

const blank = () => ({ complaint_id: newComplaintId(), wallet: '', chain: '', amount: '', tx_hash: '', fraud_type: '', state: '' })

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

export default function NewComplaint() {
  const navigate = useNavigate()
  const [form, setForm] = useState(blank)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const wallet = form.wallet.trim()
  const detected = wallet && detectChain(wallet)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await trace({
        complaint_id: form.complaint_id.trim(),
        wallet,
        chain: form.chain || detected || null,
        amount: form.amount === '' ? null : Number(form.amount),
        tx_hash: form.tx_hash.trim() || null,
        fraud_type: form.fraud_type || null,
        state: form.state || null,
        reported_at: Math.floor(Date.now() / 1000),
      })
      navigate(`/cases/${res.case_id}`)
    } catch (err) {
      setError(err)
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="New Complaint" subtitle="Start a forward trace from the wallet the victim paid">
        <button
          type="button"
          onClick={() => setForm((f) => ({ ...f, ...HERO }))}
          className="inline-flex items-center gap-1.5 rounded-md border border-accent/50 px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent/10"
        >
          <Sparkles className="size-4" /> Fill hero example
        </button>
      </PageHeader>

      <form onSubmit={submit} className="max-w-3xl space-y-5 p-6">
        <div className="grid gap-5 rounded-lg border border-line bg-panel p-5 sm:grid-cols-2">
          <Field label="Complaint ID">
            <input required value={form.complaint_id} onChange={set('complaint_id')} className={input} />
          </Field>
          <Field label="Chain" hint={!form.chain && detected ? `Auto-detected: ${humanize(detected)}` : null}>
            <select value={form.chain} onChange={set('chain')} className={input}>
              <option value="">Auto-detect</option>
              {CHAINS.map((c) => (
                <option key={c} value={c}>
                  {humanize(c)}
                </option>
              ))}
            </select>
          </Field>

          <div className="sm:col-span-2">
            <Field
              label="Reported wallet"
              hint={wallet && !detected ? 'Address format not recognised. Check for typos.' : 'The address the victim sent funds to.'}
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

          <Field label="Amount lost (USDT)">
            <input type="number" min="0" step="any" value={form.amount} onChange={set('amount')} className={input} />
          </Field>
          <Field label="Fraud type">
            <select value={form.fraud_type} onChange={set('fraud_type')} className={input}>
              <option value="">Unknown</option>
              {FRAUD_TYPES.map((t) => (
                <option key={t} value={t}>
                  {humanize(t)}
                </option>
              ))}
            </select>
          </Field>

          <div className="sm:col-span-2">
            <Field label="Transaction hash (optional)">
              <input value={form.tx_hash} onChange={set('tx_hash')} spellCheck={false} className={`${input} font-mono`} />
            </Field>
          </div>

          <Field label="State">
            <select value={form.state} onChange={set('state')} className={input}>
              <option value="">Unknown</option>
              {STATES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
        </div>

        {error && (
          <p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            Trace failed: {error.message}
          </p>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={busy || !wallet}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
            {busy ? 'Tracing…' : 'Trace funds'}
          </button>
          <span className="text-xs text-muted">Creates a case and opens its fund-flow graph.</span>
        </div>
      </form>
    </>
  )
}
