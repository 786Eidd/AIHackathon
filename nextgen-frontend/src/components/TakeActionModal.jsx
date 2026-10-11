import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useBackend } from "../context/BackendContext";
import { api, mediaUrl } from "../lib/api";
import { mapsSearchUrl, orderContacts, responsePlan } from "../lib/responsePlan";

const KIND_ICON = { police: "🚓", security: "🛡", rescue: "🚑", fire: "🚒", ambulance: "🚑", other: "☎" };

function ContactCard({ contact, primary }) {
  return (
    <div className={`rounded-[8px] border px-4 py-3 flex items-center gap-3 flex-wrap ${primary ? "border-brand-red bg-[#fff5f5]" : "border-[#e3e3e3]"}`}>
      <span className="text-[20px]" aria-hidden>
        {KIND_ICON[contact.kind] || KIND_ICON.other}
      </span>
      <div className="flex-1 min-w-[150px]">
        <p className="text-brand-navy text-[14px] font-semibold">{contact.label}</p>
        {contact.address && (
          <a href={mapsSearchUrl(contact.address)} target="_blank" rel="noreferrer" className="text-[12px] text-[#0d88c7] underline break-words">
            {contact.address}
          </a>
        )}
      </div>
      {contact.phone && (
        <a
          href={`tel:${contact.phone.replace(/[^\d+]/g, "")}`}
          className={`rounded-[5px] h-[38px] px-4 flex items-center gap-2 text-[14px] font-bold ${
            primary ? "bg-brand-red text-white" : "border border-brand-navy text-brand-navy"
          }`}
        >
          📞 {contact.phone}
        </a>
      )}
    </div>
  );
}

// Opened by "Take Action" on an alert: shows the evidence, what to do, and
// who to call, and only then lets the operator close the alert.
export default function TakeActionModal({ alert, cameraName, onResolve, onClose }) {
  const navigate = useNavigate();
  const { baseUrl, cameras } = useBackend();
  const [site, setSite] = useState(null);
  const [event, setEvent] = useState(null);
  const [resolving, setResolving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getSite(baseUrl).then((data) => !cancelled && setSite(data)).catch(() => !cancelled && setSite({ contacts: [] }));
    if (alert.event_id) {
      api.getEvent(baseUrl, alert.event_id).then((data) => !cancelled && setEvent(data)).catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [baseUrl, alert.event_id]);

  const plan = responsePlan(alert);
  const contacts = orderContacts(site?.contacts, plan);
  const clip = mediaUrl(baseUrl, event?.clip_url);
  const snapshot = mediaUrl(baseUrl, event?.snapshot_url || alert.snapshot_url);
  const high = plan.severity === "high";

  async function resolve() {
    setResolving(true);
    await onResolve();
    setResolving(false);
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-3" onClick={onClose}>
      <div className="bg-white rounded-[10px] w-full max-w-[760px] max-h-full overflow-auto flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className={`px-5 py-4 flex items-start justify-between gap-3 ${high ? "bg-brand-red text-white" : "bg-[#fdf3de] text-[#7a5200]"}`}>
          <div className="min-w-0">
            <p className="text-[17px] font-bold leading-snug">{plan.headline}</p>
            <p className="text-[12.5px] opacity-90">
              {cameraName}
              {alert.created_at ? ` · ${new Date(alert.created_at).toLocaleString()}` : ""}
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-[18px] px-1 opacity-90" aria-label="Close">
            ✕
          </button>
        </div>

        <div className="p-5 flex flex-col gap-5">
          {clip ? (
            <video src={clip} poster={snapshot || undefined} controls autoPlay muted loop className="w-full rounded-[6px] bg-black max-h-[320px]" />
          ) : (
            snapshot && <img src={snapshot} alt="" className="w-full rounded-[6px] bg-black max-h-[320px] object-contain" />
          )}

          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => {
                onClose();
                // Site-wide alerts (panic) have no single camera to open.
                navigate(cameras[alert.camera_id] ? `/cameras/${alert.camera_id}` : "/cameras");
              }}
              className="border border-brand-navy text-brand-navy text-[13px] font-medium rounded-[5px] h-[38px] px-4"
            >
              🎥 {cameras[alert.camera_id] ? "Open live camera" : "Open live cameras"}
            </button>
            {(alert.title || "").toLowerCase() === "unknown_face_detected" && (
              <button
                type="button"
                onClick={() => navigate("/face-management")}
                className="border border-brand-navy text-brand-navy text-[13px] font-medium rounded-[5px] h-[38px] px-4"
              >
                👤 I know this person — enroll them
              </button>
            )}
          </div>

          {event?.payload?.appearance && (
            <div className="bg-[#f4f3fa] rounded-[6px] px-4 py-3">
              <p className="text-brand-navy text-[15px] font-semibold mb-1">About this person</p>
              <div className="flex flex-wrap gap-2 mb-2">
                <span className="bg-white border border-[#e3e3e3] rounded-full px-3 py-1 text-[12px] text-[#3d3a52] font-medium">{event.payload.appearance.label}</span>
                {event.payload.appearance.clothing_colour && (
                  <span className="bg-white border border-[#e3e3e3] rounded-full px-3 py-1 text-[12px] text-[#3d3a52]">
                    Top: {event.payload.appearance.clothing_colour}
                  </span>
                )}
                <span className="bg-white border border-[#e3e3e3] rounded-full px-3 py-1 text-[12px] text-[#3d3a52]">
                  {event.payload.appearance.visits > 1 ? `Visit ${event.payload.appearance.visits}` : "First time seen"}
                </span>
                {event.payload.duration_seconds != null && (
                  <span className="bg-white border border-[#e3e3e3] rounded-full px-3 py-1 text-[12px] text-[#3d3a52]">
                    Stayed {Math.max(1, Math.round(event.payload.duration_seconds))}s
                  </span>
                )}
              </div>
              {event.payload.appearance.visits > 1 && event.payload.appearance.first_seen && (
                <p className="text-[12.5px] text-[#4f4b61]">First seen {new Date(event.payload.appearance.first_seen).toLocaleString()}.</p>
              )}
              {event.payload.appearance.description && <p className="text-[13px] text-[#3d3a52] leading-relaxed mt-1">{event.payload.appearance.description}</p>}
              <p className="text-[11px] text-brand-gray mt-1">Clothing colour is estimated from the picture and can be wrong in poor light.</p>
            </div>
          )}

          <div>
            <p className="text-brand-navy text-[15px] font-semibold mb-2">What to do</p>
            <ol className="flex flex-col gap-2">
              {plan.steps.map((step, i) => (
                <li key={i} className="flex gap-3 text-[13.5px] text-[#3d3a52] leading-relaxed">
                  <span className="shrink-0 size-[22px] rounded-full bg-brand-navy text-white text-[12px] font-bold flex items-center justify-center mt-[1px]">
                    {i + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>

          <div>
            <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
              <p className="text-brand-navy text-[15px] font-semibold">Who to call</p>
              <a href={mapsSearchUrl("police station near me")} target="_blank" rel="noreferrer" className="text-[12.5px] text-[#0d88c7] underline">
                📍 Find the nearest police station
              </a>
            </div>
            {site?.site_address && (
              <p className="text-[12.5px] text-[#4f4b61] bg-[#f4f3fa] rounded-[5px] px-3 py-2 mb-2">
                <span className="font-semibold">Tell them this address:</span> {site.site_name ? `${site.site_name}, ` : ""}
                {site.site_address}
              </p>
            )}
            <div className="flex flex-col gap-2">
              {contacts.map((contact, i) => (
                <ContactCard key={`${contact.label}-${i}`} contact={contact} primary={high && i === 0} />
              ))}
              {site && contacts.length === 0 && <p className="text-[13px] text-[#9c9c9c]">No contacts are set up yet.</p>}
            </div>
            <p className="text-[11.5px] text-brand-gray mt-2">
              Add your local police station, its address and your site guard under{" "}
              <button type="button" onClick={() => navigate("/settings")} className="underline text-[#0d88c7]">
                Settings → Emergency contacts
              </button>
              .
            </p>
          </div>
        </div>

        <div className="border-t border-[#e4e4e4] px-5 py-3 flex items-center justify-end gap-3 flex-wrap sticky bottom-0 bg-white">
          <button type="button" onClick={onClose} className="border border-brand-border text-[#4f4b61] text-[13px] rounded-[5px] h-[40px] px-4">
            Keep open
          </button>
          <button type="button" onClick={resolve} disabled={resolving} className="bg-[#3c9e62] disabled:opacity-60 text-white font-semibold text-[13px] rounded-[5px] h-[40px] px-5">
            {resolving ? "Saving…" : "✓ Handled — mark as resolved"}
          </button>
        </div>
      </div>
    </div>
  );
}
