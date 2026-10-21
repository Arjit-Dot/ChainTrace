import { ArrowRight, ExternalLink, FileText, Search, ShieldCheck, UserCog } from 'lucide-react'
import { Link } from 'react-router-dom'
import { DemoNotice, TricolorStrip } from '../components/citizen/CitizenLayout'
import { R } from '../lib/routes'

const door = 'group flex items-center justify-between gap-3 rounded-lg border border-line bg-panel-2/60 px-4 py-3 text-sm hover:border-accent/60'

// The page a citizen or officer lands on when sent here from the official government website.
export default function Gateway() {
  return (
    <div className="min-h-full" data-area="gateway">
      <TricolorStrip />
      <DemoNotice />
      <main className="mx-auto max-w-4xl space-y-8 px-6 py-10">
        <section className="rounded-lg border border-line bg-panel px-5 py-4" aria-label="Hand-off from the official website">
          <p className="flex items-center gap-2 text-xs tracking-wide text-muted uppercase">
            <ShieldCheck className="size-4 text-accent" /> Simulated hand-off from an official cybercrime reporting website
          </p>
          <h1 className="mt-2 text-2xl font-bold tracking-tight">Crypto Fraud Reporting and Response</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            This module handles complaints where money was sent in cryptocurrency. Report what happened, and follow the
            progress of your complaint with the complaint ID you receive.
          </p>
        </section>

        <div className="grid gap-5 md:grid-cols-2">
          <section className="space-y-3 rounded-lg border border-line bg-panel p-5" aria-label="For citizens">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <FileText className="size-5 text-accent" /> For citizens
            </h2>
            <p className="text-sm text-muted">Lost money to a crypto scam? Tell us, then check progress at any time.</p>
            <Link to={R.file} className={door}>
              <span className="flex items-center gap-2">
                <FileText className="size-4" /> File a complaint
              </span>
              <ArrowRight className="size-4 text-muted group-hover:text-accent" />
            </Link>
            <Link to={R.track} className={door}>
              <span className="flex items-center gap-2">
                <Search className="size-4" /> Track a complaint
              </span>
              <ArrowRight className="size-4 text-muted group-hover:text-accent" />
            </Link>
          </section>

          <section className="space-y-3 rounded-lg border border-line bg-panel p-5" aria-label="For officers">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <UserCog className="size-5 text-accent" /> For officers
            </h2>
            <p className="text-sm text-muted">
              Review incoming complaints, run the investigation and take action. Opens in a separate tab.
            </p>
            <a href={R.officer} target="_blank" rel="noopener noreferrer" className={door}>
              <span className="flex items-center gap-2">
                <UserCog className="size-4" /> Open the officer console
              </span>
              <ExternalLink className="size-4 text-muted group-hover:text-accent" />
            </a>
          </section>
        </div>

        <section className="space-y-2 text-sm text-muted" aria-label="What happens next">
          <h2 className="text-sm font-semibold text-ink">What happens after you report</h2>
          <ol className="list-decimal space-y-1 pl-5">
            <li>Your complaint is registered and you receive a complaint ID.</li>
            <li>An officer reviews it and decides on the next steps.</li>
            <li>You can follow the status of your complaint with your ID. For the integrity of the investigation, details of how it is handled are not shown.</li>
          </ol>
          <p className="pt-2">If you have just lost money, also call the National Cyber Crime Helpline 1930 right away.</p>
        </section>
      </main>
    </div>
  )
}
