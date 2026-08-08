from pybaseball import statcast
import pandas as pd
import json
from datetime import datetime, timezone


# ==========================================
# SETTINGS
# ==========================================

START_DATE = "2026-03-01"
END_DATE = "2026-08-07"

# Statcast pitch type
PITCH_TYPE = "FF"

# Qualification requirement:
# 1.0 two-strike pitch of this type per team game
PITCHES_PER_TEAM_GAME = 1.0

OUTPUT_FILE = "putaway_pitches.json"


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
# COUNT TEAM GAMES
# ==========================================

home_games = data[
    ["game_pk", "home_team"]
].rename(
    columns={"home_team": "team"}
)

away_games = data[
    ["game_pk", "away_team"]
].rename(
    columns={"away_team": "team"}
)

team_games = pd.concat(
    [home_games, away_games]
).drop_duplicates()

team_game_counts = (
    team_games
    .groupby("team")["game_pk"]
    .nunique()
    .to_dict()
)


# ==========================================
# FOUR-SEAM FASTBALLS
# ==========================================

pitch_data = data[
    data["pitch_type"] == PITCH_TYPE
].copy()

print(f"Four-seam fastballs: {len(pitch_data):,}")


# ==========================================
# TWO-STRIKE FOUR-SEAM FASTBALLS
# ==========================================

two_strike = pitch_data[
    pitch_data["strikes"] == 2
].copy()

print(
    f"Two-strike four-seam fastballs: "
    f"{len(two_strike):,}"
)


# ==========================================
# IDENTIFY PITCHER'S TEAM
# ==========================================

two_strike["pitching_team"] = two_strike.apply(
    lambda row:
        row["home_team"]
        if row["inning_topbot"] == "Top"
        else row["away_team"],
    axis=1
)


# ==========================================
# BUILD PITCHER LEADERBOARD
# ==========================================

leaderboard = (
    two_strike
    .groupby(["pitcher", "player_name"])
    .agg(
        two_strike_pitches=("pitch_type", "size"),

        strikeouts=(
            "events",
            lambda x: x.isin(
                ["strikeout", "strikeout_double_play"]
            ).sum()
        ),

        teams=(
            "pitching_team",
            lambda x: sorted(x.dropna().unique())
        )
    )
    .reset_index()
)


# ==========================================
# CALCULATE TEAM GAMES
# ==========================================

def calculate_team_games(teams):
    return sum(
        team_game_counts.get(team, 0)
        for team in teams
    )


leaderboard["team_games"] = leaderboard["teams"].apply(
    calculate_team_games
)


# ==========================================
# QUALIFICATION THRESHOLD
# ==========================================

leaderboard["minimum_two_strike_pitches"] = (
    leaderboard["team_games"]
    * PITCHES_PER_TEAM_GAME
)


# ==========================================
# QUALIFY PITCHERS
# ==========================================

leaderboard = leaderboard[
    leaderboard["two_strike_pitches"]
    >= leaderboard["minimum_two_strike_pitches"]
].copy()


# ==========================================
# CALCULATE PUTAWAY RATE
# ==========================================

leaderboard["putaway_rate"] = (
    leaderboard["strikeouts"]
    / leaderboard["two_strike_pitches"]
)


# ==========================================
# SORT
# ==========================================

leaderboard = leaderboard.sort_values(
    "putaway_rate",
    ascending=False
)


# ==========================================
# CREATE JSON DATA
# ==========================================

players = []

for _, row in leaderboard.iterrows():

    players.append({
        "player_id": int(row["pitcher"]),
        "player_name": row["player_name"],
        "teams": row["teams"],
        "team_games": int(row["team_games"]),
        "two_strike_pitches": int(row["two_strike_pitches"]),
        "strikeouts": int(row["strikeouts"]),
        "putaway_rate": round(
            float(row["putaway_rate"]),
            4
        )
    })


# ==========================================
# FINAL JSON
# ==========================================

output = {
    "last_updated": datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ"),

    "season": 2026,

    "season_type": "regular",

    "qualification": {
        "minimum_two_strike_pitches_per_team_game":
            PITCHES_PER_TEAM_GAME
    },

    "pitch_types": {

        "four_seam": {

            "name": "Four-Seam Fastball",

            "statcast_code": "FF",

            "players": players
        }
    }
}


# ==========================================
# WRITE JSON
# ==========================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        output,
        f,
        indent=2,
        ensure_ascii=False
    )


print()
print("=" * 70)
print("JSON CREATED")
print("=" * 70)
print(f"File: {OUTPUT_FILE}")
print(f"Qualified pitchers: {len(players)}")
