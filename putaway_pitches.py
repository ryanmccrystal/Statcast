from pybaseball import statcast
import pandas as pd


# ==========================================
# SETTINGS
# ==========================================

START_DATE = "2026-03-01"
END_DATE = "2026-08-07"

# Statcast pitch type
PITCH_TYPE = "FF"

# Temporary minimum for testing
MIN_TWO_STRIKE_PITCHES = 100


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
# REGULAR SEASON ONLY
# ==========================================

data = data[
    data["game_type"] == "R"
].copy()

print(f"Regular-season pitches: {len(data):,}")


# ==========================================
# FOUR-SEAM FASTBALLS
# ==========================================

four_seam = data[
    data["pitch_type"] == PITCH_TYPE
].copy()

print(f"Four-seam fastballs: {len(four_seam):,}")


# ==========================================
# TWO-STRIKE FOUR-SEAM FASTBALLS
# ==========================================

two_strike_ff = four_seam[
    four_seam["strikes"] == 2
].copy()

print(f"Two-strike four-seam fastballs: {len(two_strike_ff):,}")


# ==========================================
# BUILD LEADERBOARD
# ==========================================

leaderboard = (
    two_strike_ff
    .groupby(["pitcher", "player_name"])
    .agg(
        two_strike_pitches=("pitch_type", "size"),
        strikeouts=(
            "events",
            lambda x: x.isin(
                ["strikeout", "strikeout_double_play"]
            ).sum()
        )
    )
    .reset_index()
)


# ==========================================
# CALCULATE PUTAWAY RATE
# ==========================================

leaderboard["putaway_rate"] = (
    leaderboard["strikeouts"]
    / leaderboard["two_strike_pitches"]
)


# ==========================================
# MINIMUM SAMPLE SIZE
# ==========================================

leaderboard = leaderboard[
    leaderboard["two_strike_pitches"] >= MIN_TWO_STRIKE_PITCHES
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
print("FOUR-SEAM FASTBALL PUTAWAY RATE")
print("=" * 70)

print(
    leaderboard[
        [
            "player_name",
            "two_strike_pitches",
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
