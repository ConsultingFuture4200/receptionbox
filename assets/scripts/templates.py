"""Dialogue script templates for the 500-call corpus (ASSETS-01 / D-01).

Persona x intent x adversity matrix produces 10 x 10 x 5 = 500 unique combos.
Utterances are hand-curated by (intent, persona) -- adversity_level is a
*rendering* attribute (background noise, accent intensity, etc.) handled
in render_corpus.py, not a textual variation.
"""

from __future__ import annotations

import json
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIALOGUES_JSON = ROOT / "assets" / "scripts" / "dialogues.json"

INTENTS: tuple[str, ...] = (
    "intake_inquiry",
    "fee_question",
    "attorney_request",
    "hours_inquiry",
    "location_inquiry",
    "case_status_question",
    "document_dropoff_request",
    "appointment_reschedule",
    "attorney_callback_request",
    "escalation_request",
)

ADVERSITY_LEVELS: tuple[str, ...] = (
    "neutral",
    "mild_emotional",
    "accent_strong",
    "background_noise",
    "urgent_distressed",
)

PERSONAS: tuple[str, ...] = (
    "nervous_first_time",
    "returning_client",
    "frustrated_billing",
    "calm_professional",
    "elderly_hard_of_hearing",
    "esl_speaker",
    "fast_talker",
    "soft_voice",
    "interrupting_caller",
    "cooperative_brief",
)

KOKORO_VOICE_BY_PERSONA: dict[str, str] = {
    # Maps to Kokoro voice presets; production voice catalog locked at render time.
    "nervous_first_time": "af_heart",
    "returning_client": "af_alloy",
    "frustrated_billing": "am_adam",
    "calm_professional": "af_bella",
    "elderly_hard_of_hearing": "am_michael",
    "esl_speaker": "af_nicole",
    "fast_talker": "am_eric",
    "soft_voice": "af_sky",
    "interrupting_caller": "am_liam",
    "cooperative_brief": "af_river",
}

# Hand-curated utterance pool, keyed by (intent, persona). Each entry is one
# canonical utterance that gets adversity-rendered five times. We curate 100
# utterances total (10 intents x 10 personas) to fully populate the matrix.

UTTERANCES: dict[tuple[str, str], str] = {
    # intake_inquiry
    (
        "intake_inquiry",
        "nervous_first_time",
    ): "Hi, I -- I'm not sure if I'm in the right place. I had something happen with my landlord and I think I need to talk to someone.",
    (
        "intake_inquiry",
        "returning_client",
    ): "Hi, this is Pat. I worked with the firm last spring and I have a new matter -- can I get on the schedule again?",
    (
        "intake_inquiry",
        "frustrated_billing",
    ): "I need an attorney for a billing dispute with my contractor. Can someone call me back today?",
    (
        "intake_inquiry",
        "calm_professional",
    ): "Good morning. I'd like to schedule a consultation regarding a commercial lease question.",
    (
        "intake_inquiry",
        "elderly_hard_of_hearing",
    ): "Hello? I -- yes -- I want to set up a meeting about my late husband's estate.",
    (
        "intake_inquiry",
        "esl_speaker",
    ): "Hello, I have problem with my employer and I want to make consultation, please.",
    (
        "intake_inquiry",
        "fast_talker",
    ): "Hi I'm calling because my neighbor is doing something on the property line and I think I need a lawyer fast can someone get back to me?",
    (
        "intake_inquiry",
        "soft_voice",
    ): "I'd like to ask about consulting on a personal injury matter.",
    (
        "intake_inquiry",
        "interrupting_caller",
    ): "Yeah hi -- listen -- I just need to know -- can you handle a small business dispute?",
    (
        "intake_inquiry",
        "cooperative_brief",
    ): "Hi, I'd like to set up a consultation about a landlord-tenant matter.",
    # fee_question
    (
        "fee_question",
        "nervous_first_time",
    ): "I -- this might be a silly question -- but how much would something like a will cost?",
    (
        "fee_question",
        "returning_client",
    ): "Quick question -- ballpark, what would a contract review run me?",
    (
        "fee_question",
        "frustrated_billing",
    ): "I just want to know the rate before I waste any more of my time.",
    (
        "fee_question",
        "calm_professional",
    ): "What is the typical retainer for an employment matter at the firm?",
    ("fee_question", "elderly_hard_of_hearing"): "How much will it cost? I'm on a fixed income.",
    ("fee_question", "esl_speaker"): "Please, what is the price for the consultation?",
    (
        "fee_question",
        "fast_talker",
    ): "Whats the hourly rate I just need a number to compare with another firm we got a quote from yesterday.",
    ("fee_question", "soft_voice"): "Could you tell me what you charge for an initial review?",
    (
        "fee_question",
        "interrupting_caller",
    ): "Just tell me -- how much -- how much for a divorce consultation?",
    ("fee_question", "cooperative_brief"): "What does a 30-minute consultation cost?",
    # attorney_request
    (
        "attorney_request",
        "nervous_first_time",
    ): "I think I need an actual attorney to talk to me, not just a paralegal -- is that possible?",
    (
        "attorney_request",
        "returning_client",
    ): "Can I be put through to Attorney Reyes? She handled my last matter.",
    (
        "attorney_request",
        "frustrated_billing",
    ): "I need to speak with a partner about a problem with the invoice.",
    (
        "attorney_request",
        "calm_professional",
    ): "Could you connect me with the attorney handling commercial litigation?",
    (
        "attorney_request",
        "elderly_hard_of_hearing",
    ): "I'd like to speak with the lawyer please. The actual lawyer.",
    (
        "attorney_request",
        "esl_speaker",
    ): "I want to speak with attorney directly please, not assistant.",
    (
        "attorney_request",
        "fast_talker",
    ): "Yeah I really need to talk to an attorney can you put me through to whoever's available right now?",
    (
        "attorney_request",
        "soft_voice",
    ): "Is there an attorney available who could speak with me briefly?",
    (
        "attorney_request",
        "interrupting_caller",
    ): "Don't transfer me again -- I want -- get me an attorney on the phone.",
    ("attorney_request", "cooperative_brief"): "Could I speak with an attorney about my matter?",
    # hours_inquiry
    (
        "hours_inquiry",
        "nervous_first_time",
    ): "What -- when are you guys open? I didn't want to call too early.",
    ("hours_inquiry", "returning_client"): "Are you open through five today?",
    ("hours_inquiry", "frustrated_billing"): "What are your hours? I keep getting voicemail.",
    (
        "hours_inquiry",
        "calm_professional",
    ): "Could you tell me your business hours and whether evening appointments are available?",
    ("hours_inquiry", "elderly_hard_of_hearing"): "What time do you close? My ride is asking.",
    ("hours_inquiry", "esl_speaker"): "What are open hours, please?",
    (
        "hours_inquiry",
        "fast_talker",
    ): "What are your hours just need to know if I can swing by after work today around six fifteen.",
    ("hours_inquiry", "soft_voice"): "I just wanted to check what time you close.",
    ("hours_inquiry", "interrupting_caller"): "Hours -- what are -- when do you close today?",
    ("hours_inquiry", "cooperative_brief"): "What are your office hours?",
    # location_inquiry
    (
        "location_inquiry",
        "nervous_first_time",
    ): "Where are you located? I might be in the wrong part of town.",
    ("location_inquiry", "returning_client"): "Are you still at the same address as last year?",
    (
        "location_inquiry",
        "frustrated_billing",
    ): "Where do I drop off this paperwork? Just give me an address.",
    (
        "location_inquiry",
        "calm_professional",
    ): "Could you confirm the office address and parking arrangements?",
    (
        "location_inquiry",
        "elderly_hard_of_hearing",
    ): "Where are you located? Can you spell the street?",
    ("location_inquiry", "esl_speaker"): "Please, what is the address of office?",
    (
        "location_inquiry",
        "fast_talker",
    ): "What's your address I'm putting it in my GPS right now is it the building with the brick front?",
    ("location_inquiry", "soft_voice"): "Could you tell me where you're located?",
    ("location_inquiry", "interrupting_caller"): "Address -- I just need -- the address please.",
    ("location_inquiry", "cooperative_brief"): "What's your office address?",
    # case_status_question
    (
        "case_status_question",
        "nervous_first_time",
    ): "I -- I haven't heard anything in a while -- could someone tell me where my case is at?",
    (
        "case_status_question",
        "returning_client",
    ): "Hi it's me again, can I get a status update on the file?",
    ("case_status_question", "frustrated_billing"): "Where are we on this? It's been three weeks.",
    (
        "case_status_question",
        "calm_professional",
    ): "Could I get a status update on the matter we opened in February?",
    (
        "case_status_question",
        "elderly_hard_of_hearing",
    ): "Can someone tell me what's happening with my case please?",
    ("case_status_question", "esl_speaker"): "I want to know about my case, please. Status.",
    (
        "case_status_question",
        "fast_talker",
    ): "Hey just checking in on my case any updates I haven't heard from anyone in a couple weeks.",
    (
        "case_status_question",
        "soft_voice",
    ): "Could someone update me on my matter when there's time?",
    ("case_status_question", "interrupting_caller"): "My case -- I need an update -- where are we?",
    ("case_status_question", "cooperative_brief"): "Can I get a status update on my case?",
    # document_dropoff_request
    (
        "document_dropoff_request",
        "nervous_first_time",
    ): "I -- I have some papers I was told to bring in -- can I just drop them off?",
    (
        "document_dropoff_request",
        "returning_client",
    ): "I'm dropping off the signed retainer this afternoon, who should I leave it with?",
    (
        "document_dropoff_request",
        "frustrated_billing",
    ): "Where should I leave these documents? I don't want to mail them.",
    (
        "document_dropoff_request",
        "calm_professional",
    ): "I have a packet of documents to deliver -- when is the front desk staffed?",
    (
        "document_dropoff_request",
        "elderly_hard_of_hearing",
    ): "I have some papers to bring you. Where do I leave them?",
    ("document_dropoff_request", "esl_speaker"): "I bring documents today, please. Where I leave?",
    (
        "document_dropoff_request",
        "fast_talker",
    ): "I'm coming by to drop off paperwork in like ten minutes who do I give it to is there a front desk?",
    (
        "document_dropoff_request",
        "soft_voice",
    ): "I have documents to drop off -- where would I bring them?",
    (
        "document_dropoff_request",
        "interrupting_caller",
    ): "Documents -- where -- where do I drop these off?",
    ("document_dropoff_request", "cooperative_brief"): "Where can I drop off some paperwork?",
    # appointment_reschedule
    (
        "appointment_reschedule",
        "nervous_first_time",
    ): "I -- I'm sorry, I had a thing come up -- can I move my appointment?",
    (
        "appointment_reschedule",
        "returning_client",
    ): "Need to reschedule Thursday's meeting -- something at work came up.",
    ("appointment_reschedule", "frustrated_billing"): "I have to move my appointment again, sorry.",
    (
        "appointment_reschedule",
        "calm_professional",
    ): "Could we reschedule the Thursday consultation to early next week?",
    (
        "appointment_reschedule",
        "elderly_hard_of_hearing",
    ): "I need to change my appointment. I have a doctor's visit.",
    (
        "appointment_reschedule",
        "esl_speaker",
    ): "I cannot come to appointment Thursday, please change.",
    (
        "appointment_reschedule",
        "fast_talker",
    ): "Hey I gotta reschedule my appointment for tomorrow can we push it to next week sometime in the afternoon?",
    ("appointment_reschedule", "soft_voice"): "Could we move my appointment to a different day?",
    (
        "appointment_reschedule",
        "interrupting_caller",
    ): "Reschedule -- I need to -- change the time.",
    ("appointment_reschedule", "cooperative_brief"): "I need to reschedule my appointment.",
    # attorney_callback_request
    (
        "attorney_callback_request",
        "nervous_first_time",
    ): "Could -- could someone call me back? I have a question I'd rather not leave on a message.",
    (
        "attorney_callback_request",
        "returning_client",
    ): "Just need a callback when she's free, no rush.",
    (
        "attorney_callback_request",
        "frustrated_billing",
    ): "I need a call back today -- this can't wait until next week.",
    (
        "attorney_callback_request",
        "calm_professional",
    ): "Could I request a callback at the attorney's earliest convenience?",
    (
        "attorney_callback_request",
        "elderly_hard_of_hearing",
    ): "Can someone call me back later? I have a question.",
    ("attorney_callback_request", "esl_speaker"): "Please, can the attorney call me back today?",
    (
        "attorney_callback_request",
        "fast_talker",
    ): "Need a callback when she gets a chance can be later today or tomorrow either works for me.",
    (
        "attorney_callback_request",
        "soft_voice",
    ): "Could I ask for a callback when there's a moment?",
    (
        "attorney_callback_request",
        "interrupting_caller",
    ): "Have him call me -- back -- soon as he can.",
    ("attorney_callback_request", "cooperative_brief"): "Could the attorney call me back today?",
    # escalation_request
    (
        "escalation_request",
        "nervous_first_time",
    ): "I -- I don't think the assistant can help me with this -- can I speak to someone higher up?",
    (
        "escalation_request",
        "returning_client",
    ): "I need to escalate this -- can I get a partner on the line?",
    (
        "escalation_request",
        "frustrated_billing",
    ): "I want to speak to whoever is in charge. Now please.",
    (
        "escalation_request",
        "calm_professional",
    ): "I'd like to escalate this matter -- could you put me through to a senior attorney?",
    (
        "escalation_request",
        "elderly_hard_of_hearing",
    ): "I want to speak with someone in charge please.",
    ("escalation_request", "esl_speaker"): "I want to speak with manager or senior, please.",
    (
        "escalation_request",
        "fast_talker",
    ): "I really need to speak with somebody in charge this is the third time I've called and gotten nowhere.",
    ("escalation_request", "soft_voice"): "Could I speak with someone more senior, please?",
    (
        "escalation_request",
        "interrupting_caller",
    ): "Manager -- supervisor -- whoever's in charge -- please.",
    ("escalation_request", "cooperative_brief"): "I'd like to speak with a supervisor.",
}


def build_dialogues(seed: int = 42) -> list[dict]:
    """Deterministic 500-dialogue authoring.

    Iterates (intent, adversity_level, persona) in fixed order. Each combo
    gets one dialogue with the canonical (intent, persona) utterance and
    the adversity_level recorded as a render-time hint.
    """
    rng = random.Random(seed)  # used only if we add adversity-driven utterance variants
    out: list[dict] = []
    seq = 1
    for intent in INTENTS:
        for adv in ADVERSITY_LEVELS:
            for persona in PERSONAS:
                key = (intent, persona)
                utterance = UTTERANCES.get(key)
                if utterance is None:
                    raise SystemExit(f"Missing canonical utterance for ({intent}, {persona})")
                out.append(
                    {
                        "script_id": f"call-{seq:04d}",
                        "intent": intent,
                        "adversity_level": adv,
                        "persona": persona,
                        "utterance": utterance,
                        "voice_seed": KOKORO_VOICE_BY_PERSONA[persona],
                        "duration_target_s": 5.0,
                    }
                )
                seq += 1
    # rng currently unused -- kept so future adversity-driven variants are deterministic
    _ = rng
    return out


def main() -> int:
    dialogues = build_dialogues(seed=42)
    if len(dialogues) != 500:
        raise SystemExit(f"expected 500 dialogues, got {len(dialogues)}")
    payload = json.dumps(dialogues, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    DIALOGUES_JSON.write_text(payload)
    print(f"Wrote {len(dialogues)} dialogues -> {DIALOGUES_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
