Exercise Plan JSON Format (for LLM output)
Required keys
summary: string

weekly_plan: array of exactly 14 day objects (days 1..14)

safety: string

progression: string

measures: array of strings

Day object
{
"day": 1..14,
"focus": "core|balance|posture|gait|active-recovery|rest",
"exercises": [
{ "name": "...", "sets": 2, "reps": "8 each", "notes": "..." }
]
}

Validation rules
Exactly 14 entries in weekly_plan.

For non‑rest days, include at least one exercise with name, sets, reps, notes.

Keep language patient‑friendly; avoid jargon.