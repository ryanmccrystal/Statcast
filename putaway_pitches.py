from pybaseball import statcast
import pandas as pd


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
# PITCH TYPE
# ==========================================

pitch_data = data[
    data["pitch_type"] == PITCH_TYPE
].copy()

print(f"Four-seam fastballs: {len(pitch_data):,}")


# ==========================================
# TWO-STRIKE PITCHES
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

# Top of inning:
#   Away team is batting
#   Home team is pitching
#
# Bottom of inning:
#   Home team is batting
#   Away team is pitching

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
# QUALIFY
# ==========================================

leaderboard = leaderboard[
    leaderboard["two_strike_pitches"]
    >= leaderboard["minimum_two_strike_pitches"]
].copy()


# ==========================================
# PUTAWAY RATE
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
# DISPLAY
# ==========================================

print()
print("=" * 100)
print("FOUR-SEAM FASTBALL PUTAWAY RATE")
print("=" * 100)

print(
    leaderboard[
        [
            "player_name",
            "two_strike_pitches",
            "strikeouts",
            "putaway_rate",
            "team_games",
            "minimum_two_strike_pitches"
        ]
    ].to_string(
        index=False,
        formatters={
            "putaway_rate": lambda x: f"{x:.1%}",
            "minimum_two_strike_pitches": lambda x: f"{x:.0f}"
        }
    )
)
