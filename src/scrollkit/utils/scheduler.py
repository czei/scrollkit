# Copyright (c) 2024-2026 Michael Czeiszperger
"""ActScheduler: weighted-age, family-aware picking for 24/7 variety.

For signs that run unattended, randomness alone repeats itself: the same
act twice running reads as a bug. This scheduler draws from "decks" of
tagged material so that (a) nothing whose visual family the caller has
just used is picked, and (b) the least-recently-seen material surfaces
first — every entry's weight is ``(acts since last seen + 1)^2``, and
new entries start old, so fresh material leads.

Deck entries are any sequences whose first two items are ``(name,
family, ...)`` — typically ``(name, family, callable)``. Ages are kept
per ``deck_key``, so one scheduler instance can serve independent decks
(builds, treatments, exits, layouts...).

CircuitPython-safe: only ``random.random()``. Promoted from the DarkOwl
LED logo app (2026), where it schedules a 14-build / 15-treatment /
9-exit show across four logo layouts.
"""

import random

__all__ = ["ActScheduler"]


class ActScheduler:
    """Weighted-age no-repeat picker over tagged decks."""

    AGE_CAP = 20        # ages saturate here (weight stops growing)
    NEW_AGE = 12        # unseen entries start this old, so they lead

    def __init__(self):
        self._ages = {}                     # deck_key -> {name: age}

    def pick(self, deck, deck_key, avoid=(), force=None):
        """Draw one entry from ``deck``.

        Entries whose family is in ``avoid`` are excluded (falling back
        to the whole deck if that excludes everything). ``force`` names
        an entry to pick outright — with the same age bookkeeping, so a
        forced opener still counts as just-played. Every other entry
        ages by one (capped); the chosen entry's age resets to zero.
        """
        ages = self._ages.setdefault(deck_key, {})
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
                age = min(ages.get(e[0], self.NEW_AGE), self.AGE_CAP)
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
            ages[e[0]] = min(ages.get(e[0], self.NEW_AGE) + 1, self.AGE_CAP)
        ages[chosen[0]] = 0
        return chosen
