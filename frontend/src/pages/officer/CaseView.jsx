import { FileDown, FileWarning, Info, Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import FreezeNoticeModal from "../../components/case/FreezeNoticeModal";
import Legend from "../../components/case/Legend";
import NearestVaspCard from "../../components/case/NearestVaspCard";
import NodePanel from "../../components/case/NodePanel";
import PageHeader from "../../components/common/PageHeader";
import LeadsPanel from "../../components/case/LeadsPanel";
import CeasePanel from "../../components/case/CeasePanel";
import PeoplePanel from "../../components/case/PeoplePanel";
import RequestsPanel from "../../components/case/RequestsPanel";
import { MulesPanel, OutcomesPanel } from "../../components/case/OutcomesPanel";
import RecommendationsPanel from "../../components/case/RecommendationsPanel";
import { ErrorState, Loading } from "../../components/common/Status";
import SummaryStrip from "../../components/case/SummaryStrip";
import TraceGraph from "../../components/case/TraceGraph";
import { useFetch } from "../../hooks/useFetch";
import { useAlertListener } from "../../hooks/useAlerts";
import {
  getCase,
  getReport,
  simulateAlert,
  simulateMovement,
} from "../../lib/api";
import { humanize, shortAddr } from "../../lib/format";

const btn =
  "inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

function CaseBody({ trace, reload }) {
  const [selected, setSelected] = useState(null);
  const [noticeOpen, setNoticeOpen] = useState(false)
  const [inv, setInv] = useState(0) // bumped when the investigation changes (a request moved, a reply arrived)
  const bump = () => setInv((n) => n + 1);
  const [alerts, setAlerts] = useState([]);
  const [simMsg, setSimMsg] = useState(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [simBusy, setSimBusy] = useState(false);

  // Live monitoring: re-read the case every 30 s, and straight away when an alert for it arrives.
  useEffect(() => {
    const timer = setInterval(reload, 30000);
    return () => clearInterval(timer);
  }, [reload]);
  useAlertListener((alert) => {
    if (alert.case_id !== trace.case_id) return;
    setAlerts((a) => [alert, ...a].slice(0, 5));
    reload();
  });

  // Engine mode replays a recorded transfer and re-traces; otherwise (fixture / Demo Mode) there is nothing to
  // replay, so the next scripted alert for this case is pushed instead. Both are SIMULATED.
  const simulate = async () => {
    setSimBusy(true);
    setSimMsg(null);
    try {
      await simulateMovement(trace.case_id).catch(() =>
        simulateAlert(trace.case_id),
      );
    } catch (e) {
      setSimMsg(e.message);
    } finally {
      setSimBusy(false);
    }
  };
  const downloadReport = async () => {
    setReportBusy(true);
    setSimMsg(null);
    try {
      const { blob } = await getReport(trace.case_id);
      const url = URL.createObjectURL(blob);
      Object.assign(document.createElement("a"), {
        href: url,
        download: `${trace.case_id}_evidence_report.pdf`,
      }).click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setSimMsg(`Report failed: ${e.message}`);
    } finally {
      setReportBusy(false);
    }
  };
  const node = selected && trace.graph.nodes.find((n) => n.id === selected);

  return (
    <>
      <PageHeader
        title={`Case ${trace.case_id}`}
        subtitle={`${trace.complaint_id} · ${humanize(trace.fraud_type)} · reported wallet ${shortAddr(trace.wallet, 8)}`}
      >
        <button
          onClick={simulate}
          disabled={simBusy}
          title="Push a SIMULATED alert for this case (replays a recorded fund movement when the engine is on)"
          className={`${btn} border-amber-400/50 text-amber-300 enabled:hover:bg-amber-400/10`}
        >
          <Play className="size-4" />
          {trace.summary.idle_funds > 0
            ? "Simulate fund movement"
            : "Simulate alert"}
        </button>
        <button
          disabled={!trace.nearest_vasp}
          onClick={() => setNoticeOpen(true)}
          title={
            trace.nearest_vasp
              ? "Draft a freeze request to the exchange"
              : "No exchange identified: nothing to freeze"
          }
          className={`${btn} border-emerald-500/50 text-emerald-300 enabled:hover:bg-emerald-500/10`}
        >
          <FileWarning className="size-4" /> Freeze Notice
        </button>
        <button
          onClick={downloadReport}
          disabled={reportBusy}
          title="PDF evidence report: summary, graph, transactions, attribution, risk, recommendations"
          className={`${btn} border-line text-ink enabled:hover:bg-panel-2`}
        >
          {reportBusy ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <FileDown className="size-4" />
          )}
          {reportBusy ? "Building PDF…" : "Download Report"}
        </button>
      </PageHeader>

      <div className="space-y-6 p-6">
        <SummaryStrip trace={trace} />
        {simMsg && <p className="text-xs text-amber-300">{simMsg}</p>}
        {alerts.length > 0 && (
          <ul className="space-y-1 rounded-md border border-line bg-panel-2/60 px-3 py-2 text-xs">
            {alerts.map((a) => (
              <li key={a.id}>
                <span className="font-semibold">
                  {a.type.replaceAll("_", " ")}
                </span>{" "}
                · {a.message}
              </li>
            ))}
          </ul>
        )}
        {trace.notes && (
          <p className="flex items-start gap-2 rounded-md border border-line bg-panel-2/60 px-3 py-2 text-xs text-muted">
            <Info className="mt-px size-3.5 shrink-0" /> {trace.notes}
          </p>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <section className="flex flex-col self-start rounded-lg border border-line bg-panel">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
              <h2 className="text-sm font-semibold">Fund flow</h2>
              <Legend />
            </div>
            <div className="h-[520px]">
              <TraceGraph
                trace={trace}
                selected={selected}
                onSelect={setSelected}
              />
            </div>
            <p className="border-t border-line px-4 py-2 text-xs text-muted">
              Click a wallet for details. Green path = route to the Nearest VASP
              · dashed = bridge / mixer · amber ring = idle funds.
            </p>
          </section>

          <div className="space-y-6">
            {node ? (
              <NodePanel
                node={node}
                graph={trace.graph}
                onClose={() => setSelected(null)}
              />
            ) : (
              <NearestVaspCard
                vasp={trace.nearest_vasp}
                graph={trace.graph}
                onLocate={() => setSelected(trace.nearest_vasp.deposit_address)}
              />
            )}
          </div>
        </div>

        <RecommendationsPanel items={trace.recommendations} />
        <OutcomesPanel caseId={trace.case_id} version={inv} />
        <MulesPanel caseId={trace.case_id} version={inv} />
        <LeadsPanel caseId={trace.case_id} version={inv} onChange={bump} />
        <RequestsPanel caseId={trace.case_id} version={inv} onChange={bump} />
        <PeoplePanel caseId={trace.case_id} version={inv} />
        <CeasePanel caseId={trace.case_id} version={inv} onChange={bump} />
      </div>

      {noticeOpen && (
        <FreezeNoticeModal
          caseId={trace.case_id}
          onClose={() => setNoticeOpen(false)}
        />
      )}
    </>
  );
}

export default function CaseView() {
  const { id } = useParams();
  const { data, loading, error, reload } = useFetch(() => getCase(id), [id]);

  if (loading && !data) return <Loading label={`Loading ${id}…`} />;
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  return <CaseBody key={id} trace={data} reload={reload} />;
}
