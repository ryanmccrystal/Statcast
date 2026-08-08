from pybaseball import statcast
import pandas as pd


# ==========================================
# SETTINGS
# ==========================================

START_DATE = "2026-03-01"
END_DATE = "2026-08-07"

# Fastballs for this first version
FASTBALL_TYPES = ["FF", "SI", "FC"]


# ==========================================
# GET STATCAST DATA
# ==========================================

print("Downloading Statcast data...")
print(f"Date range: {START_DATE} through {END_DATE}")

data = statcast(
    start_dt=START_DATE,
    end_dt=END_DATE
)

print(f"Total pitches downloaded: {len(data):,}")


# ==========================================
# KEEP FASTBALLS
# ==========================================

fastballs = data[
    data["pitch_type"].isin(FASTBALL_TYPES)
].copy()

print(f"Fastballs: {len(fastballs):,}")


# ==========================================
# TWO-STRIKE FASTBALLS
# ==========================================

two_strike_fastballs = fastballs[
    fastballs["strikes"] == 2
].copy()

print(f"Two-strike fastballs: {len(two_strike_fastballs):,}")


# ==========================================
# BUILD LEADERBOARD
# ==========================================

leaderboard = (
    two_strike_fastballs
    .groupby(["pitcher", "player_name"])
    .agg(
        two_strike_fastballs=("pitch_type", "size"),
        strikeouts=("events", lambda x: (x == "strikeout").sum())
    )
    .reset_index()
)


# ==========================================
# CALCULATE PUTAWAY RATE
# ==========================================

leaderboard["putaway_rate"] = (
    leaderboard["strikeouts"]
    / leaderboard["two_strike_fastballs"]
)


# ==========================================
# MINIMUM SAMPLE SIZE
# ==========================================

# Temporary minimum for testing.
# We will decide the final minimum later.
MIN_TWO_STRIKE_FASTBALLS = 100

leaderboard = leaderboard[
    leaderboard["two_strike_fastballs"] >= MIN_TWO_STRIKE_FASTBALLS
].copy()


# ==========================================
# SORT
# ==========================================

leaderboard = leaderboard.sort_values(
    "putaway_rate",
    ascending=False
)


# ==========================================
# DISPLAY
# ==========================================

print()
print("=" * 70)
print("FASTBALL PUTAWAY RATE")
print("=" * 70)

print(
    leaderboard[
        [
            "player_name",
            "two_strike_fastballs",
            "strikeouts",
            "putaway_rate"
        ]
    ].to_string(
        index=False,
        formatters={
            "putaway_rate": lambda x: f"{x:.1%}"
        }
    )
)
