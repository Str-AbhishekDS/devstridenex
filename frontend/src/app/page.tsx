"use client";

import React, { useEffect, useState } from "react";
import PsychometricTestModal from "@/components/PsychometricTestModal";
import { psychometricApi, OnboardingStatusResponse } from "@/services/psychometricApi";

export default function Home() {
  const [status, setStatus] = useState<OnboardingStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [showTestModal, setShowTestModal] = useState<boolean>(false);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const res = await psychometricApi.checkOnboardingStatus();
      setStatus(res);

      // 🔴 If fresh student (not onboarded), open the test modal popup automatically!
      if (!res.is_onboarded) {
        setShowTestModal(true);
      }
    } catch (err) {
      console.error("Failed to check student onboarding status", err);
    } finally {
      setLoading(false);
    }
  };

  const handleTestCompleted = () => {
    setShowTestModal(false);
    // Refresh status to load completed results
    fetchStatus();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* Top Navbar */}
      <header className="w-full border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center font-black text-white text-lg shadow-lg shadow-indigo-500/25">
              N
            </div>
            <span className="font-bold text-lg tracking-tight text-white">NexEdu StrideNex</span>
          </div>

          <div className="flex items-center gap-4">
            {loading ? (
              <div className="h-4 w-24 bg-slate-800 rounded animate-pulse"></div>
            ) : status?.is_onboarded ? (
              <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                Onboarding Completed
              </span>
            ) : (
              <button
                onClick={() => setShowTestModal(true)}
                className="px-3.5 py-1.5 rounded-xl bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold hover:bg-indigo-500/30 transition-all flex items-center gap-1.5"
              >
                <span>🧠</span> Take Onboarding Test
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Dashboard Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-10 space-y-8">
        
        {/* Welcome Hero Banner */}
        <section className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-900/40 via-purple-900/30 to-slate-900 border border-indigo-500/20 p-8 md:p-12 shadow-2xl">
          <div className="relative z-10 max-w-2xl space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold">
              🎓 Student Intelligence Portal
            </div>
            <h1 className="text-3xl md:text-5xl font-black text-white tracking-tight leading-tight">
              Welcome to StrideNex
            </h1>
            <p className="text-slate-300 text-sm md:text-base leading-relaxed">
              Your personalized career pathways, habit analytics, and AI psychometric trait assessments in one centralized dashboard.
            </p>

            {/* CTA Actions */}
            {!loading && !status?.is_onboarded && (
              <div className="pt-4 flex items-center gap-4">
                <button
                  onClick={() => setShowTestModal(true)}
                  className="px-6 py-3 rounded-2xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-bold text-sm shadow-xl shadow-indigo-500/25 hover:from-indigo-600 hover:to-purple-700 active:scale-95 transition-all flex items-center gap-2"
                >
                  <span>🚀</span> Complete Psychometric Onboarding
                </button>
              </div>
            )}
          </div>
        </section>

        {/* Status & Personality Overview Cards */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Psychometric Test Status */}
          <div className="rounded-3xl bg-slate-900/80 border border-slate-800 p-6 flex flex-col justify-between space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <span className="text-2xl">🧠</span>
              <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${
                status?.is_onboarded
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/30"
              }`}>
                {status?.is_onboarded ? "Completed" : "Pending"}
              </span>
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Psychometric Evaluation</h3>
              <p className="text-xs text-slate-400 mt-1">
                {status?.is_onboarded
                  ? "Your personality profile is active and powering your career recommendations."
                  : "Take the mandatory 1-time onboarding test to unlock personalized recommendations."}
              </p>
            </div>
            {status?.is_onboarded ? (
              <div className="text-xs text-slate-500 border-t border-slate-800 pt-3">
                Completed on: {status.submission?.creation || "Active"}
              </div>
            ) : (
              <button
                onClick={() => setShowTestModal(true)}
                className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-colors"
              >
                Start Assessment Now
              </button>
            )}
          </div>

          {/* Card 2: Orientation Breakdown */}
          <div className="rounded-3xl bg-slate-900/80 border border-slate-800 p-6 flex flex-col justify-between space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <span className="text-2xl">🎯</span>
              <span className="text-xs text-slate-400 font-mono">Score Breakdown</span>
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Career Orientation</h3>
              <p className="text-xs text-slate-400 mt-1">
                {status?.submission
                  ? `Assessed Score: ${status.submission.score} (${status.submission.percentage}%)`
                  : "Evaluates Job, Startup, and Higher Education suitability based on Big Five traits."}
              </p>
            </div>
            <div className="flex items-center gap-2 pt-2">
              <span className="px-3 py-1 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-medium">
                💼 Job
              </span>
              <span className="px-3 py-1 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-medium">
                🚀 Startup
              </span>
              <span className="px-3 py-1 rounded-xl bg-pink-500/10 border border-pink-500/20 text-pink-300 text-xs font-medium">
                🎓 Higher Ed
              </span>
            </div>
          </div>

          {/* Card 3: Habit & Pathways Integration */}
          <div className="rounded-3xl bg-slate-900/80 border border-slate-800 p-6 flex flex-col justify-between space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <span className="text-2xl">⚡</span>
              <span className="text-xs text-emerald-400 font-medium">AI Sync Active</span>
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Habit & Career Pathways</h3>
              <p className="text-xs text-slate-400 mt-1">
                Personalized 30-day daily habit plans automatically tailored to your psychometric results.
              </p>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div className="bg-emerald-400 h-full w-3/4"></div>
            </div>
          </div>
        </section>
      </main>

      {/* Onboarding Psychometric Test Modal Popup */}
      <PsychometricTestModal
        isOpen={showTestModal}
        onClose={() => setShowTestModal(false)}
        onCompleted={handleTestCompleted}
      />
    </div>
  );
}
