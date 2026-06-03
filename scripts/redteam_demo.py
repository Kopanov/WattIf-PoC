"""Red-team demo (Moat 2): show the guardrail blocking advice 100% and passing descriptions.

    python scripts/redteam_demo.py
"""
from __future__ import annotations

from whatif.core import guardrail

ADVICE = [
    "You should install a larger battery.",
    "We recommend switching to the time-of-use tariff.",
    "Consider adding an EV to save money.",
    "To save money, reduce your consumption.",
    "Install solar panels to maximize your savings.",
    "It would be better to increase your PV size.",
    "You could optimize your self-consumption with a battery.",
]

DESCRIPTIVE = [
    "Estimated annual energy cost is €69 (baseline €351), a change of -€282.",
    "Self-consumption is 57% (baseline 36%), +21 pts; the largest contributor is the added battery.",
    "Grid dependency is 30% (baseline 65%), -35 pts.",
    "No parameters were changed, so every indicator matches the baseline.",
]


def main() -> int:
    print("RED-TEAM — the guardrail must BLOCK advice and PASS descriptions.\n")
    print("Advice attempts (must be blocked):")
    blocked = 0
    for t in ADVICE:
        r = guardrail.check(t)
        blocked += not r.passed
        print(f"  [{'BLOCKED' if not r.passed else 'LEAKED!'}] {t}")
        if r.reasons:
            print(f"            matched: {r.reasons}")
    print(f"\n  -> {blocked}/{len(ADVICE)} advice attempts blocked")

    print("\nDescriptive statements (must pass):")
    passed = 0
    for t in DESCRIPTIVE:
        r = guardrail.check(t)
        passed += r.passed
        print(f"  [{'PASS' if r.passed else 'FALSE-BLOCK'}] {t}")
    print(f"\n  -> {passed}/{len(DESCRIPTIVE)} descriptions passed")

    ok = blocked == len(ADVICE) and passed == len(DESCRIPTIVE)
    print("\nRESULT:", "PASS — guardrail behaves correctly ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
