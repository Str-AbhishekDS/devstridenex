// Frappe API base URL configuration
// Uses window.location.origin in browser environment or fallback to Frappe site URL
const getBackendUrl = () => {
  if (typeof window !== "undefined") {
    // If running on port 3000/3001, proxy or target backend server
    if (window.location.port === "3001" || window.location.port === "3000") {
      return "https://devstridenex.quantcloud.in";
    }
    return window.location.origin;
  }
  return "https://devstridenex.quantcloud.in";
};

export interface OnboardingStatusResponse {
  is_onboarded: boolean;
  test_completed: boolean;
  has_completed_test: boolean;
  submission?: {
    name: string;
    psychometric_test: string;
    score: number;
    percentage: number;
    creation: string;
  } | null;
  test_screen?: {
    name: string;
    creation: string;
    docstatus: number;
  } | null;
}

export interface QuestionData {
  question: string;
  question_type: "Choices" | "User Input" | "Open Ended";
  subject: string;
  options?: string[];
  multiple_correct?: boolean | number;
  is_last?: boolean;
  no_of_options?: string;
  saved_response?: string | null;
  completed?: boolean;
}

export const psychometricApi = {
  // 1. Check onboarding status for logged in student
  checkOnboardingStatus: async (): Promise<OnboardingStatusResponse> => {
    try {
      const res = await fetch(`${getBackendUrl()}/api/method/nexedu.api.check_onboarding_status`, {
        method: "GET",
        credentials: "include",
        headers: { "Content-Type": "application/json" }
      });
      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`);
      }
      const data = await res.json();
      return data.message || { is_onboarded: false, test_completed: false, has_completed_test: false };
    } catch (err) {
      console.warn("Could not check onboarding status, defaulting to uncompleted", err);
      return { is_onboarded: false, test_completed: false, has_completed_test: false };
    }
  },

  // 2. Fetch list of available psychometric tests
  getTests: async (): Promise<Array<{ name: string }>> => {
    const res = await fetch(`${getBackendUrl()}/api/method/nexedu.api.get_tests`, {
      method: "GET",
      credentials: "include",
      headers: { "Content-Type": "application/json" }
    });
    const data = await res.json();
    return data.message || [];
  },

  // 3. Start a new test session and return session screen_name (ID)
  startNewTest: async (testType: string): Promise<string> => {
    const res = await fetch(`${getBackendUrl()}/api/method/nexedu.api.start_new_test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ test_type: testType })
    });
    const data = await res.json();
    return data.message;
  },

  // 4. Load question for screen_name
  loadQuestion: async (screenName: string): Promise<QuestionData> => {
    const res = await fetch(`${getBackendUrl()}/api/method/nexedu.api.load_question`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ screen_name: screenName })
    });
    const data = await res.json();
    return data.message;
  },

  // 5. Submit answer and load next question
  nextQuestion: async (params: {
    screen_name: string;
    selected_option?: string | string[];
    user_input?: string;
    open_ended?: string;
  }): Promise<QuestionData> => {
    const res = await fetch(`${getBackendUrl()}/api/method/nexedu.api.next_question`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(params)
    });
    const data = await res.json();
    return data.message;
  },

  // 6. Go back to previous question
  previousQuestion: async (screenName: string): Promise<QuestionData> => {
    const res = await fetch(`${getBackendUrl()}/api/method/nexedu.api.previous_question`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ screen_name: screenName })
    });
    const data = await res.json();
    return data.message;
  },

  // 7. Finalize and submit the test session
  submitTest: async (screenName: string): Promise<string> => {
    const res = await fetch(`${getBackendUrl()}/api/method/nexedu.api.submit_test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ name: screenName })
    });
    const data = await res.json();
    return data.message;
  }
};
