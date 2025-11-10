import React, { useState } from "react";

type Role = "user" | "assistant";

interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  createdAt: string;
}

interface ChatResponse {
  reply: string;
  triage_level?: string;
  triage_notes?: string;
}

const App: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triageLevel, setTriageLevel] = useState<string | null>(null);
  const [triageNotes, setTriageNotes] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!input.trim() || isLoading) return;

    const userText = input.trim();
    setInput("");
    setError(null);

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: userText,
      createdAt: new Date().toISOString(),
    };

    // Optimistically append user message
    setMessages((prev) => [...prev, userMessage]);

    try {
      setIsLoading(true);
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: userText }),
      });

      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }

      const data: ChatResponse = await res.json();

      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.reply ?? "No reply received from server.",
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setTriageLevel(data.triage_level ?? null);
      setTriageNotes(data.triage_notes ?? null);
    } catch (err: any) {
      console.error(err);
      setError(err?.message ?? "Unknown error");
      // Append an error-like assistant message for visibility
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "Sorry, something went wrong while contacting the server.",
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-50">
      {/* Header */}
      <header className="border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">HealthChat – Online Triage</h1>
          <p className="text-xs text-slate-400">
            This service provides preliminary health guidance only. It does not replace in-person medical diagnosis.
          </p>
        </div>
        <span className="text-xs rounded-full border border-emerald-500/60 px-3 py-1 text-emerald-300 bg-emerald-950/40">
          Prototype · Not a medical device
        </span>
      </header>

      {/* Main layout */}
      <main className="flex-1 flex flex-col md:flex-row">
        {/* Chat area */}
        <section className="flex-1 flex flex-col border-b md:border-b-0 md:border-r border-slate-800">
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {messages.length === 0 && (
              <div className="text-sm text-slate-400 mt-4">
                Start by describing your symptoms in as much detail as you can. For example:
                <br />
                <span className="italic text-slate-300">
                  “I have had a headache and mild fever for 2 days. No cough, but I feel tired.”
                </span>
              </div>
            )}

            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                    m.role === "user"
                      ? "bg-sky-600 text-slate-50 rounded-br-sm"
                      : "bg-slate-800 text-slate-50 rounded-bl-sm"
                  }`}
                >
                  <div className="text-[10px] uppercase tracking-wide mb-1 opacity-70">
                    {m.role === "user" ? "You" : "Assistant"}
                  </div>
                  {m.content}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="max-w-[70%] rounded-2xl px-3 py-2 text-sm bg-slate-800/80 text-slate-300 border border-slate-700/70">
                  <div className="text-[10px] uppercase tracking-wide mb-1 opacity-70">
                    Assistant
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="inline-block w-2 h-2 rounded-full bg-slate-400 animate-pulse" />
                    <span>Thinking about your case...</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input area */}
          <form
            onSubmit={handleSubmit}
            className="border-t border-slate-800 px-4 py-3 flex flex-col gap-2 bg-slate-950/80 backdrop-blur"
          >
            {error && (
              <div className="text-xs text-rose-400 bg-rose-950/40 border border-rose-700/60 px-2 py-1 rounded">
                Error: {error}
              </div>
            )}

            <div className="flex items-end gap-2">
              <textarea
                className="flex-1 resize-none rounded-xl bg-slate-900 border border-slate-700/70 px-3 py-2 text-sm text-slate-50 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 min-h-[52px] max-h-[120px]"
                placeholder="Describe your symptoms, when they started, and anything that makes them better or worse..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={2}
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="inline-flex items-center justify-center px-4 py-2 rounded-xl text-sm font-medium bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-slate-400 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? "Sending..." : "Send"}
              </button>
            </div>

            <p className="text-[10px] text-slate-500">
              Do not enter personal identifiers (full name, ID numbers, exact address, etc.).
            </p>
          </form>
        </section>

        {/* Side panel: triage summary + safety note */}
        <aside className="w-full md:w-80 border-t md:border-t-0 md:border-l border-slate-800 px-4 py-4 flex flex-col gap-4 bg-slate-950/90">
          <div>
            <h2 className="text-sm font-semibold mb-2">Triage summary</h2>
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-3 text-sm space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Current assessment</span>
                <span
                  className={`text-xs px-2 py-1 rounded-full border ${
                    triageLevel === "urgent"
                      ? "border-rose-500/70 text-rose-300 bg-rose-950/50"
                      : triageLevel === "watchful"
                      ? "border-amber-500/70 text-amber-300 bg-amber-950/50"
                      : triageLevel === "normal"
                      ? "border-emerald-500/70 text-emerald-300 bg-emerald-950/40"
                      : "border-slate-600 text-slate-300 bg-slate-900"
                  }`}
                >
                  {triageLevel ? triageLevel.toUpperCase() : "Not available yet"}
                </span>
              </div>
              <p className="text-xs text-slate-300 whitespace-pre-wrap">
                {triageNotes ?? "Once the assistant responds, a brief summary of the risk level or follow-up advice can appear here."}
              </p>
            </div>
          </div>

          <div>
            <h2 className="text-sm font-semibold mb-2">Safety notice</h2>
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-3 text-xs text-slate-300 space-y-1">
              <p>
                This assistant is for general information and early triage support only. It does not provide a medical diagnosis.
              </p>
              <p>
                If you experience severe symptoms such as chest pain, difficulty breathing, confusion, or rapid worsening of your condition, you should seek emergency medical care immediately.
              </p>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
};

export default App;
