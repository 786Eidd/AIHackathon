function timeAgo(iso) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function BreachAlertRow({ name, message, ip, date, createdAt, thumbnail, acknowledged, onTakeAction }) {
  return (
    <div className="bg-white border border-[#d9d9d9] min-h-[111px] flex items-center px-[28px] py-4 gap-10 flex-wrap">
      <div className="flex items-center gap-4 w-[280px]">
        <div className="h-[79px] w-[123px] rounded-[5px] bg-gray-200 overflow-hidden shrink-0">
          {thumbnail && <img src={thumbnail} alt={name} className="w-full h-full object-cover" />}
        </div>
        <div className="flex flex-col gap-0.5">
          <p className="text-brand-navy text-[16px] font-semibold">{name}</p>
          <p className="text-[#6a6888] text-[12px] font-medium">
            {acknowledged ? "Resolved" : `Triggered ${timeAgo(createdAt)}`}
          </p>
          {message && <p className="text-[#a3a1b3] text-[11px] max-w-[240px] truncate">{message}</p>}
        </div>
      </div>

      <div className="flex gap-16 items-center text-[#808080] text-[12px] w-[219px]">
        <p>{ip}</p>
        <p>{date}</p>
      </div>

      <div className="flex gap-5 items-center ml-auto">
        {acknowledged ? (
          <span className="text-[#3c9e62] text-[14px] font-semibold w-[134px] text-center">Resolved</span>
        ) : (
          <button
            onClick={onTakeAction}
            className="bg-brand-red text-white text-[14px] font-semibold rounded-[5px] px-[10px] py-[7px] w-[134px] capitalize"
          >
            Take Action
          </button>
        )}
      </div>
    </div>
  );
}
