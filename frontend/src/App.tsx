import React, { useEffect, useMemo, useState } from "react";

type Role = "user" | "assistant";

interface Patient {
  id: string;
  name: string;
  lastEncounterAt?: string | null;
}

interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  createdAt: string;
}

interface ChatResponse {
  reply: string;
  triage_level?: string;
  followups?: string;
  warnings?: string;
  is_streaming?: boolean;
}

interface TriageInfo {
  level: string | null;
  notes: string | null;
}

type MessagesByPatient = Record<string, ChatMessage[]>;
type TriageByPatient = Record<string, TriageInfo>;

const App: React.FC = () => {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [patientsError, setPatientsError] = useState<string | null>(null);

  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);

  const [messagesByPatient, setMessagesByPatient] = useState<MessagesByPatient>({});
  const [triageByPatient, setTriageByPatient] = useState<TriageByPatient>({});

  const [searchQuery, setSearchQuery] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const selectedPatient = useMemo(
    () => patients.find((p) => p.id === selectedPatientId) ?? null,
    [patients, selectedPatientId]
  );

  const currentMessages: ChatMessage[] = useMemo(() => {
    if (!selectedPatientId) return [];
    return messagesByPatient[selectedPatientId] ?? [];
  }, [messagesByPatient, selectedPatientId]);

  const currentTriage: TriageInfo | null = useMemo(() => {
    if (!selectedPatientId) return null;
    return triageByPatient[selectedPatientId] ?? null;
  }, [triageByPatient, selectedPatientId]);

  useEffect(() => {
    const fetchPatients = async () => {
      setPatientsLoading(true);
      setPatientsError(null);
      try {
        const res = await fetch("/api/users?limit=20");
        if (!res.ok) throw new Error(`Failed to load users (${res.status})`);
        const data = await res.json();
        const mapped: Patient[] = (data as any[]).map((u) => ({
          id: u.id,
          name: u.name,
          lastEncounterAt: u.last_encounter_at ?? null,
        }));
        setPatients(mapped);
      } catch (err: any) {
        console.error(err);
        setPatientsError(err?.message ?? "Failed to load users.");
      } finally {
        setPatientsLoading(false);
      }
    };

    fetchPatients().catch(console.error);
  }, []);

  const reloadDefaultPatients = async () => {
    setPatientsLoading(true);
    setPatientsError(null);
    try {
      const res = await fetch("/api/users?limit=20");
      if (!res.ok) throw new Error(`Failed to load users (${res.status})`);
      const data = await res.json();
      const mapped: Patient[] = (data as any[]).map((u) => ({
        id: u.id,
        name: u.name,
        lastEncounterAt: u.last_encounter_at ?? null,
      }));
      setPatients(mapped);
    } catch (err: any) {
      console.error(err);
      setPatientsError(err?.message ?? "Failed to load users.");
    } finally {
      setPatientsLoading(false);
    }
  };

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      await reloadDefaultPatients();
      return;
    }

    setSearchLoading(true);
    try {
      const res = await fetch(`/api/users?query=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error(`Search failed (${res.status})`);
      const data = await res.json();
      const mapped: Patient[] = (data as any[]).map((u) => ({
        id: u.id,
        name: u.name,
        lastEncounterAt: u.last_encounter_at ?? null,
      }));
      setPatients(mapped);
    } catch (err: any) {
      console.error(err);
      setPatientsError(err?.message ?? "Search users failed.");
    } finally {
      setSearchLoading(false);
    }
  };

  const handleSelectPatient = async (patient: Patient) => {
    setSelectedPatientId(patient.id);
    setSendError(null);
    if (messagesByPatient[patient.id]) {
      return;
    }
    try {
      const res = await fetch(
        `/api/chat/history?user_id=${encodeURIComponent(patient.id)}`
      );
      if (!res.ok) throw new Error(`Failed to load history (${res.status})`);
      const data = await res.json();
      const mapped: ChatMessage[] = (data as any[]).map((m, index) => ({
        id: m.id ?? `${patient.id}-${index}-${m.role}`,
        role: m.role === "assistant" ? "assistant" : "user",
        content: m.content,
        createdAt: m.created_at ?? new Date().toISOString(),
      }));
      setMessagesByPatient((prev) => ({
        ...prev,
        [patient.id]: mapped,
      }));
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreatePatient = async () => {
    const name = window.prompt("Enter patient name:");
    if (!name || !name.trim()) return;
    try {
      const res = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) throw new Error(`Failed to create user (${res.status})`);
      const u = await res.json();
      const patient: Patient = {
        id: u.id,
        name: u.name,
        lastEncounterAt: u.last_encounter_at ?? null,
      };
      setPatients((prev) => [patient, ...prev]);
      setSelectedPatientId(patient.id);
      setMessagesByPatient((prev) => ({
        ...prev,
        [patient.id]: [],
      }));
      setTriageByPatient((prev) => ({
        ...prev,
        [patient.id]: { level: null, notes: null },
      }));
    } catch (err: any) {
      console.error(err);
      window.alert(err?.message ?? "Failed to create user.");
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedPatientId) return;
    if (!input.trim() || isSending) return;

    const patientId = selectedPatientId;
    const userText = input.trim();
    setInput("");
    setSendError(null);

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: userText,
      createdAt: new Date().toISOString(),
    };

    setMessagesByPatient((prev) => {
      const existing = prev[patientId] ?? [];
      return {
        ...prev,
        [patientId]: [...existing, userMessage],
      };
    });

    // Create an initial empty assistant message for streaming content
    const initialAssistantMessageId = crypto.randomUUID();
    const initialAssistantMessage: ChatMessage = {
      id: initialAssistantMessageId,
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
    };

    setMessagesByPatient((prev) => {
      const existing = prev[patientId] ?? [];
      return {
        ...prev,
        [patientId]: [...existing, initialAssistantMessage],
      };
    });

    try {
      setIsSending(true);

      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: patientId,
          message: userText,
        }),
      });

      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) {
        throw new Error("Streaming is not supported in this browser/environment.");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      let fullReply = "";

      readingLoop: while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const raw of lines) {
          const line = raw.trim();
          if (!line.startsWith("data: ")) continue;

          const dataStr = line.slice(6).trim();

          if (dataStr === "[DONE]") {
            break readingLoop;
          }

          try {
            const data: ChatResponse = JSON.parse(dataStr);

            fullReply = data.reply ?? fullReply;

            // Update the assistant message content as we receive new data
            setMessagesByPatient((prev) => {
              const existing = prev[patientId] ?? [];
              return {
                ...prev,
                [patientId]: existing.map((msg) =>
                  msg.id === initialAssistantMessageId
                    ? { ...msg, content: fullReply || "No reply received from server." }
                    : msg
                ),
              };
            });

            // Build triage notes from followups and warnings
            const triageLevel = data.triage_level ?? null;
            const notesParts: string[] = [];
            if (data.followups) notesParts.push(data.followups);
            if (data.warnings) notesParts.push(data.warnings);
            const triageNotes =
              notesParts.length > 0 ? notesParts.join("\n\n") : null;

            setTriageByPatient((prev) => ({
              ...prev,
              [patientId]: {
                level: triageLevel,
                notes: triageNotes,
              },
            }));

            if (data.is_streaming === false) {
              break readingLoop;
            }
          } catch (e) {
            console.error("Error parsing SSE data:", e, dataStr);
          }
        }
      }
    } catch (err: any) {
      console.error(err);
      setSendError(err?.message ?? "Unknown error");

      const errorMessage: ChatMessage = {
        id: initialAssistantMessageId,
        role: "assistant",
        content: "Sorry, something went wrong while contacting the server.",
        createdAt: new Date().toISOString(),
      };

      setMessagesByPatient((prev) => {
        const existing = prev[patientId] ?? [];
        return {
          ...prev,
          [patientId]: existing.map((msg) =>
            msg.id === initialAssistantMessageId ? errorMessage : msg
          ),
        };
      });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 px-4 py-3 flex items-center justify-between bg-white">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">
            HealthChat – Triage Console
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage multiple patients, review their historical conversations, and
            continue ongoing triage.
          </p>
        </div>
        <span className="text-xs rounded-full border border-emerald-300 px-3 py-1 text-emerald-700 bg-emerald-50">
          Prototype · Not a medical device
        </span>
      </header>

      <main className="flex-1 flex flex-col md:flex-row">
        {/* Sidebar: patients */}
        <aside className="w-full md:w-72 border-b md:border-b-0 md:border-r border-slate-200 flex flex-col bg-blue-50/60">
          <div className="px-3 py-3 border-b border-slate-200 flex items-center gap-2 bg-blue-50">
            <input
              type="text"
              className="flex-1 rounded-lg bg-white border border-slate-300 px-2 py-1 text-xs placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
              placeholder="Search by patient name..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
            />
            <button
              type="button"
              onClick={handleCreatePatient}
              className="px-2 py-1 rounded-lg text-xs bg-emerald-500 hover:bg-emerald-400 text-white transition-colors"
            >
              New
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1 text-sm">
            {patientsLoading && (
              <div className="text-xs text-slate-500 px-1 py-1">
                Loading patients...
              </div>
            )}
            {patientsError && (
              <div className="text-xs text-rose-600 px-1 py-1">
                Error: {patientsError}
              </div>
            )}
            {searchLoading && (
              <div className="text-[10px] text-slate-500 px-1 py-1">
                Searching…
              </div>
            )}

            {patients.length === 0 && !patientsLoading && (
              <div className="text-xs text-slate-500 px-1 py-1">
                No patients yet. Click &quot;New&quot; to create one.
              </div>
            )}

            {patients.map((p) => {
              const isActive = p.id === selectedPatientId;
              const last = p.lastEncounterAt
                ? new Date(p.lastEncounterAt).toLocaleString()
                : "No encounters";
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => handleSelectPatient(p)}
                  className={`w-full text-left px-2 py-2 rounded-lg border text-xs mb-1 transition-colors ${
                    isActive
                      ? "border-sky-400 bg-sky-50"
                      : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-medium truncate text-slate-900">
                      {p.name}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1 truncate">
                    {last}
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        {/* Chat area */}
        <section className="flex-1 flex flex-col border-b md:border-b-0 md:border-r border-slate-200 bg-white">
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {!selectedPatient && (
              <div className="text-sm text-slate-500 mt-4">
                Select a patient on the left or create a new one to start a
                triage session.
              </div>
            )}

            {selectedPatient &&
              currentMessages.map((m) => (
                <div
                  key={m.id}
                  className={`flex ${
                    m.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                      m.role === "user"
                        ? "bg-sky-100 text-slate-900 rounded-br-sm border border-sky-100"
                        : "bg-slate-100 text-slate-900 rounded-bl-sm border border-slate-200"
                    }`}
                  >
                    <div className="text-[10px] uppercase tracking-wide mb-1 opacity-70">
                      {m.role === "user" ? "Patient" : "Assistant"}
                    </div>
                    {m.content}
                  </div>
                </div>
              ))}

            {selectedPatient && isSending && (
              <div className="flex justify-start">
                <div className="max-w-[70%] rounded-2xl px-3 py-2 text-sm bg-slate-100 text-slate-700 border border-slate-200">
                  <div className="text-[10px] uppercase tracking-wide mb-1 opacity-70">
                    Assistant
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="inline-block w-2 h-2 rounded-full bg-slate-400 animate-pulse" />
                    <span>Thinking about this case...</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <form
            onSubmit={handleSubmit}
            className="border-t border-slate-200 px-4 py-3 flex flex-col gap-2 bg-slate-50"
          >
            {sendError && (
              <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 px-2 py-1 rounded">
                Error: {sendError}
              </div>
            )}

            <div className="flex items-end gap-2">
              <textarea
                className="flex-1 resize-none rounded-xl bg-white border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:border-sky-400 min-h-[52px] max-h-[120px]"
                placeholder={
                  selectedPatient
                    ? `Describe ${selectedPatient.name}'s symptoms, onset time, and any key context...`
                    : "Select or create a patient first."
                }
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={2}
                disabled={!selectedPatient || isSending}
              />
              <button
                type="submit"
                disabled={!selectedPatient || isSending || !input.trim()}
                className="inline-flex items-center justify-center px-4 py-2 rounded-xl text-sm font-medium bg-sky-500 hover:bg-sky-400 text-white disabled:bg-slate-300 disabled:text-slate-600 disabled:cursor-not-allowed transition-colors"
              >
                {isSending ? "Sending..." : "Send"}
              </button>
            </div>

            <p className="text-[10px] text-slate-500">
              Do not enter personal identifiers (full name, ID numbers, exact
              address, etc.).
            </p>
          </form>
        </section>

        {/* Side panel */}
        <aside className="w-full md:w-80 border-t md:border-t-0 md:border-l border-slate-200 px-4 py-4 flex flex-col gap-4 bg-slate-50">
          <div>
            <h2 className="text-sm font-semibold mb-2 text-slate-900">
              Triage summary
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  Current assessment
                </span>
                <span
                  className={`text-xs px-2 py-1 rounded-full border ${
                    currentTriage?.level === "urgent"
                      ? "border-rose-300 text-rose-700 bg-rose-50"
                      : currentTriage?.level === "watchful"
                      ? "border-amber-300 text-amber-700 bg-amber-50"
                      : currentTriage?.level === "normal"
                      ? "border-emerald-300 text-emerald-700 bg-emerald-50"
                      : "border-slate-300 text-slate-600 bg-slate-50"
                  }`}
                >
                  {currentTriage?.level
                    ? currentTriage.level.toUpperCase()
                    : "Not available"}
                </span>
              </div>
              <p className="text-xs text-slate-700 whitespace-pre-wrap">
                {currentTriage?.notes ??
                  "Once the assistant responds for a patient, a brief summary of the risk level or follow-up advice can appear here."}
              </p>
            </div>
          </div>

          <div>
            <h2 className="text-sm font-semibold mb-2 text-slate-900">
              Safety notice
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-700 space-y-1">
              <p>
                This assistant is for general information and early triage
                support only. It does not provide a medical diagnosis.
              </p>
              <p>
                If a patient experiences severe symptoms such as chest pain,
                difficulty breathing, confusion, or rapid worsening of their
                condition, they should seek emergency medical care immediately.
              </p>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
};

export default App;
