import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";

function load() {
  try {
    return JSON.parse(localStorage.getItem("nexgen_complaints") || "[]");
  } catch (e) {
    return [];
  }
}
function save(list) {
  localStorage.setItem("nexgen_complaints", JSON.stringify(list));
}

export default function Contact() {
  const [complaints, setComplaints] = useState(load);
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");

  useEffect(() => save(complaints), [complaints]);

  const filtered = complaints.filter((c) => {
    if (filter === "In-progress" && c.status !== "In-progress") return false;
    if (filter === "Resolved" && c.status !== "Resolved") return false;
    return c.detail.toLowerCase().includes(search.toLowerCase());
  });

  function createComplaint() {
    const detail = window.prompt("Describe the issue:");
    if (!detail) return;
    setComplaints((prev) => [
      { id: String(Date.now()).slice(-5), detail, createdBy: "1", date: new Date().toLocaleDateString(), status: "In-progress" },
      ...prev,
    ]);
  }
  function resolve(id) {
    setComplaints((prev) => prev.map((c) => (c.id === id ? { ...c, status: "Resolved" } : c)));
  }

  return (
    <DashboardLayout title="Complaint list" actionLabel="Create new complaint" onAction={createComplaint}>
      <div className="bg-[#fff8e6] border border-[#f0dcae] text-[#8a6416] text-[12px] rounded-[6px] px-4 py-2.5 mb-4 leading-relaxed">
        There's no complaint/ticketing API on this backend, so this list lives in your browser only (localStorage) —
        it won't sync anywhere else or across devices.
      </div>

      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <label className="flex items-center gap-2.5 text-[#5d5959] text-[14px] cursor-pointer">
          <input type="checkbox" className="size-[15px] rounded-[3px] border border-[#dbdbdb]" />
          Select All
        </label>

        <div className="flex items-center gap-3">
          <div className="border border-black/[0.06] rounded-[5px] h-[38px] flex items-center gap-2 px-4 w-[220px]">
            <span className="text-[#726f70]/50 text-[12px]">🔍</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search"
              className="bg-transparent outline-none flex-1 text-[12px] placeholder:text-[#726f70]/50"
            />
          </div>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="border border-black/10 rounded-[5px] h-[38px] px-4 text-[#645b5b] text-[14px] bg-transparent"
          >
            <option>All</option>
            <option>In-progress</option>
            <option>Resolved</option>
          </select>
        </div>
      </div>

      <div className="border border-[#d1d1d1] rounded-t-[5px] overflow-x-auto">
        <table className="w-full text-[12px] text-center border-collapse">
          <thead>
            <tr className="bg-[#f2f2f2] text-[#605b5b]">
              <th className="border border-[#f8f8f8] w-[44px]" />
              <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">ID</th>
              <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Detail</th>
              <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Request date</th>
              <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Status</th>
              <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="py-10 text-[#9c9c9c]">
                  No complaints yet.
                </td>
              </tr>
            )}
            {filtered.map((c) => (
              <tr key={c.id} className="text-[#808080]">
                <td className="border border-[#e4e4e4] h-[50px]">
                  <input type="checkbox" className="size-5 rounded-[3px] border border-[#d5d5d5] mx-auto block" />
                </td>
                <td className="border border-[#e4e4e4]">{c.id}</td>
                <td className="border border-[#e4e4e4]">{c.detail}</td>
                <td className="border border-[#e4e4e4]">{c.date}</td>
                <td className={`border border-[#e4e4e4] ${c.status === "Resolved" ? "text-[#3c9e62]" : "text-[#e9513d]"}`}>{c.status}</td>
                <td className="border border-[#e4e4e4]">
                  {c.status !== "Resolved" && (
                    <button className="text-[#0d88c7] underline" onClick={() => resolve(c.id)}>
                      Mark resolved
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DashboardLayout>
  );
}
