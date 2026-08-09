from pybaseball import statcast
import pandas as pd
import json
from datetime import datetime, timezone


# ==========================================
# SETTINGS
# ==========================================

START_DATE = "2026-03-01"
END_DATE = "2026-08-07"

# Qualification requirement:
# 1.0 two-strike pitch of that specific type per team game
PITCHES_PER_TEAM_GAME = 1.0

OUTPUT_FILE = "putaway_pitches.json"


# ==========================================
# PITCH TYPE NAMES
# ==========================================

PITCH_TYPE_NAMES = {
    "FF": "Four-Seam Fastball",
    "SI": "Sinker",
    "SL": "Slider",
    "CH": "Changeup",
    "ST": "Sweeper",
    "FC": "Cutter",
    "CU": "Curveball",
    "FS": "Splitter",
    "KC": "Knuckle Curve",
    "SV": "Slurve",
    "EP": "Eephus",
    "FA": "Fastball",
    "FO": "Forkball",
    "KN": "Knuckleball",
    "CS": "Slow Curve",
    "SC": "Screwball",
    "PO": "Pitch Out",
    "UN": "Unknown",
}


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
# IDENTIFY PITCHER'S TEAM
# ==========================================

# Top of inning:
#   Away team is batting
#   Home team is pitching
#
# Bottom of inning:
#   Home team is batting
#   Away team is pitching

data["pitching_team"] = data.apply(
    lambda row:
        row["home_team"]
        if row["inning_topbot"] == "Top"
        else row["away_team"],
    axis=1
)


# ==========================================
# GET AVAILABLE PITCH TYPES
# ==========================================

available_pitch_types = sorted(
    data["pitch_type"]
    .dropna()
    .unique()
)


print()
print("Pitch types found:")
print(", ".join(available_pitch_types))


# ==========================================
# BUILD LEADERBOARDS
# ==========================================

all_pitch_types = {}


for pitch_type in available_pitch_types:

    print()
    print("=" * 70)
    print(
        f"Processing {pitch_type} - "
        f"{PITCH_TYPE_NAMES.get(pitch_type, pitch_type)}"
    )
    print("=" * 70)


    # --------------------------------------
    # KEEP THIS PITCH TYPE
    # --------------------------------------

    pitch_data = data[
        data["pitch_type"] == pitch_type
    ].copy()


    # --------------------------------------
    # TWO-STRIKE PITCHES
    # --------------------------------------

    two_strike = pitch_data[
        pitch_data["strikes"] == 2
    ].copy()


    print(
        f"Two-strike pitches: "
        f"{len(two_strike):,}"
    )


    # --------------------------------------
    # BUILD PITCHER LEADERBOARD
    # --------------------------------------

    if len(two_strike) == 0:
        all_pitch_types[pitch_type.lower()] = {
            "name": PITCH_TYPE_NAMES.get(
                pitch_type,
                pitch_type
            ),
            "statcast_code": pitch_type,
            "players": []
        }

        continue


    leaderboard = (
        two_strike
        .groupby(["pitcher", "player_name"])
        .agg(
            two_strike_pitches=(
                "pitch_type",
                "size"
            ),

            strikeouts=(
                "events",
                lambda x: x.isin(
                    [
                        "strikeout",
                        "strikeout_double_play"
                    ]
                ).sum()
            ),

            teams=(
                "pitching_team",
                lambda x:
                    sorted(
                        x.dropna().unique()
                    )
            )
        )
        .reset_index()
    )


    # --------------------------------------
    # CALCULATE TEAM GAMES
    # --------------------------------------

    def calculate_team_games(teams):

        return sum(
            team_game_counts.get(team, 0)
            for team in teams
        )


    leaderboard["team_games"] = (
        leaderboard["teams"]
        .apply(calculate_team_games)
    )


    # --------------------------------------
    # QUALIFICATION THRESHOLD
    # --------------------------------------

    leaderboard[
        "minimum_two_strike_pitches"
    ] = (
        leaderboard["team_games"]
        * PITCHES_PER_TEAM_GAME
    )


    # --------------------------------------
    # QUALIFY PITCHERS
    # --------------------------------------

    leaderboard = leaderboard[
        leaderboard["two_strike_pitches"]
        >=
        leaderboard[
            "minimum_two_strike_pitches"
        ]
    ].copy()


    # --------------------------------------
    # PUTAWAY RATE
    # --------------------------------------

    leaderboard["putaway_rate"] = (
        leaderboard["strikeouts"]
        /
        leaderboard["two_strike_pitches"]
    )


    # --------------------------------------
    # SORT
    # --------------------------------------

    leaderboard = leaderboard.sort_values(
        "putaway_rate",
        ascending=False
    )


    # --------------------------------------
    # CREATE JSON PLAYER LIST
    # --------------------------------------

    players = []


    for _, row in leaderboard.iterrows():

        players.append({
            "player_id": int(row["pitcher"]),

            "player_name": row[
                "player_name"
            ],

            "teams": row["teams"],

            "team_games": int(
                row["team_games"]
            ),

            "two_strike_pitches": int(
                row["two_strike_pitches"]
            ),

            "strikeouts": int(
                row["strikeouts"]
            ),

            "putaway_rate": round(
                float(
                    row["putaway_rate"]
                ),
                4
            )
        })


    # --------------------------------------
    # STORE PITCH TYPE
    # --------------------------------------

    all_pitch_types[
        pitch_type.lower()
    ] = {

        "name": PITCH_TYPE_NAMES.get(
            pitch_type,
            pitch_type
        ),

        "statcast_code": pitch_type,

        "players": players
    }


    print(
        f"Qualified pitchers: "
        f"{len(players)}"
    )


# ==========================================
# CREATE FINAL JSON
# ==========================================

output = {

    "last_updated": datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),

    "season": 2026,

    "season_type": "regular",

    "qualification": {

        "minimum_two_strike_pitches_per_team_game":
            PITCHES_PER_TEAM_GAME
    },

    "pitch_types": all_pitch_types
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


# ==========================================
# DONE
# ==========================================

print()
print("=" * 70)
print("JSON CREATED")
print("=" * 70)

print(
    f"Pitch types processed: "
    f"{len(all_pitch_types)}"
)

print(
    f"File: {OUTPUT_FILE}"
)
