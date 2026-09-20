"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { psychometricApi, QuestionData } from "@/services/psychometricApi";

export default function PsychometricTestPage() {
  const router = useRouter();
  const [screenName, setScreenName] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [question, setQuestion] = useState<QuestionData | null>(null);
  const [questionNumber, setQuestionNumber] = useState<number>(1);
  const [totalEstimated, setTotalEstimated] = useState<number>(10);

  // Selection states
  const [selectedOption, setSelectedOption] = useState<string | string[]>("");
  const [userInput, setUserInput] = useState<string>("");
  const [openEnded, setOpenEnded] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [isFinished, setIsFinished] = useState<boolean>(false);

  useEffect(() => {
    checkAndInit();
  }, []);

  const checkAndInit = async () => {
    try {
      setLoading(true);
      // 1. Check onboarding status
      const status = await psychometricApi.checkOnboardingStatus();
      if (status.is_onboarded) {
        // If already onboarded, redirect to home/dashboard
        router.push("/");
        return;
      }

      // 2. Fetch available tests
      const tests = await psychometricApi.getTests();
      const testName = tests && tests.length > 0 ? tests[0].name : "Demo psy 1";

      // 3. Start test session
      const sid = await psychometricApi.startNewTest(testName);
      setScreenName(sid);

      // 4. Load first question
      const qData = await psychometricApi.loadQuestion(sid);
      setQuestion(qData);
      setQuestionNumber(1);
    } catch (err) {
      console.error("Initialization error:", err);
      setErrorMessage("Could not load test session.");
    } finally {
      setLoading(false);
    }
  };

  const handleNext = async () => {
    if (!screenName || !question) return;

    const qType = question.question_type;
    if (qType === "Choices" && (!selectedOption || (Array.isArray(selectedOption) && selectedOption.length === 0))) {
      setErrorMessage("Please select an option before proceeding.");
      return;
    }
    if (qType === "User Input" && !userInput.trim()) {
      setErrorMessage("Please type your response.");
      return;
    }
    if (qType === "Open Ended" && !openEnded.trim()) {
      setErrorMessage("Please provide your answer.");
      return;
    }

    try {
      setSubmitting(true);
      setErrorMessage("");

      const res = await psychometricApi.nextQuestion({
        screen_name: screenName,
        selected_option: selectedOption,
        user_input: userInput,
        open_ended: openEnded,
      });

      if (res && res.completed) {
        await psychometricApi.submitTest(screenName);
        setIsFinished(true);
        setTimeout(() => {
          router.push("/");
        }, 2500);
        return;
      }

      setQuestion(res);
      setQuestionNumber((prev) => prev + 1);
      clearSelections();
    } catch (err) {
      console.error("Error advancing question:", err);
      setErrorMessage("Failed to save answer.");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePrevious = async () => {
    if (!screenName || questionNumber <= 1) return;

    try {
      setSubmitting(true);
      setErrorMessage("");

      const res = await psychometricApi.previousQuestion(screenName);
      setQuestion(res);
      setQuestionNumber((prev) => Math.max(1, prev - 1));

      if (res.saved_response) {
        setSelectedOption(res.saved_response);
        setUserInput(res.saved_response);
        setOpenEnded(res.saved_response);
      } else {
        clearSelections();
      }
    } catch (err) {
      console.error("Error loading previous question:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const clearSelections = () => {
    setSelectedOption("");
    setUserInput("");
    setOpenEnded("");
    setErrorMessage("");
  };

  const handleOptionSelect = (opt: string) => {
    setErrorMessage("");
    if (question?.multiple_correct) {
      const current = Array.isArray(selectedOption) ? selectedOption : [];
      if (current.includes(opt)) {
        setSelectedOption(current.filter((item) => item !== opt));
      } else {
        setSelectedOption([...current, opt]);
      }
    } else {
      setSelectedOption(opt);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-2xl overflow-hidden rounded-3xl bg-slate-900 border border-slate-800 shadow-2xl">
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-2xl bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center font-bold text-lg">
              🧠
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Student Psychometric Onboarding</h1>
              <p className="text-xs text-slate-400">Discover your personality orientation & career strengths</p>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        {!isFinished && !loading && (
          <div className="w-full bg-slate-800 h-1.5">
            <div
              className="bg-gradient-to-r from-indigo-500 to-purple-500 h-full transition-all duration-500"
              style={{ width: `${Math.min(100, (questionNumber / totalEstimated) * 100)}%` }}
            />
          </div>
        )}

        {/* Body */}
        <div className="p-6">
          {loading ? (
            <div className="py-16 flex flex-col items-center justify-center gap-4 text-center">
              <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
              <p className="text-sm text-slate-400">Loading your psychometric test session...</p>
            </div>
          ) : isFinished ? (
            <div className="py-12 flex flex-col items-center justify-center text-center gap-4">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-3xl">
                🎉
              </div>
              <h2 className="text-2xl font-bold text-white">Assessment Submitted!</h2>
              <p className="text-sm text-slate-400">Redirecting to your personalized dashboard...</p>
            </div>
          ) : question ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
                <span className="px-3 py-1 rounded-full bg-slate-800 text-indigo-400">
                  {question.subject || "Trait Assessment"}
                </span>
                <span>Question {questionNumber}</span>
              </div>

              <div
                className="text-lg font-medium text-slate-100"
                dangerouslySetInnerHTML={{ __html: question.question }}
              />

              {errorMessage && (
                <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs">
                  ⚠️ {errorMessage}
                </div>
              )}

              {question.question_type === "Choices" && question.options && (
                <div className="grid gap-3 pt-2">
                  {question.options.map((opt, idx) => {
                    const isSelected = Array.isArray(selectedOption)
                      ? selectedOption.includes(opt)
                      : selectedOption === opt;

                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleOptionSelect(opt)}
                        className={`w-full p-4 rounded-2xl border text-left text-sm font-medium transition-all ${
                          isSelected
                            ? "bg-indigo-600/20 border-indigo-500 text-white"
                            : "bg-slate-800/40 border-slate-700/70 text-slate-300 hover:bg-slate-800"
                        }`}
                      >
                        <span className="mr-3 text-xs font-bold text-slate-500">
                          {String.fromCharCode(65 + idx)}.
                        </span>
                        {opt}
                      </button>
                    );
                  })}
                </div>
              )}

              {question.question_type === "User Input" && (
                <input
                  type="text"
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  placeholder="Type your response..."
                  className="w-full p-4 rounded-2xl bg-slate-800/60 border border-slate-700 text-sm"
                />
              )}

              {question.question_type === "Open Ended" && (
                <textarea
                  rows={4}
                  value={openEnded}
                  onChange={(e) => setOpenEnded(e.target.value)}
                  placeholder="Provide your response..."
                  className="w-full p-4 rounded-2xl bg-slate-800/60 border border-slate-700 text-sm resize-none"
                />
              )}
            </div>
          ) : null}
        </div>

        {/* Footer Controls */}
        {!isFinished && !loading && (
          <div className="p-6 border-t border-slate-800 flex items-center justify-between">
            <button
              type="button"
              onClick={handlePrevious}
              disabled={questionNumber <= 1 || submitting}
              className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white disabled:opacity-30"
            >
              ← Previous
            </button>

            <button
              type="button"
              onClick={handleNext}
              disabled={submitting}
              className="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Next Question →"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
