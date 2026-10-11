// What an operator should do for each kind of alert, and which contacts
// matter for it. Kept in one place so the wording is easy to review.

const WEAPON = {
  severity: "high",
  headline: "Possible weapon on camera — treat as an emergency",
  steps: [
    "Do not approach or confront the person.",
    "Call the police now and give them the site address and camera location.",
    "Move staff and visitors away from that area and lock doors if it is safe to do so.",
    "Keep the live camera open and tell the police what you see until they arrive.",
    "Do not delete the recording — it is saved with this alert as evidence.",
  ],
  contactKinds: ["police", "rescue", "security"],
};

const POSSIBLE_WEAPON = {
  severity: "medium",
  headline: "An object that could be used as a weapon",
  steps: [
    "Open the live camera and see who has it and what they are doing with it.",
    "If it is ordinary use (sport, craft, kitchen, work), no action is needed — mark this as resolved.",
    "If the person is unknown, threatening someone or trying to get in, send the guard and call the police.",
  ],
  contactKinds: ["security", "police"],
};

const UNKNOWN_PERSON = {
  severity: "medium",
  headline: "Someone the system does not recognise",
  steps: [
    "Open the live camera and check who it is.",
    "If they are staff, family or an expected visitor, add them under Face Management so they stop raising alerts.",
    "If they should not be there, send the on-site guard to check, or speak to them over the intercom.",
    "If they refuse to leave, are trying doors or windows, or you feel unsafe, call the police.",
  ],
  contactKinds: ["security", "police"],
};

const SUSPICIOUS = {
  severity: "high",
  headline: "The scene looks unsafe",
  steps: [
    "Open the live camera and confirm what is happening.",
    "Send the on-site guard if it is safe to do so.",
    "Call the police if there is violence, a break-in or a visible weapon. Call rescue if anyone is hurt.",
  ],
  contactKinds: ["security", "police", "rescue", "ambulance"],
};

const PANIC = {
  severity: "high",
  headline: "Panic alarm raised — emergency at the site",
  steps: [
    "Call the police now and give them the site address.",
    "If anyone is hurt, call rescue as well.",
    "Get people to a safe place and lock doors if it is safe to do so.",
    "Keep this dashboard open: every camera has been switched on and is recording.",
    "Mark this as resolved only once the emergency is over.",
  ],
  contactKinds: ["police", "rescue", "security", "ambulance", "fire"],
};

const GENERIC = {
  severity: "medium",
  headline: "Review this alert",
  steps: ["Open the live camera and check the scene.", "Contact the on-site guard or the police if anything looks wrong."],
  contactKinds: ["security", "police"],
};

export function responsePlan(alert) {
  const type = (alert?.title || "").toLowerCase();

  if (type === "panic_alarm") return PANIC;
  if (type === "unknown_face_detected") return UNKNOWN_PERSON;
  if (type === "suspicious_scene") return SUSPICIOUS;
  if (type.includes("bat") || type.includes("scissors")) return POSSIBLE_WEAPON;
  // firearm_detected, knife_detected, armed_unknown_person, …
  if (type.includes("armed") || type.includes("firearm") || type.includes("knife") || type.includes("weapon")) return WEAPON;

  return (alert?.priority || "").toUpperCase() === "HIGH" ? SUSPICIOUS : GENERIC;
}

// Contacts relevant to the plan first, in the plan's order, then the rest.
export function orderContacts(contacts, plan) {
  const rank = (c) => {
    const index = plan.contactKinds.indexOf(c.kind);
    return index === -1 ? plan.contactKinds.length : index;
  };
  return [...(contacts || [])].sort((a, b) => rank(a) - rank(b));
}

export function mapsSearchUrl(query) {
  return `https://www.google.com/maps/search/${encodeURIComponent(query)}`;
}

export const CONTACT_KINDS = [
  { value: "police", label: "Police" },
  { value: "security", label: "Site security / guard" },
  { value: "rescue", label: "Rescue" },
  { value: "fire", label: "Fire" },
  { value: "ambulance", label: "Ambulance" },
  { value: "other", label: "Other" },
];
