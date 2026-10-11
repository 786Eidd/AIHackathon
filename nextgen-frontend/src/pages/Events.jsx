import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { useBackend } from "../context/BackendContext";
import { mediaUrl } from "../lib/api";

const RISK_TONE = {
  high: "bg-[rgba(255,62,62,0.15)] text-brand-red",
  medium: "bg-[#fdf3de] text-[#c98a12]",
  info: "bg-[#e3f6ea] text-[#3c9e62]",
  low: "bg-[#eef0f4] text-[#6a6888]",
};

function label(eventType) {
  return (eventType || "event").replace(/_/g, " ");
}

function formatTime(iso) {
  return iso ? new Date(iso).toLocaleString() : "—";
}

function EventDetail({ event, cameraName, onClose }) {
  const { baseUrl } = useBackend();
  const snapshot = mediaUrl(baseUrl, event.snapshot_url);
  const clip = mediaUrl(baseUrl, event.clip_url);

  return (
    <div className="fixed inset-0 bg-black/50 z-30 flex items-center justify-center p-6" onClick={onClose}>
      <div className="bg-white rounded-[10px] max-w-[860px] w-full max-h-full overflow-auto p-6 flex flex-col gap-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-brand-navy text-[18px] font-semibold capitalize">{label(event.event_type)}</p>
            <p className="text-[#6a6888] text-[12px]">
              {cameraName} · {formatTime(event.started_at)}
              {event.ended_at ? ` → ${new Date(event.ended_at).toLocaleTimeString()}` : " · ongoing"}
            </p>
          </div>
          <button onClick={onClose} className="text-[#6a6888] text-[18px]">
            ✕
          </button>
        </div>

        {clip ? (
          <video src={clip} poster={snapshot || undefined} controls autoPlay muted loop className="w-full rounded-[5px] bg-black max-h-[420px]" />
        ) : snapshot ? (
          <img src={snapshot} alt="" className="w-full rounded-[5px] bg-black max-h-[420px] object-contain" />
        ) : (
          <div className="h-[160px] rounded-[5px] bg-[#f2f2f2] flex items-center justify-center text-[#9c9c9c] text-[13px]">No snapshot stored for this event.</div>
        )}

        {!clip && (event.risk_level === "high" || event.risk_level === "medium") && event.status === "open" && (
          <p className="text-[11.5px] text-brand-gray">The evidence clip is still recording; it appears here a few seconds after the event.</p>
        )}

        <p className="text-[13px] text-[#4f4b61] whitespace-pre-line leading-relaxed">{event.summary || "No summary."}</p>
      </div>
    </div>
  );
}

function Assistant() {
  const { sendChat, cameras, health } = useBackend();
  const [question, setQuestion] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [minutes, setMinutes] = useState(60);
  const [answer, setAnswer] = useState(null);
  const [busy, setBusy] = useState(false);

  async function ask(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    try {
      const data = await sendChat(question.trim(), cameraId, minutes);
      setAnswer(data.answer);
    } catch (err) {
      setAnswer(`Request failed: ${err.message}`);
    }
    setBusy(false);
  }

  return (
    <form onSubmit={ask} className="border border-[#d9d9d9] rounded-[5px] p-5 flex flex-col gap-3">
      <p className="text-brand-navy text-[16px] font-medium">Ask about recent activity</p>
      {health && !health.qwen_enabled && (
        <p className="text-[11.5px] text-[#8a6416] bg-[#fff8e6] border border-[#f0dcae] rounded px-3 py-2">
          The assistant needs a DashScope key: set <code>DASHSCOPE_API_KEY</code> in the backend's <code>.env</code> and restart it.
        </p>
      )}
      <div className="flex gap-2 flex-wrap">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Was anyone unknown seen at the front door?"
          className="flex-1 basis-full sm:basis-auto min-w-0 sm:min-w-[260px] bg-brand-field border border-brand-border rounded-[5px] h-[42px] px-4 text-[13px] outline-none"
        />
        <select value={cameraId} onChange={(e) => setCameraId(e.target.value)} className="bg-brand-field border border-brand-border rounded-[5px] h-[42px] px-3 text-[13px]">
          <option value="">All cameras</option>
          {Object.values(cameras).map((c) => (
            <option key={c.camera_id} value={c.camera_id}>
              {c.name}
            </option>
          ))}
        </select>
        <select value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} className="bg-brand-field border border-brand-border rounded-[5px] h-[42px] px-3 text-[13px]">
          <option value={15}>Last 15 min</option>
          <option value={60}>Last hour</option>
          <option value={360}>Last 6 hours</option>
          <option value={1440}>Last 24 hours</option>
        </select>
        <button type="submit" disabled={busy} className="bg-brand-navy disabled:opacity-60 text-white font-medium text-[13px] rounded-[5px] h-[42px] px-5">
          {busy ? "Asking…" : "Ask"}
        </button>
      </div>
      {answer && <p className="text-[13px] text-[#4f4b61] whitespace-pre-line leading-relaxed bg-[#f4f3fa] rounded-[5px] px-4 py-3">{answer}</p>}
    </form>
  );
}

export default function Events() {
  const { events, cameras, refreshEvents, baseUrl } = useBackend();
  const [selectedId, setSelectedId] = useState(null);
  const [risk, setRisk] = useState("all");

  useEffect(() => {
    refreshEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows = risk === "all" ? events : events.filter((e) => e.risk_level === risk);
  const selected = events.find((e) => e.event_id === selectedId);
  const nameOf = (id) => cameras[id]?.name || id;

  return (
    <DashboardLayout title="Events & Assistant" actionLabel="Refresh" onAction={refreshEvents}>
      <div className="flex flex-col gap-5">
        <Assistant />

        <div className="flex gap-2 flex-wrap">
          {["all", "high", "medium", "info"].map((r) => (
            <button
              key={r}
              onClick={() => setRisk(r)}
              className={`h-[32px] px-4 rounded-full text-[12px] font-medium capitalize border ${
                risk === r ? "bg-brand-navy text-white border-brand-navy" : "border-brand-border text-[#4f4b61]"
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        <div className="border border-[#cbcbcb] rounded-[10px] overflow-hidden">
          {rows.length === 0 && <div className="text-center text-[#9c9c9c] text-[14px] py-14">No events recorded yet.</div>}
          {rows.map((e) => {
            const thumb = mediaUrl(baseUrl, e.snapshot_url);
            return (
              <button
                key={e.event_id}
                onClick={() => setSelectedId(e.event_id)}
                className="w-full text-left bg-white border-b border-[#eee] last:border-b-0 flex flex-wrap md:flex-nowrap items-center gap-x-5 gap-y-1 px-4 sm:px-6 py-3 hover:bg-[#fafafa]"
              >
                <div className="h-[56px] w-[96px] rounded-[5px] bg-gray-200 overflow-hidden shrink-0">
                  {thumb && <img src={thumb} alt="" loading="lazy" className="w-full h-full object-cover" />}
                </div>
                <div className="flex-1 min-w-0 basis-[55%] md:basis-0">
                  <p className="text-brand-navy text-[14px] font-semibold capitalize">{label(e.event_type)}</p>
                  <p className="text-[#a3a1b3] text-[11.5px] truncate">{(e.summary || "").split("\n")[0]}</p>
                </div>
                <span className={`text-[11px] font-semibold rounded px-2 py-0.5 capitalize ${RISK_TONE[e.risk_level] || RISK_TONE.low}`}>{e.risk_level}</span>
                <span className="text-[#808080] text-[12px] md:w-[130px] truncate">{nameOf(e.camera_id)}</span>
                <span className="text-[#808080] text-[12px] md:w-[150px]">{formatTime(e.started_at)}</span>
                <span className={`text-[12px] w-[52px] ${e.status === "open" ? "text-brand-red font-semibold" : "text-[#9c9c9c]"}`}>
                  {e.status === "open" ? "● live" : "closed"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {selected && <EventDetail event={selected} cameraName={nameOf(selected.camera_id)} onClose={() => setSelectedId(null)} />}
    </DashboardLayout>
  );
}
