import { ArrowRight, ClipboardCheck, FileText, Search, ShieldCheck, UserCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import GatewaySidebar from '../components/citizen/GatewaySidebar'
import { DemoNotice, TricolorStrip } from '../components/citizen/CitizenLayout'
import NetworkBackground from '../components/common/NetworkBackground'
import { R } from '../lib/routes'

const STEPS = [
  { icon: FileText, title: 'Register', text: 'Tell us what happened and receive a complaint ID.' },
  { icon: UserCheck, title: 'Review', text: 'An officer reviews your complaint and decides the next steps.' },
  { icon: ClipboardCheck, title: 'Action', text: 'The relevant institutions are contacted. Follow progress with your ID.' },
]

// The page a citizen or officer lands on when sent here from the official government website: the message in the
// middle, the complaint tracker and other doors in a collapsible side panel, a moving graph behind it all.
export default function Gateway() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-bg" data-area="gateway">
      <NetworkBackground />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(56,189,248,0.10),transparent_55%),radial-gradient(ellipse_at_bottom,rgba(11,15,23,0.9),transparent_60%)]"
      />
      <div className="relative z-10 flex min-h-screen flex-col">
        <TricolorStrip />
        <DemoNotice />
        <div className="flex flex-1">
          <GatewaySidebar />
          <main className="flex flex-1 items-center justify-center px-6 py-12">
            <div className="float-slow w-full max-w-2xl space-y-8">
              <section
                aria-label="Hand-off from the official website"
                className="space-y-5 rounded-2xl border border-white/10 bg-panel/55 p-8 text-center shadow-2xl backdrop-blur-md"
              >
                <p className="mx-auto inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs tracking-wide text-accent uppercase">
                  <ShieldCheck className="size-3.5" /> Simulated hand-off from an official cybercrime reporting website
                </p>
                <h1 className="gradient-text text-4xl leading-tight font-extrabold tracking-tight sm:text-5xl">
                  Crypto Fraud Reporting and Response
                </h1>
                <p className="mx-auto max-w-xl text-base text-ink/80">
                  Lost money to a cryptocurrency scam? Report it here, then follow the progress of your complaint with the
                  complaint ID you receive.
                </p>
                <div className="flex flex-wrap items-center justify-center gap-3 pt-1">
                  <Link
                    to={R.file}
                    className="cta-glow inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-3 text-base font-semibold text-bg hover:bg-accent/90"
                  >
                    File a complaint <ArrowRight className="size-4" />
                  </Link>
                  <Link
                    to={R.track}
                    className="inline-flex items-center gap-2 rounded-lg border border-white/20 px-6 py-3 text-base text-ink hover:border-accent/70 hover:bg-white/5"
                  >
                    <Search className="size-4" /> Track a complaint
                  </Link>
                </div>
              </section>

              <ol aria-label="What happens after you report" className="grid gap-3 sm:grid-cols-3">
                {STEPS.map(({ icon: Icon, title, text }, i) => (
                  <li key={title} className="rounded-xl border border-white/10 bg-panel/50 p-4 backdrop-blur-md">
                    <p className="flex items-center gap-2 text-sm font-semibold">
                      <span className="flex size-6 items-center justify-center rounded-full bg-accent/20 text-xs text-accent">{i + 1}</span>
                      <Icon className="size-4 text-accent" /> {title}
                    </p>
                    <p className="mt-2 text-xs text-muted">{text}</p>
                  </li>
                ))}
              </ol>
              <p className="text-center text-xs text-muted">
                For the integrity of the investigation, details of how a complaint is handled are not shown.
              </p>
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
