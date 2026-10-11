import { useEffect, useState } from "react";
import { useBackend } from "../context/BackendContext";
import { api } from "../lib/api";
import { CONTACT_KINDS, mapsSearchUrl } from "../lib/responsePlan";

const inputClass = "bg-brand-field border border-brand-border rounded-[5px] h-[40px] px-3 text-[13px] outline-none min-w-0";

// Site address and the contacts shown when an operator takes action on an alert.
export default function EmergencyContacts() {
  const { baseUrl, pushToast } = useBackend();
  const [site, setSite] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getSite(baseUrl).then(setSite).catch(() => setSite({ site_name: "", site_address: "", contacts: [] }));
  }, [baseUrl]);

  if (!site) return <p className="text-[13px] text-[#9c9c9c]">Loading…</p>;

  const setField = (key, value) => setSite((s) => ({ ...s, [key]: value }));
  const setContact = (index, key, value) =>
    setSite((s) => ({ ...s, contacts: s.contacts.map((c, i) => (i === index ? { ...c, [key]: value } : c)) }));
  const removeContact = (index) => setSite((s) => ({ ...s, contacts: s.contacts.filter((_, i) => i !== index) }));
  const addContact = (kind, label) =>
    setSite((s) => ({ ...s, contacts: [...s.contacts, { kind, label, phone: "", address: "" }] }));

  async function save() {
    const contacts = site.contacts.filter((c) => c.label.trim());
    setSaving(true);
    try {
      setSite(await api.saveSite(baseUrl, { ...site, contacts }));
      pushToast("Emergency contacts saved", "Operators will see these when they take action on an alert.", "medium");
    } catch (e) {
      pushToast("Could not save", e.message, "high");
    }
    setSaving(false);
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[12.5px] text-[#6a6888] leading-relaxed">
        Shown to the operator when they press <b>Take Action</b> on an alert. The national helplines are filled in already; add your nearest
        police station (with its direct number and address) and your own guard or site manager.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <input className={inputClass} placeholder="Site name (e.g. Dream Home)" value={site.site_name} onChange={(e) => setField("site_name", e.target.value)} />
        <input
          className={inputClass}
          placeholder="Site address — read out to the police"
          value={site.site_address}
          onChange={(e) => setField("site_address", e.target.value)}
        />
      </div>

      <div className="flex flex-col gap-3">
        {site.contacts.map((contact, i) => (
          <div key={i} className="border border-[#e3e3e3] rounded-[6px] p-3 grid grid-cols-1 sm:grid-cols-[150px_1fr_150px_auto] gap-2 items-center">
            <select className={inputClass} value={contact.kind} onChange={(e) => setContact(i, "kind", e.target.value)}>
              {CONTACT_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
            <input className={inputClass} placeholder="Name (e.g. Model Town Police Station)" value={contact.label} onChange={(e) => setContact(i, "label", e.target.value)} />
            <input className={inputClass} placeholder="Phone" inputMode="tel" value={contact.phone} onChange={(e) => setContact(i, "phone", e.target.value)} />
            <button type="button" onClick={() => removeContact(i)} className="text-brand-red text-[12.5px] font-medium h-[40px] px-2 justify-self-start sm:justify-self-auto">
              Remove
            </button>
            <input
              className={`${inputClass} sm:col-span-4`}
              placeholder="Address (optional — opens in Maps)"
              value={contact.address}
              onChange={(e) => setContact(i, "address", e.target.value)}
            />
          </div>
        ))}
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        <button type="button" onClick={() => addContact("police", "Nearest police station")} className="border border-brand-navy text-brand-navy text-[12.5px] font-medium rounded-[5px] h-[36px] px-3">
          + Police station
        </button>
        <button type="button" onClick={() => addContact("security", "Site guard")} className="border border-brand-navy text-brand-navy text-[12.5px] font-medium rounded-[5px] h-[36px] px-3">
          + Guard / manager
        </button>
        <button type="button" onClick={() => addContact("other", "")} className="border border-brand-border text-[#4f4b61] text-[12.5px] font-medium rounded-[5px] h-[36px] px-3">
          + Other
        </button>
        <a href={mapsSearchUrl("police station near me")} target="_blank" rel="noreferrer" className="text-[12.5px] text-[#0d88c7] underline ml-1">
          📍 Look up the nearest police station
        </a>
      </div>

      <button type="button" onClick={save} disabled={saving} className="bg-brand-red disabled:opacity-60 text-white font-bold text-[14px] rounded-[5px] h-[44px] w-full sm:w-[200px]">
        {saving ? "Saving…" : "Save contacts"}
      </button>
    </div>
  );
}
