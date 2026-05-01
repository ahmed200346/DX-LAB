"use client";

import { useState, useRef } from "react";
import { toPng } from "html-to-image";
import jsPDF from "jspdf";
import Breadcrumb from "@/components/Common/Breadcrumb";
import TargetDashboard from "@/components/Dashboard/TargetDashboard";

export default function AgentPage() {
  const [prompt, setPrompt] = useState("");
  const [resultHtml, setResultHtml] = useState("");
  const [loading, setLoading] = useState(false);
  const [targets, setTargets] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [sourceCount, setSourceCount] = useState(0);
  const [validationScore, setValidationScore] = useState(0);
  const [fullResponse, setFullResponse] = useState<any>(null);
  const [showJson, setShowJson] = useState(false);
  const [viewMode, setViewMode] = useState<"report" | "dashboard">("report");

  // Assistant pop-up state
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [inputQuestion, setInputQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);

  const reportRef = useRef<HTMLDivElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) {
      setResultHtml("<p class='text-red-500'>⚠️ Please enter a query first.</p>");
      return;
    }

    setLoading(true);
    setResultHtml("");
    setFullResponse(null);
    setShowJson(false);
    setTargets([]);
    setSources([]);
    setSourceCount(0);
    setValidationScore(0);
    setViewMode("report");
    // Reset assistant when new query is run
    setMessages([]);
    setIsAssistantOpen(false);

    try {
      const response = await fetch("http://localhost:8000/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt.trim(),
          top_k: 10,
          data_types: ["text", "pdf"],
          intent: "refresh",
        }),
      });
      const data = await response.json();

      if (data.success) {
        setResultHtml(data.result);
        setTargets(data.targets || []);
        setSources(data.sources || []);
        setSourceCount(data.source_count);
        setValidationScore(data.validation_score);
        setFullResponse(data);
      } else {
        setResultHtml(`<p class='text-red-500'>❌ Error: ${data.error}</p>`);
        setFullResponse(data);
      }
    } catch (err) {
      console.error(err);
      setResultHtml(
        "<p class='text-red-500'>❌ Cannot connect to the agent server. Make sure it's running on port 8000.</p>"
      );
    } finally {
      setLoading(false);
    }
  };

  const downloadPDF = async () => {
    if (!reportRef.current) return;
    const element = reportRef.current;
    try {
      const dataUrl = await toPng(element, {
        quality: 1,
        pixelRatio: 2,
        cacheBust: true,
      });
      const pdf = new jsPDF({
        unit: "mm",
        format: "a4",
        orientation: "portrait",
      });
      const imgProps = pdf.getImageProperties(dataUrl);
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
      let heightLeft = pdfHeight;
      let position = 0;

      pdf.addImage(dataUrl, "PNG", 0, position, pdfWidth, pdfHeight);
      heightLeft -= pdf.internal.pageSize.getHeight();

      while (heightLeft > 0) {
        position = heightLeft - pdfHeight;
        pdf.addPage();
        pdf.addImage(dataUrl, "PNG", 0, position, pdfWidth, pdfHeight);
        heightLeft -= pdf.internal.pageSize.getHeight();
      }
      pdf.save(`target_report_${new Date().toISOString().slice(0, 19)}.pdf`);
    } catch (err) {
      console.error("PDF generation failed:", err);
    }
  };

  const sendQuestion = async () => {
    const sessionId = fullResponse?.session_id;
    if (!inputQuestion.trim() || !sessionId) return;
    const userMsg = inputQuestion.trim();
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setInputQuestion("");
    setIsAsking(true);

    try {
      const res = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, question: userMsg }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, an error occurred while contacting the assistant." },
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <>
      {/* Modern Header for Agent Page */}
      <section className="relative z-10 overflow-hidden pt-28 pb-8 md:pt-[150px] md:pb-[60px] xl:pt-[180px] xl:pb-[80px] 2xl:pt-[210px] 2xl:pb-[100px] bg-blue-50">
        <div className="container">
          <div className="-mx-4 flex flex-wrap items-center">
            <div className="w-full px-4 text-center">
              <h1 className="mb-5 text-3xl font-extrabold leading-tight text-black dark:text-white sm:text-4xl sm:leading-tight md:text-5xl md:leading-tight">
                Intelligent Target <span className="text-primary">Discovery</span>
              </h1>
              <p className="mx-auto mb-6 max-w-[600px] text-base font-medium text-body-color">
                Ask about drug targets, genes, and diseases. Our multi-agent AI searches PubMed, extracts validated targets, and returns structured clinical insights.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Main Agent Interface */}
      <section className="pb-16 md:pb-20 lg:pb-24 bg-blue-50">
        <div className="container">
          <div className="-mx-4 flex flex-wrap">
            <div className="w-full px-4 lg:w-10/12 xl:w-8/12 mx-auto">
              <div className="shadow-three dark:bg-gray-dark rounded-xl bg-white border border-gray-100 px-8 py-10 sm:p-12 dark:shadow-none transition-all hover:shadow-lg">
                <form onSubmit={handleSubmit}>
                  <div className="mb-8">
                    <label
                      htmlFor="prompt"
                      className="mb-4 flex items-center text-sm font-semibold text-black dark:text-white"
                    >
                      <span className="mr-2 text-xl">💬</span> What would you like to discover?
                    </label>
                    <textarea
                      id="prompt"
                      rows={4}
                      className="border-stroke dark:text-body-color-dark dark:shadow-two text-body-color focus:border-primary focus:ring-4 focus:ring-primary/20 dark:focus:border-primary w-full rounded-lg border bg-[#f8f8f8] px-6 py-5 text-lg outline-none transition-all duration-300 dark:border-transparent dark:bg-[#2C303B] shadow-sm resize-y"
                      placeholder="e.g., Identify novel targets for triple‑negative breast cancer, or What are the mechanisms of KRAS G12C inhibitor resistance?"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                    />
                  </div>
                  <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
                    <button
                      type="submit"
                      disabled={loading}
                      className="shadow-submit dark:shadow-submit-dark rounded-full bg-primary px-10 py-4 text-lg font-bold text-white transition-all duration-300 ease-in-out hover:bg-blue-600 hover:shadow-lg disabled:opacity-50 flex items-center gap-2"
                    >
                      {loading ? (
                        <>
                          <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          Discovering...
                        </>
                      ) : (
                        <>✨ Start Discovery Agent</>
                      )}
                    </button>
                    {sourceCount > 0 && (
                      <span className="text-sm text-body-color dark:text-body-color-dark">
                        {sourceCount} unique sources • SGV: {validationScore.toFixed(3)}
                      </span>
                    )}
                  </div>
                </form>

                {resultHtml && (
                  <div className="mt-10 rounded-sm border border-stroke bg-gray-50 p-6 dark:border-transparent dark:bg-gray-800">
                    <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                      <div className="flex gap-4">
                        <button
                          onClick={() => setViewMode("report")}
                          className={`px-3 py-1 rounded-sm text-sm font-medium ${
                            viewMode === "report"
                              ? "bg-primary text-white"
                              : "bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200"
                          }`}
                        >
                          📄 Report
                        </button>
                        <button
                          onClick={() => setViewMode("dashboard")}
                          className={`px-3 py-1 rounded-sm text-sm font-medium ${
                            viewMode === "dashboard"
                              ? "bg-primary text-white"
                              : "bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200"
                          }`}
                        >
                          📊 Dashboard
                        </button>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={downloadPDF}
                          className="rounded-sm bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
                        >
                          📄 Download PDF
                        </button>
                        {fullResponse && (
                          <button
                            onClick={() => setShowJson(!showJson)}
                            className="rounded-sm bg-gray-200 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-200"
                          >
                            {showJson ? "Hide JSON" : "Show JSON"}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Content to be captured for PDF */}
                    <div ref={reportRef}>
                      {viewMode === "report" && (
                        <div dangerouslySetInnerHTML={{ __html: resultHtml }} />
                      )}
                      {viewMode === "dashboard" && targets.length > 0 && (
                        <TargetDashboard targets={targets} />
                      )}
                      {viewMode === "dashboard" && targets.length === 0 && (
                        <div className="text-center py-12 text-gray-500">
                          No targets extracted. Try a different query or ensure
                          the agent returns targets.
                        </div>
                      )}
                    </div>

                    {/* JSON viewer (not included in PDF) */}
                    {showJson && fullResponse && (
                      <div className="mt-6">
                        <h4 className="font-semibold text-black dark:text-white mb-2">
                          📄 Full JSON Response
                        </h4>
                        <pre className="overflow-auto rounded-sm bg-gray-100 p-4 text-xs text-gray-800 dark:bg-gray-900 dark:text-gray-200 max-h-96">
                          {JSON.stringify(fullResponse, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Floating Assistant Button */}
      {fullResponse && fullResponse.session_id && (
        <button
          onClick={() => setIsAssistantOpen(true)}
          className="fixed bottom-6 right-6 z-50 rounded-full bg-primary p-3 text-white shadow-lg hover:bg-primary/90 focus:outline-none"
        >
          <span className="text-2xl">💬</span>
        </button>
      )}

      {/* Assistant Modal */}
      {isAssistantOpen && fullResponse?.session_id && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="flex h-[500px] w-full max-w-md flex-col rounded-lg bg-white shadow-xl dark:bg-gray-800">
            {/* Header */}
            <div className="flex items-center justify-between border-b p-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🤖 AI Assistant
              </h3>
              <button
                onClick={() => setIsAssistantOpen(false)}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                <span className="text-xl">❌</span>
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.length === 0 && (
                <p className="text-center text-sm text-gray-500 dark:text-gray-400">
                  Ask me anything about the retrieved documents or targets!
                </p>
              )}
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-2 ${
                      msg.role === "user"
                        ? "bg-primary text-white"
                        : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200"
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {isAsking && (
                <div className="flex justify-start">
                  <div className="rounded-lg bg-gray-100 px-4 py-2 text-gray-500 dark:bg-gray-700">
                    Thinking...
                  </div>
                </div>
              )}
            </div>

            {/* Input area */}
            <div className="border-t p-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={inputQuestion}
                  onChange={(e) => setInputQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendQuestion()}
                  placeholder="Ask a question..."
                  className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                />
                <button
                  onClick={sendQuestion}
                  disabled={isAsking}
                  className="rounded bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}