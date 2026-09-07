import { useBackend } from "../context/BackendContext";

export default function Toasts() {
  const { toasts } = useBackend();
  return (
    <div className="fixed top-4 right-4 z-[999] flex flex-col gap-2 w-[300px] pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`bg-white rounded-lg shadow-lg border-l-4 p-3 text-[12.5px] ${
            t.level === "high" ? "border-brand-red" : "border-amber-400"
          }`}
        >
          <div className="font-bold text-brand-navy mb-0.5">{t.title}</div>
          <div className="text-[#555]">{t.message}</div>
        </div>
      ))}
    </div>
  );
}
