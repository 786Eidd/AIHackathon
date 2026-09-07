import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { useBackend } from "../context/BackendContext";

function parseRtsp(url) {
  // rtsp://user:pass@host:port/path — best-effort parse for the edit form.
  try {
    const u = new URL((url || "").replace(/^rtsp/, "http"));
    return { ip: u.hostname, port: u.port || "554", user: u.username || "", pass: u.password || "", path: u.pathname || "/" };
  } catch (e) {
    return { ip: "", port: "554", user: "", pass: "", path: "/" };
  }
}

const emptyForm = { name: "", location: "", ip: "", port: "554", user: "", pass: "", path: "/Streaming/Channels/101" };

export default function CameraManagement() {
  const { cameras, createCamera, updateCamera, deleteCamera, cameraAction, pushToast } = useBackend();
  const list = Object.values(cameras);

  const [tab, setTab] = useState("list");
  const [selectAll, setSelectAll] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);

  useEffect(() => {
    setSelectAll(list.length > 0 && selected.size === list.length);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, list.length]);

  function toggleAll() {
    if (selectAll) setSelected(new Set());
    else setSelected(new Set(list.map((c) => c.camera_id)));
    setSelectAll(!selectAll);
  }

  function toggleOne(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function startAdd() {
    setEditingId(null);
    setForm(emptyForm);
    setTab("config");
  }

  function startEdit(cam) {
    const parsed = parseRtsp(cam.rtsp_url);
    setEditingId(cam.camera_id);
    setForm({ name: cam.name || "", location: cam.location || "", ...parsed });
    setTab("config");
  }

  async function handleModify() {
    if (selected.size !== 1) {
      pushToast("Select one camera", "Modify works on exactly one camera at a time.", "medium");
      return;
    }
    const id = [...selected][0];
    const cam = cameras[id];
    if (cam) startEdit(cam);
  }

  async function handleBulkDelete() {
    if (selected.size === 0) return;
    if (!window.confirm(`Delete ${selected.size} camera(s)? Their historical events/alerts are kept.`)) return;
    for (const id of selected) {
      try {
        await deleteCamera(id);
      } catch (e) {
        pushToast("Delete failed", `${cameras[id]?.name || id}: ${e.message}`, "medium");
      }
    }
    setSelected(new Set());
  }

  async function handleSave(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.ip.trim()) {
      pushToast("Missing fields", "Name and IP are required.", "medium");
      return;
    }
    const auth = form.user ? `${form.user}:${form.pass}@` : "";
    const rtsp_url = `rtsp://${auth}${form.ip}:${form.port || "554"}${form.path.startsWith("/") ? form.path : "/" + form.path}`;

    try {
      if (editingId) {
        await updateCamera(editingId, { name: form.name, location: form.location || null, rtsp_url });
        pushToast("Camera updated", form.name, "medium");
      } else {
        await createCamera({ name: form.name, location: form.location || null, rtsp_url, enabled: true });
        pushToast("Camera added", form.name, "medium");
      }
      setForm(emptyForm);
      setEditingId(null);
      setTab("list");
    } catch (e) {
      pushToast("Save failed", e.message, "medium");
    }
  }

  function hostOf(url) {
    try {
      return new URL((url || "").replace(/^rtsp/, "http")).host;
    } catch (e) {
      return url || "—";
    }
  }

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-[71px] border-b border-[#e4e4e4] pb-2.5">
          <button
            type="button"
            onClick={() => setTab("list")}
            className={`text-[16px] tracking-[0.2px] pb-1 border-b-4 -mb-[13px] ${
              tab === "list" ? "text-brand-navy font-medium border-brand-navy" : "text-[#4f4b61]/50 border-transparent"
            }`}
          >
            Camera's List
          </button>
          <button
            type="button"
            onClick={() => setTab("config")}
            className={`text-[16px] tracking-[0.2px] pb-1 border-b-4 -mb-[13px] ${
              tab === "config" ? "text-brand-navy font-medium border-brand-navy" : "text-[#4f4b61]/50 border-transparent"
            }`}
          >
            Camera configuration
          </button>
        </div>

        {tab === "list" ? (
          <>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <label className="flex items-center gap-2.5 text-[#5d5959] text-[14px] cursor-pointer">
                <input type="checkbox" checked={selectAll} onChange={toggleAll} className="size-[15px] rounded-[3px] border border-[#dbdbdb]" />
                Select All
              </label>
              <div className="flex gap-[15px]">
                <button onClick={startAdd} className="border border-[#dbdbdb] rounded-[5px] h-[31px] px-4 text-[#808080] text-[12px] font-medium">
                  Quick Add
                </button>
                <button onClick={handleModify} className="border border-[#dbdbdb] rounded-[5px] h-[31px] px-4 text-[#808080] text-[12px] font-medium">
                  Modify
                </button>
                <button onClick={handleBulkDelete} className="border border-[#dbdbdb] rounded-[5px] h-[31px] px-4 text-brand-red text-[12px] font-medium">
                  Delete
                </button>
              </div>
            </div>

            <div className="border border-[#d1d1d1] rounded-t-[5px] overflow-x-auto">
              <table className="w-full text-[12px] text-center border-collapse">
                <thead>
                  <tr className="bg-[#f2f2f2] text-[#605b5b]">
                    <th className="border border-[#f8f8f8] w-[44px]" />
                    <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Name</th>
                    <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Host</th>
                    <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Sample FPS</th>
                    <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Status</th>
                    <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Location</th>
                    <th className="border border-[#f8f8f8] h-[48px] font-medium px-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {list.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-10 text-[#9c9c9c]">
                        No cameras yet — use Quick Add.
                      </td>
                    </tr>
                  )}
                  {list.map((cam) => (
                    <tr key={cam.camera_id} className="text-[#808080]">
                      <td className="border border-[#e4e4e4] h-[50px]">
                        <input
                          type="checkbox"
                          checked={selected.has(cam.camera_id)}
                          onChange={() => toggleOne(cam.camera_id)}
                          className="size-5 rounded-[3px] border border-[#d5d5d5] mx-auto block"
                        />
                      </td>
                      <td className="border border-[#e4e4e4] font-medium text-[#221f54]">{cam.name}</td>
                      <td className="border border-[#e4e4e4]">{hostOf(cam.rtsp_url)}</td>
                      <td className="border border-[#e4e4e4]">{cam.sample_fps ?? "—"}</td>
                      <td className={`border border-[#e4e4e4] ${(cam.status || "").toLowerCase() === "online" ? "text-[#3c9e62]" : "text-brand-red"}`}>
                        {cam.status}
                      </td>
                      <td className="border border-[#e4e4e4] text-[#838386]">{cam.location || "—"}</td>
                      <td className="border border-[#e4e4e4]">
                        <div className="flex gap-2 justify-center">
                          <button className="text-[#0d88c7] underline" onClick={() => cameraAction(cam.camera_id, "restart")}>
                            Restart
                          </button>
                          <button className="text-brand-red underline" onClick={() => startEdit(cam)}>
                            Edit
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <form onSubmit={handleSave} className="flex flex-col gap-6 max-w-[760px]">
            <p className="text-brand-navy text-[16px] font-semibold">{editingId ? "Edit camera" : "Add a camera"}</p>
            <div className="grid grid-cols-2 gap-x-[18px] gap-y-[18px]">
              <Field label="Name" value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} placeholder="Enter name" />
              <Field label="Location" value={form.location} onChange={(v) => setForm((f) => ({ ...f, location: v }))} placeholder="lab room e.g" />
              <Field label="IP" value={form.ip} onChange={(v) => setForm((f) => ({ ...f, ip: v }))} placeholder="192.168.2.1 e.g" />
              <Field label="Port" value={form.port} onChange={(v) => setForm((f) => ({ ...f, port: v }))} placeholder="554 e.g" />
              <Field label="Username" value={form.user} onChange={(v) => setForm((f) => ({ ...f, user: v }))} placeholder="Enter username" />
              <Field label="Password" type="password" value={form.pass} onChange={(v) => setForm((f) => ({ ...f, pass: v }))} placeholder="Enter password" />
              <div className="flex flex-col gap-3 col-span-2">
                <label className="text-brand-navy text-[16px] font-medium">Stream path</label>
                <div className="bg-brand-field border border-brand-border rounded-[5px] h-[52px] flex items-center px-5">
                  <input
                    value={form.path}
                    onChange={(e) => setForm((f) => ({ ...f, path: e.target.value }))}
                    placeholder="/Streaming/Channels/101"
                    className="bg-transparent outline-none flex-1 text-[14px] placeholder:text-[#c6c6c6]"
                  />
                </div>
              </div>
            </div>
            <p className="text-[11.5px] text-brand-gray">
              Builds <code className="bg-[#f2f2f2] px-1 rounded">
                rtsp://{form.user || "user"}:{form.pass ? "•••" : "pass"}@{form.ip || "ip"}:{form.port || "554"}
                {form.path || "/Streaming/Channels/101"}
              </code>
            </p>
            <div className="flex gap-4">
              <button type="submit" className="bg-brand-red text-white font-bold text-[16px] rounded-[5px] h-[52px] w-[200px]">
                Save
              </button>
              {editingId && (
                <button
                  type="button"
                  onClick={() => {
                    setEditingId(null);
                    setForm(emptyForm);
                  }}
                  className="border border-brand-navy text-brand-navy font-medium text-[14px] rounded-[5px] h-[52px] w-[160px]"
                >
                  Cancel edit
                </button>
              )}
            </div>
          </form>
        )}
      </div>
    </DashboardLayout>
  );
}

function Field({ label, value, onChange, placeholder, type = "text" }) {
  return (
    <div className="flex flex-col gap-3">
      <label className="text-brand-navy text-[16px] font-medium">{label}</label>
      <div className="bg-brand-field border border-brand-border rounded-[5px] h-[52px] flex items-center px-5">
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="bg-transparent outline-none flex-1 text-[14px] placeholder:text-[#c6c6c6]"
        />
      </div>
    </div>
  );
}
