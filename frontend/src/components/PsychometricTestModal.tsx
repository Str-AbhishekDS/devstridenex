"use client";

import React, { useState, useEffect } from "react";
import { psychometricApi, QuestionData } from "@/services/psychometricApi";

interface PsychometricTestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCompleted: () => void;
}

export default function PsychometricTestModal({
  isOpen,
  onClose,
  onCompleted,
}: PsychometricTestModalProps) {
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

  // Initialize test session when modal opens
  useEffect(() => {
    if (isOpen && !screenName) {
      initTest();
    }
  }, [isOpen]);

  const initTest = async () => {
    try {
      setLoading(true);
      setErrorMessage("");
      
      // 1. Fetch available tests
      const tests = await psychometricApi.getTests();
      const testName = tests && tests.length > 0 ? tests[0].name : "Demo psy 1";
      
      // 2. Start new test session
      const sid = await psychometricApi.startNewTest(testName);
      setScreenName(sid);

      // 3. Load first question
      const qData = await psychometricApi.loadQuestion(sid);
      setQuestion(qData);
      setQuestionNumber(1);
    } catch (err: any) {
      console.error("Failed to initialize psychometric test:", err);
      setErrorMessage("Could not load test session. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleNext = async () => {
    if (!screenName || !question) return;

    // Validation
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
        // Test finish flow
        await psychometricApi.submitTest(screenName);
        setIsFinished(true);
        setTimeout(() => {
          onCompleted();
        }, 3000);
        return;
      }

      // Load next question
      setQuestion(res);
      setQuestionNumber((prev) => prev + 1);
      clearSelections();
    } catch (err: any) {
      console.error("Error advancing question:", err);
      setErrorMessage("Failed to save answer. Please try again.");
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

      // Restore saved response
      if (res.saved_response) {
        setSelectedOption(res.saved_response);
        setUserInput(res.saved_response);
        setOpenEnded(res.saved_response);
      } else {
        clearSelections();
      }
    } catch (err: any) {
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-md transition-all duration-300">
      <div className="relative w-full max-w-2xl overflow-hidden rounded-3xl bg-slate-900 border border-slate-800 text-slate-100 shadow-2xl shadow-indigo-950/50 flex flex-col max-h-[90vh]">
        
        {/* Header Bar */}
        <div className="px-6 pt-6 pb-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-500 to-purple-500 text-white font-bold text-lg shadow-lg shadow-indigo-500/30">
              🧠
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                Psychometric Assessment
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-medium">
                  Onboarding Step
                </span>
              </h2>
              <p className="text-xs text-slate-400">Discover your personality orientation & career strengths</p>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        {!isFinished && !loading && (
          <div className="w-full bg-slate-800/50 h-1.5 overflow-hidden">
            <div
              className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 h-full transition-all duration-500 ease-out"
              style={{
                width: `${Math.min(100, (questionNumber / totalEstimated) * 100)}%`,
              }}
            />
          </div>
        )}

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 custom-scrollbar">
          {loading ? (
            <div className="py-16 flex flex-col items-center justify-center text-center gap-4">
              <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
              <p className="text-sm font-medium text-slate-300 animate-pulse">
                Initializing your psychometric test session...
              </p>
            </div>
          ) : isFinished ? (
            /* Celebration Completion View */
            <div className="py-12 flex flex-col items-center justify-center text-center gap-6 animate-fadeIn">
              <div className="w-20 h-20 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-4xl shadow-xl shadow-emerald-500/20 animate-bounce">
                🎉
              </div>
              <div className="space-y-2">
                <h3 className="text-2xl font-bold text-white">Assessment Complete!</h3>
                <p className="text-sm text-slate-400 max-w-md">
                  Thank you for completing your orientation evaluation. Your personality breakdown is being calculated.
                </p>
              </div>
              <div className="px-5 py-3 rounded-2xl bg-slate-800/80 border border-slate-700/60 text-xs text-indigo-300 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
                Generating AI Career Trait Analysis...
              </div>
            </div>
          ) : question ? (
            /* Active Question View */
            <div className="space-y-6">
              {/* Subject Tag & Question Number */}
              <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400">
                <span className="px-3 py-1 rounded-full bg-slate-800 text-indigo-400 border border-slate-700">
                  {question.subject || "General Personality"}
                </span>
                <span>Question {questionNumber}</span>
              </div>

              {/* Question Text */}
              <div
                className="text-lg md:text-xl font-medium text-slate-100 leading-relaxed"
                dangerouslySetInnerHTML={{ __html: question.question }}
              />

              {/* Error Message Toast */}
              {errorMessage && (
                <div className="p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                  <span>⚠️</span> {errorMessage}
                </div>
              )}

              {/* Options Rendering */}
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
                        className={`w-full p-4 rounded-2xl border text-left font-medium text-sm transition-all duration-200 flex items-center justify-between group ${
                          isSelected
                            ? "bg-indigo-600/20 border-indigo-500 text-white shadow-lg shadow-indigo-600/10 ring-1 ring-indigo-500/50"
                            : "bg-slate-800/40 border-slate-700/70 text-slate-300 hover:bg-slate-800 hover:border-slate-600 hover:text-white"
                        }`}
                      >
                        <span className="flex items-center gap-3">
                          <span
                            className={`w-7 h-7 rounded-xl flex items-center justify-center text-xs font-bold transition-colors ${
                              isSelected
                                ? "bg-indigo-500 text-white"
                                : "bg-slate-700 text-slate-400 group-hover:bg-slate-600 group-hover:text-slate-200"
                            }`}
                          >
                            {String.fromCharCode(65 + idx)}
                          </span>
                          {opt}
                        </span>

                        <span
                          className={`w-5 h-5 rounded-full border flex items-center justify-center text-xs transition-all ${
                            isSelected
                              ? "border-indigo-400 bg-indigo-500 text-white"
                              : "border-slate-600 bg-transparent opacity-40 group-hover:opacity-100"
                          }`}
                        >
                          {isSelected && "✓"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* User Input Type */}
              {question.question_type === "User Input" && (
                <div className="pt-2">
                  <input
                    type="text"
                    value={userInput}
                    onChange={(e) => {
                      setUserInput(e.target.value);
                      setErrorMessage("");
                    }}
                    placeholder="Type your response here..."
                    className="w-full p-4 rounded-2xl bg-slate-800/60 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-slate-500"
                  />
                </div>
              )}

              {/* Open Ended Type */}
              {question.question_type === "Open Ended" && (
                <div className="pt-2">
                  <textarea
                    rows={4}
                    value={openEnded}
                    onChange={(e) => {
                      setOpenEnded(e.target.value);
                      setErrorMessage("");
                    }}
                    placeholder="Provide your response..."
                    className="w-full p-4 rounded-2xl bg-slate-800/60 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-slate-500 resize-none"
                  />
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Modal Footer Controls */}
        {!isFinished && !loading && (
          <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/80 flex items-center justify-between">
            <button
              type="button"
              onClick={handlePrevious}
              disabled={questionNumber <= 1 || submitting}
              className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent transition-all flex items-center gap-1.5"
            >
              ← Previous
            </button>

            <button
              type="button"
              onClick={handleNext}
              disabled={submitting}
              className="px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-600 hover:from-indigo-600 hover:to-purple-600 active:scale-95 shadow-lg shadow-indigo-500/25 transition-all disabled:opacity-50 flex items-center gap-2"
            >
              {submitting ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Saving...
                </>
              ) : (
                <>Next Question →</>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
