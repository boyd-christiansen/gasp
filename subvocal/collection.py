"""Versioned, local-only collection protocols. Prompts are never model inputs."""
import random
import uuid

PROTOCOL = "personal-training-v1"


def prompt(key, text, seconds=6, mode=None, instruction="", target=None):
    return dict(id=key, text=text, target=text if target is None else target,
                duration_s=seconds, mode=mode, instruction=instruction)


DECKS = [
    dict(id="calibration-v1", name="Personal calibration", description="Placement reference, articulation checks, and everyday movement. About 5 minutes with review.", calibration=True, prompts=[
        prompt("still", "Sit comfortably and stay still.", 8, "rest", "Keep your normal desk posture. Breathe normally.", "[rest]"),
        prompt("jaw", "Slowly open and close your jaw three times.", 8, "negative", "Movement reference; do not speak.", "[jaw movement]"),
        prompt("lips", "Purse your lips, then relax. Repeat three times.", 8, "negative", "Movement reference; do not speak.", "[lip movement]"),
        prompt("stops", "pa pa pa · ta ta ta · ka ka ka", 8, instruction="Read at a comfortable pace. Keep the movement natural."),
        prompt("nasals", "ma ma ma · na na na · me nee moo", 8),
        prompt("fricatives", "fa va · sa za · sha sha · tha tha", 8, instruction="Use your normal pronunciation; this is coverage, not a pronunciation test."),
        prompt("vowels", "ee ah oo · ee ah oo · oh ay eye", 8),
        prompt("sentence1", "Please put the blue mug beside my keyboard.", 8),
        prompt("sentence2", "We should move the meeting to Thursday afternoon.", 8),
        prompt("sentence3", "Five small packages arrived before lunch.", 8),
        prompt("turn", "Look left, look right, then return to the screen.", 8, "negative", "Do not speak. Keep the sensor fixed.", "[head turn]"),
        prompt("swallow", "Swallow once, then sit still.", 6, "negative", "Do not speak.", "[swallow]"),
    ]),
    dict(id="commands-v1", name="First phrase experiment", description="Six short commands plus rest. Repeated in a reproducible shuffled order.", calibration=False, prompts=[
        prompt("note", "add a note", 4), prompt("save", "save this note", 4),
        prompt("paragraph", "new paragraph", 4), prompt("undo", "undo that", 4),
        prompt("next", "next item", 4), prompt("cancel", "cancel that", 4),
        prompt("rest", "Sit still without speaking.", 4, "rest", "An important negative example.", "[rest]"),
    ]),
    dict(id="sentences-v1", name="Natural sentences", description="Varied sentence material for future sequence models. This starter deck is not a complete phonetic corpus.", calibration=False, prompts=[
        prompt("s1", "Please put the blue mug beside my keyboard.", 8),
        prompt("s2", "We should move the meeting to Thursday afternoon.", 8),
        prompt("s3", "Five small packages arrived before lunch.", 8),
        prompt("s4", "Can you check whether the window is open?", 8),
        prompt("s5", "I would like a little more time to think.", 8),
        prompt("s6", "The quiet room faces the busy street.", 8),
        prompt("s7", "Send the updated document when you finish.", 8),
        prompt("s8", "My train leaves at seven thirty tomorrow.", 8),
        prompt("s9", "A fresh cup of coffee would be lovely.", 8),
        prompt("s10", "Which of these three options works best?", 8),
        prompt("s11", "We walked through the park after the rain.", 8),
        prompt("s12", "Remember to bring your keys and jacket.", 8),
    ]),
]


def make_plan(deck_id, mode="silent", repetitions=2, seed=None):
    if mode not in {"silent", "voiced", "paired"}:
        raise ValueError("Choose silent, voiced or paired collection")
    deck = next((d for d in DECKS if d["id"] == deck_id), None)
    if not deck:
        raise ValueError("Unknown collection deck")
    if not 1 <= repetitions <= 10:
        raise ValueError("Use 1–10 repetitions")
    seed = uuid.uuid4().hex if seed is None else str(seed)
    units = [(p, rep) for rep in range(1 if deck["calibration"] else repetitions) for p in deck["prompts"]]
    if not deck["calibration"]:
        random.Random(seed).shuffle(units)
    plan = []
    for p, rep in units:
        pair_id = uuid.uuid4().hex if mode == "paired" and not p["mode"] else None
        modes = [p["mode"]] if p["mode"] else ["voiced", "silent"] if mode == "paired" else [mode]
        for articulation in modes:
            plan.append(dict(step_id=uuid.uuid4().hex, prompt_id=p["id"], prompt_text=p["text"],
                target_text=p["target"], duration_s=p["duration_s"], articulation=articulation,
                instruction=p["instruction"], repetition=rep+1, pair_id=pair_id))
    return dict(protocol=PROTOCOL, deck_id=deck_id, deck_name=deck["name"], calibration=deck["calibration"],
                mode=mode, repetitions=repetitions, seed=seed, steps=plan)
