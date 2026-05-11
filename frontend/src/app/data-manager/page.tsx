"use client";

import DataManagerView from "@/components/Dashboard/DataManagerView";
import ErrorBoundary from "@/components/ErrorBoundary";

export default function Page() {
  return (
    <>
      {/* Hero Section */}
      <section className="relative z-10 overflow-hidden pt-28 pb-10 md:pt-[150px] md:pb-[70px] xl:pt-[180px] xl:pb-[80px] 2xl:pt-[210px] 2xl:pb-[100px] bg-blue-50 dark:bg-[#050505]">
        <div
          className="absolute inset-0 opacity-[0.06] dark:opacity-[0.02] pointer-events-none"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%233b82f6' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
            backgroundRepeat: "repeat",
            backgroundSize: "120px 120px",
          }}
        />

        {/* Floating decorative blobs */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute -top-28 left-1/4 w-80 h-80 bg-blue-300/20 rounded-full filter blur-3xl opacity-60 blob-float-1" />
          <div className="absolute -bottom-24 right-1/4 w-96 h-96 bg-indigo-300/20 rounded-full filter blur-3xl opacity-60 blob-float-2" />
          <div className="absolute top-1/3 left-3/4 w-56 h-56 bg-purple-300/20 rounded-full filter blur-3xl opacity-50 blob-float-3" />
          <div className="absolute bottom-10 left-10 w-72 h-72 bg-cyan-300/20 rounded-full filter blur-3xl opacity-50 blob-float-1" />
        </div>

        <div className="container relative z-10">
          <div className="-mx-4 flex flex-wrap items-center">
            <div className="w-full px-4 text-center">
              <h1
                className="mb-5 text-4xl font-extrabold leading-tight tracking-tight text-black dark:text-white sm:text-5xl md:text-6xl"
                style={{ fontFamily: "'DM Serif Display', serif" }}
              >
                Knowledge <span className="text-primary italic">Hub Agent</span>
              </h1>
              <p
                className="mx-auto mb-6 max-w-[720px] text-lg font-medium text-body-color dark:text-body-color-dark"
                style={{ fontFamily: "'Sora', sans-serif" }}
              >
                Knowledge indexing and vector storage for research data
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="pb-16 md:pb-20 lg:pb-24 bg-gray-50 dark:bg-[#050505] min-h-[50vh]">
        <div className="container">
          <div className="-mx-4 flex flex-wrap">
            <div className="w-full px-4 mx-auto">
              <div className="shadow-sm dark:bg-[#0a0a0f] rounded-xl bg-white border border-gray-200 dark:border-white/10 p-6 sm:p-10 transition-all">
                <ErrorBoundary><DataManagerView /></ErrorBoundary>
              </div>
            </div>
          </div>
        </div>
      </section>

      <style jsx global>{`
        @keyframes float1 {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-24px) scale(1.06); }
        }
        @keyframes float2 {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-18px) scale(1.04); }
        }
        @keyframes float3 {
          0%, 100% { transform: translateY(0px) scale(1); }
          50% { transform: translateY(-12px) scale(1.03); }
        }

        .blob-float-1 { animation: float1 8s ease-in-out infinite; }
        .blob-float-2 { animation: float2 7s ease-in-out 1s infinite; }
        .blob-float-3 { animation: float3 9s ease-in-out 0.5s infinite; }
      `}</style>
    </>
  );
}