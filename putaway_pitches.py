from pybaseball import statcast
import pandas as pd


# ==========================================
# SETTINGS
# ==========================================

START_DATE = "2026-03-01"
END_DATE = "2026-08-07"


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
# AVAILABLE PITCH TYPES
# ==========================================

print()
print("=" * 70)
print("REGULAR SEASON PITCH TYPES")
print("=" * 70)

pitch_types = (
    data["pitch_type"]
    .value_counts(dropna=False)
    .reset_index()
)

pitch_types.columns = ["pitch_type", "pitches"]

print(pitch_types.to_string(index=False))


# ==========================================
# PITCH TYPES FOUND
# ==========================================

print()
print("=" * 70)
print("PITCH TYPES FOUND")
print("=" * 70)

unique_pitch_types = sorted(
    data["pitch_type"]
    .dropna()
    .unique()
)

print(", ".join(unique_pitch_types))
