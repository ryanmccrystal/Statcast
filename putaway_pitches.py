from pybaseball import statcast
import pandas as pd
import json
import math
from datetime import datetime, timezone


# ==========================================
# SETTINGS
# ==========================================

START_DATE = "2026-03-01"
END_DATE = "2026-08-07"

# League leaderboard qualification:
# 50 two-strike pitches per 162 team games
# Overall
OVERALL_PITCHES_PER_162_GAMES = 50

# League leaderboard qualification:
# 40 two-strike pitches per 162 team games
# RHB/LHB splits
SPLIT_PITCHES_PER_162_GAMES = 40

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
# AVAILABLE PITCH TYPES
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
# HELPER: TEAM GAMES
# ==========================================

def calculate_team_games(teams):

    return sum(
        team_game_counts.get(team, 0)
        for team in teams
    )


# ==========================================
# BUILD QUALIFIED LEADERBOARD
# ==========================================

def build_leaderboard(
    pitch_data,
    pitches_per_162_games
):

    # --------------------------------------
    # TWO-STRIKE PITCHES
    # --------------------------------------

    two_strike = pitch_data[
        pitch_data["strikes"] == 2
    ].copy()

    if len(two_strike) == 0:
        return []


    # --------------------------------------
    # BUILD PITCHER LEADERBOARD
    # --------------------------------------

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
    # TEAM GAMES
    # --------------------------------------

    leaderboard["team_games"] = (
        leaderboard["teams"]
        .apply(calculate_team_games)
    )


    # --------------------------------------
    # QUALIFICATION
    # --------------------------------------

    leaderboard[
        "minimum_two_strike_pitches"
    ] = (
        leaderboard["team_games"]
        / 162
        * pitches_per_162_games
    ).apply(math.ceil)


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

            "player_id": int(
                row["pitcher"]
            ),

            "player_name": row[
                "player_name"
            ],

            "teams": row[
                "teams"
            ],

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

    return players


# ==========================================
# BUILD INDIVIDUAL PITCHER DATA
# ==========================================

def build_individual_pitchers(
    pitch_data
):

    # Only two-strike pitches are relevant
    two_strike = pitch_data[
        pitch_data["strikes"] == 2
    ].copy()

    if len(two_strike) == 0:
        return {}


    pitchers = {}


    # --------------------------------------
    # SPLITS
    # --------------------------------------

    splits = {

        "overall": two_strike,

        "vs_rhb": two_strike[
            two_strike["stand"] == "R"
        ],

        "vs_lhb": two_strike[
            two_strike["stand"] == "L"
        ]
    }


    # --------------------------------------
    # PROCESS EACH SPLIT
    # --------------------------------------

    for split_name, split_data in splits.items():

        if len(split_data) == 0:
            continue


        # Total two-strike pitches for
        # each pitcher in this split

        pitcher_totals = (
            split_data
            .groupby("pitcher")
            .size()
            .to_dict()
        )


        # ----------------------------------
        # PITCHER + PITCH TYPE
        # ----------------------------------

        grouped = (
            split_data
            .groupby(
                [
                    "pitcher",
                    "player_name",
                    "pitch_type"
                ]
            )
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


        # ----------------------------------
        # BUILD PITCHER RECORDS
        # ----------------------------------

        for _, row in grouped.iterrows():

            pitcher_id = int(
                row["pitcher"]
            )

            if pitcher_id not in pitchers:

                pitchers[pitcher_id] = {

                    "player_name":
                        row["player_name"],

                    "teams":
                        [],

                    "overall": [],

                    "vs_rhb": [],

                    "vs_lhb": []
                }


            # ----------------------------------
            # ADD TEAMS
            # ----------------------------------

            for team in row["teams"]:

                if team not in pitchers[
                    pitcher_id
                ]["teams"]:

                    pitchers[
                        pitcher_id
                    ]["teams"].append(team)


            # ----------------------------------
            # CALCULATE USAGE
            # ----------------------------------

            total_two_strike_pitches = (
                pitcher_totals[
                    pitcher_id
                ]
            )

            usage = (
                row["two_strike_pitches"]
                /
                total_two_strike_pitches
            )


            # ----------------------------------
            # CALCULATE PUTAWAY RATE
            # ----------------------------------

            if row["two_strike_pitches"] > 0:

                putaway_rate = (
                    row["strikeouts"]
                    /
                    row["two_strike_pitches"]
                )

            else:

                putaway_rate = 0


            # ----------------------------------
            # ADD PITCH
            # ----------------------------------

            pitch_record = {

                "pitch_type":
                    row["pitch_type"],

                "pitch_name":
                    PITCH_TYPE_NAMES.get(
                        row["pitch_type"],
                        row["pitch_type"]
                    ),

                "usage": round(
                    float(usage),
                    4
                ),

                "two_strike_pitches":
                    int(
                        row[
                            "two_strike_pitches"
                        ]
                    ),

                "strikeouts":
                    int(
                        row["strikeouts"]
                    ),

                "putaway_rate": round(
                    float(
                        putaway_rate
                    ),
                    4
                )
            }


            pitchers[
                pitcher_id
            ][split_name].append(
                pitch_record
            )


    # --------------------------------------
    # SORT PITCHES BY USAGE
    # --------------------------------------

    for pitcher in pitchers.values():

        for split in [
            "overall",
            "vs_rhb",
            "vs_lhb"
        ]:

            pitcher[split].sort(
                key=lambda x:
                    x["usage"],
                reverse=True
            )

        pitcher["teams"].sort()


    return pitchers


# ==========================================
# BUILD LEAGUE LEADERBOARDS
# ==========================================

all_pitch_types = {}


for pitch_type in available_pitch_types:

    pitch_name = PITCH_TYPE_NAMES.get(
        pitch_type,
        pitch_type
    )

    print()
    print("=" * 70)
    print(
        f"Processing {pitch_type} - {pitch_name}"
    )
    print("=" * 70)


    pitch_data = data[
        data["pitch_type"] == pitch_type
    ].copy()


    # --------------------------------------
    # OVERALL
    # --------------------------------------

    overall_players = build_leaderboard(
        pitch_data,
        OVERALL_PITCHES_PER_162_GAMES
    )

    print(
        f"Overall qualified pitchers: "
        f"{len(overall_players)}"
    )


    # --------------------------------------
    # VS RHB
    # --------------------------------------

    vs_rhb = pitch_data[
        pitch_data["stand"] == "R"
    ].copy()

    rhb_players = build_leaderboard(
        vs_rhb,
        SPLIT_PITCHES_PER_162_GAMES
    )

    print(
        f"vs RHB qualified pitchers: "
        f"{len(rhb_players)}"
    )


    # --------------------------------------
    # VS LHB
    # --------------------------------------

    vs_lhb = pitch_data[
        pitch_data["stand"] == "L"
    ].copy()

    lhb_players = build_leaderboard(
        vs_lhb,
        SPLIT_PITCHES_PER_162_GAMES
    )

    print(
        f"vs LHB qualified pitchers: "
        f"{len(lhb_players)}"
    )


    # --------------------------------------
    # STORE PITCH TYPE
    # --------------------------------------

    all_pitch_types[
        pitch_type.lower()
    ] = {

        "name": pitch_name,

        "statcast_code": pitch_type,

        "overall": overall_players,

        "vs_rhb": rhb_players,

        "vs_lhb": lhb_players
    }


# ==========================================
# BUILD INDIVIDUAL PITCHER DATA
# ==========================================

print()
print("=" * 70)
print("BUILDING INDIVIDUAL PITCHER DATA")
print("=" * 70)

individual_pitchers = (
    build_individual_pitchers(data)
)

print(
    f"Individual pitchers: "
    f"{len(individual_pitchers)}"
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

        "overall_two_strike_pitches_per_162_games":
            OVERALL_PITCHES_PER_162_GAMES,

        "split_two_strike_pitches_per_162_games":
            SPLIT_PITCHES_PER_162_GAMES
    },

    "pitch_types":
        all_pitch_types,

    "pitchers":
        individual_pitchers
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
    f"Individual pitchers: "
    f"{len(individual_pitchers)}"
)

print(
    f"File: {OUTPUT_FILE}"
)
