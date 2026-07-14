"""ActScheduler: parity with the source app's scheduler, plus the
force/avoid/fallback/age semantics documented on pick()."""

import random

from scrollkit.utils.scheduler import ActScheduler


def _oracle_pick(ages_all, deck, deck_key, avoid, force=None):
    """The ORIGINAL _sched_pick math (DarkOwl app), verbatim, as the
    parity oracle. Any drift between this and ActScheduler is a bug."""
    ages = ages_all.setdefault(deck_key, {})
    chosen = None
    if force is not None:
        for e in deck:
            if e[0] == force:
                chosen = e
                break
    if chosen is None:
        candidates = [e for e in deck if e[1] not in avoid]
        if not candidates:
            candidates = list(deck)
        weights = []
        total = 0
        for e in candidates:
            age = min(ages.get(e[0], 12), 20)
            w = (age + 1) * (age + 1)
            total += w
            weights.append(total)
        roll = random.random() * total
        chosen = candidates[-1]
        for e, cum in zip(candidates, weights):
            if roll < cum:
                chosen = e
                break
    for e in deck:
        ages[e[0]] = min(ages.get(e[0], 12) + 1, 20)
    ages[chosen[0]] = 0
    return chosen


DECK = (
    ("slide", "letters", "payload-a"),
    ("swarm", "swarm", "payload-b"),
    ("drip", "fall", "payload-c"),
    ("wink", "wall", "payload-d"),
    ("iris", "radial", "payload-e"),
)


def test_parity_with_the_source_scheduler():
    script = [((), None), (("letters",), None), (("fall", "wall"), None),
              ((), "wink"), (("radial",), None)] * 40
    random.seed(20260714)
    oracle_ages = {}
    expected = [_oracle_pick(oracle_ages, DECK, "b", avoid, force)
                for avoid, force in script]
    random.seed(20260714)
    sched = ActScheduler()
    actual = [sched.pick(DECK, "b", avoid, force)
              for avoid, force in script]
    assert actual == expected
    assert sched._ages["b"] == oracle_ages["b"]


def test_force_picks_by_name_with_bookkeeping():
    sched = ActScheduler()
    e = sched.pick(DECK, "b", avoid=("letters",), force="slide")
    assert e[0] == "slide"                       # force beats avoid
    assert sched._ages["b"]["slide"] == 0        # counts as just-played
    assert sched._ages["b"]["swarm"] == 13       # everyone else aged


def test_avoid_excludes_families_with_whole_deck_fallback():
    random.seed(7)
    sched = ActScheduler()
    for _ in range(50):
        e = sched.pick(DECK, "b", avoid=("letters", "swarm"))
        assert e[1] not in ("letters", "swarm")
    all_families = tuple(e[1] for e in DECK)
    e = sched.pick(DECK, "b", avoid=all_families)     # excludes everything
    assert e in DECK                                  # falls back, still picks


def test_ages_cap_and_new_entries_lead():
    random.seed(3)
    sched = ActScheduler()
    for _ in range(30):
        sched.pick(DECK, "b")
    assert all(a <= ActScheduler.AGE_CAP for a in sched._ages["b"].values())
    # A brand-new entry starts at NEW_AGE and so tends to surface quickly.
    grown = DECK + (("hunt", "letters", "payload-f"),)
    hits = 0
    for _ in range(6):
        if sched.pick(grown, "b")[0] == "hunt":
            hits += 1
    assert hits >= 1


def test_decks_are_independent_by_key():
    sched = ActScheduler()
    sched.pick(DECK, "builds", force="slide")
    sched.pick(DECK, "exits", force="wink")
    assert sched._ages["builds"]["slide"] == 0
    assert sched._ages["exits"]["wink"] == 0
    assert sched._ages["builds"]["wink"] != 0
