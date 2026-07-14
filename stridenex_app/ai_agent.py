# Copyright (c) 2026, Stridenex App
# AI-powered internship / industry-project recommendation agent
# Backed by Groq's hosted API (OpenAI-compatible) using NATIVE tool-calling.
#
# WHY THE SWITCH: Ollama's /api/generate has no native tool support, so the
# previous version forced the model to hand-write JSON describing which tool
# to call, then parsed it manually. That's fragile (Qwen3 kept drifting from
# the schema and never producing a valid final_answer -> "exceeded max turns").
# Groq's chat.completions endpoint supports the standard `tools` param, so the
# API itself guarantees well-formed tool_calls -- no manual JSON parsing,
# no schema drift, no infinite loop of "Unknown action".
#
# SETUP REQUIRED:
#   1. pip install groq   (on the bench's python env)
#   2. Store the API key OUTSIDE of source code:
#        bench --site <site> set-config groq_api_key "gsk_..."
#      Never commit the key or paste it into code/chat. If a key has ever
#      been shared/pasted anywhere, rotate it in the Groq console immediately.
#   3. Same DocTypes/tools as before -- only the model-calling layer changed.

import json

import frappe
from frappe import _
from groq import Groq

GROQ_MODEL = "llama-3.3-70b-versatile"  # solid tool-calling model on Groq; swap if needed
MAX_AGENT_TURNS = 8


def _get_client():
	api_key = frappe.conf.get("groq_api_key")
	if not api_key:
		frappe.throw(_("groq_api_key is not set. Run: bench set-config groq_api_key <key>"))
	return Groq(api_key=api_key)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

@frappe.whitelist()
def generate_recommendation(student: str):
	profile = _build_student_profile(student)
	result = _run_agent_loop(profile)

	if result and "error" not in result:
		_log_recommendation(student, result)

	return result


@frappe.whitelist()
def get_recommendation_history(student: str):
	logs = frappe.get_all(
		"AI Recommendation Log",
		filters={"student": student},
		fields=[
			"name", "creation", "top_pick_type", "top_pick_name",
			"top_pick_title", "fit_score", "reasoning", "full_recommendation",
		],
		order_by="creation desc",
		limit_page_length=50,
	)
	for log in logs:
		try:
			parsed = json.loads(log.get("full_recommendation") or "{}")
			log["alternatives"] = parsed.get("alternatives", [])
		except Exception:
			log["alternatives"] = []
	return logs


# ---------------------------------------------------------------------------
# Tool schema (native function-calling format, OpenAI/Groq compatible)
# ---------------------------------------------------------------------------

TOOLS = [
	{
		"type": "function",
		"function": {
			"name": "search_internships",
			"description": "Search active internships, optionally filtered by industry and/or keyword.",
			"parameters": {
				"type": "object",
				"properties": {
					"industry": {"type": "string", "description": "Industry link name, optional"},
					"keyword": {"type": "string", "description": "Keyword to match in title/description, optional"},
				},
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "search_projects",
			"description": "Search active industry projects, optionally filtered by industry and/or keyword.",
			"parameters": {
				"type": "object",
				"properties": {
					"industry": {"type": "string", "description": "Industry link name, optional"},
					"keyword": {"type": "string", "description": "Keyword to match in project_name/description, optional"},
				},
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "get_student_skill_ledger",
			"description": "Get the VERIFIED skill ledger for a student (weight this more heavily than self-declared skills).",
			"parameters": {
				"type": "object",
				"properties": {
					"student": {"type": "string", "description": "Student docname (email_id)"},
				},
				"required": ["student"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "final_answer",
			"description": "Submit the final recommendation. Call this LAST, only after you have real candidates from search_internships/search_projects.",
			"parameters": {
				"type": "object",
				"properties": {
					"top_pick": {
						"type": "object",
						"properties": {
							"type": {"type": "string", "enum": ["internship", "project"]},
							"name": {"type": "string", "description": "docname"},
							"title": {"type": "string"},
							"reasoning": {"type": "string"},
							"fit_score": {"type": "number"},
						},
						"required": ["type", "name", "title", "reasoning", "fit_score"],
					},
					"alternatives": {
						"type": "array",
						"items": {
							"type": "object",
							"properties": {
								"type": {"type": "string", "enum": ["internship", "project"]},
								"name": {"type": "string"},
								"title": {"type": "string"},
								"reasoning": {"type": "string"},
								"fit_score": {"type": "number"},
							},
						},
					},
				},
				"required": ["top_pick"],
			},
		},
	},
]


# ---------------------------------------------------------------------------
# Agent loop -- native tool calling, Groq handles the schema for us
# ---------------------------------------------------------------------------

def _run_agent_loop(profile):
	client = _get_client()

	messages = [
		{"role": "system", "content": _system_prompt()},
		{"role": "user", "content": f"Student profile:\n{json.dumps(profile, indent=2, default=str)}"},
	]

	debug_trace = []

	for turn_num in range(MAX_AGENT_TURNS):
		try:
			resp = client.chat.completions.create(
				model=GROQ_MODEL,
				messages=messages,
				tools=TOOLS,
				tool_choice="auto",
				temperature=0.2,
			)
		except Exception as e:
			frappe.log_error(title="Groq API error", message=str(e))
			frappe.throw(_("Groq request failed: {0}").format(e))

		msg = resp.choices[0].message
		debug_trace.append({"turn": turn_num, "content": msg.content, "tool_calls": _serialize_tool_calls(msg)})

		if not msg.tool_calls:
			# Model replied with plain text instead of a tool call -- nudge it.
			messages.append({"role": "assistant", "content": msg.content or ""})
			messages.append({
				"role": "user",
				"content": (
					"You must respond by calling one of the provided tools "
					"(search_internships, search_projects, get_student_skill_ledger, "
					"or final_answer). Do not reply with plain text."
				),
			})
			continue

		# Append the assistant's tool-call message, then each tool result
		messages.append({
			"role": "assistant",
			"content": msg.content,
			"tool_calls": [
				{
					"id": tc.id,
					"type": "function",
					"function": {"name": tc.function.name, "arguments": tc.function.arguments},
				}
				for tc in msg.tool_calls
			],
		})

		for tc in msg.tool_calls:
			name = tc.function.name
			try:
				args = json.loads(tc.function.arguments or "{}")
			except json.JSONDecodeError:
				args = {}

			if name == "final_answer":
				return args  # {"top_pick": {...}, "alternatives": [...]}

			tool_output = _dispatch_tool(name, args)
			messages.append({
				"role": "tool",
				"tool_call_id": tc.id,
				"content": json.dumps(tool_output, default=str),
			})

	frappe.log_error(
		title="Groq agent exceeded max turns",
		message=json.dumps(debug_trace, indent=2, default=str)[:140000],
	)
	return {
		"error": "Agent exceeded max turns without a final_answer.",
		"debug_trace": debug_trace,  # keep while debugging; drop once stable
	}


def _serialize_tool_calls(msg):
	if not msg.tool_calls:
		return None
	return [{"name": tc.function.name, "arguments": tc.function.arguments} for tc in msg.tool_calls]


def _system_prompt():
	return """You are Stridenex's internship & project recommendation agent.
Find the single best-fit internship or industry project for the student,
using ONLY real listings retrieved via the provided tools. Never invent a
listing or skill.

Weigh verified skills (get_student_skill_ledger) more heavily than
self-declared skills already included in the student profile. Consider
CGPA/eligibility, career interest alignment, and skill overlap.

Call search_internships and/or search_projects (you may call either more
than once with different filters) before calling final_answer. Include 2-3
ranked alternatives besides the top pick. Call final_answer exactly once,
as your last step."""


# ---------------------------------------------------------------------------
# Tool dispatch -- unchanged from before, still only reads real Frappe data
# ---------------------------------------------------------------------------

def _dispatch_tool(name, tool_input):
	if name == "search_internships":
		return _search_internships(**{k: v for k, v in tool_input.items() if k in ("industry", "keyword")})
	if name == "search_projects":
		return _search_projects(**{k: v for k, v in tool_input.items() if k in ("industry", "keyword")})
	if name == "get_student_skill_ledger":
		return _get_student_skill_ledger(tool_input.get("student"))
	return {"error": f"Unknown tool: {name}"}


def _search_internships(industry=None, keyword=None):
	filters = {"status": "Active"}
	if industry:
		filters["industry"] = industry

	internships = frappe.get_all(
		"Internship",
		filters=filters,
		fields=[
			"name", "title", "industry", "type", "location", "work_mode",
			"stipend", "payment_mode", "duration", "openings",
			"application_deadline", "start_date", "end_date", "description",
		],
		limit_page_length=50,
	)

	for i in internships:
		i["required_skills"] = _get_child_skill_names("Internship", i["name"], "required_skills")

	if keyword:
		kw = keyword.lower()
		internships = [
			i for i in internships
			if kw in (i.get("title") or "").lower() or kw in (i.get("description") or "").lower()
		]

	return internships


def _search_projects(industry=None, keyword=None):
	filters = {"status": "Active"}
	if industry:
		filters["industry"] = industry

	projects = frappe.get_all(
		"Industry Project",
		filters=filters,
		fields=[
			"name", "project_name", "project_code", "industry", "description",
			"duration", "start_date", "end_date", "eligibility", "application_deadline",
		],
		limit_page_length=50,
	)

	for p in projects:
		p["required_skills"] = _get_child_skill_names("Industry Project", p["name"], "required_skills")

	if keyword:
		kw = keyword.lower()
		projects = [
			p for p in projects
			if kw in (p.get("project_name") or "").lower() or kw in (p.get("description") or "").lower()
		]

	return projects


def _get_student_skill_ledger(student):
	if not student:
		return []
	return frappe.get_all(
		"Student Skill",
		filters={"student": student, "status": "Verified"},
		fields=["skill", "current_level", "ai_verified", "evidence_count", "endorsement_count"],
	)


def _get_child_skill_names(parent_doctype, parent_name, child_fieldname):
	doc = frappe.get_cached_doc(parent_doctype, parent_name)
	rows = doc.get(child_fieldname) or []
	names = []
	for row in rows:
		value = row.get("skill") or row.get("skill_name") or row.get("name")
		if value:
			names.append(value)
	return names


# ---------------------------------------------------------------------------
# Student profile builder -- unchanged
# ---------------------------------------------------------------------------

def _build_student_profile(student):
	doc = frappe.get_doc("Student", student)

	self_declared_skills = []
	for row in doc.get("skill") or []:
		self_declared_skills.append({
			"skill": row.get("skill") or row.get("skill_name"),
			"level": row.get("level") or row.get("current_level"),
		})

	career_interests = []
	for row in doc.get("career_interest") or []:
		career_interests.append(row.get("career_interest") or row.get("interest"))

	return {
		"student": doc.name,
		"name": f"{doc.first_name} {doc.last_name}",
		"college": doc.college,
		"department": doc.department,
		"course": doc.course,
		"academic_year": doc.academic_year,
		"semester": doc.semester,
		"cgpa": doc.cgpa,
		"self_declared_skills": self_declared_skills,
		"verified_skill_ledger": _get_student_skill_ledger(student),
		"career_interests": career_interests,
	}


# ---------------------------------------------------------------------------
# Optional persistence -- unchanged
# ---------------------------------------------------------------------------

def _log_recommendation(student, result):
	if not frappe.db.exists("DocType", "AI Recommendation Log"):
		frappe.log_error(
			title="AI Recommendation Log missing",
			message="Create the AI Recommendation Log DocType to persist recommendation history.",
		)
		return

	top_pick = result.get("top_pick") or {}
	frappe.get_doc({
		"doctype": "AI Recommendation Log",
		"student": student,
		"top_pick_type": top_pick.get("type"),
		"top_pick_name": top_pick.get("name"),
		"top_pick_title": top_pick.get("title"),
		"fit_score": top_pick.get("fit_score"),
		"reasoning": top_pick.get("reasoning"),
		"full_recommendation": json.dumps(result, default=str),
	}).insert(ignore_permissions=True)
	frappe.db.commit()