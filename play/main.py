import datetime
from sqlalchemy.exc import SQLAlchemyError

# Adjust these imports if your folder structure is slightly different
from database.models import Match, Pair, God, ResultType
from database.postgres.postgres_interface import get_engine, get_pg_mappings, store_match_pg


def main():
    print("Connecting to database...")
    engine = get_engine()

    try:
        gods_map, engines_map = get_pg_mappings(engine)
    except Exception as e:
        print(f"Failed to fetch mappings. Check your DB connection. Error: {e}")
        return

    print("Mappings fetched successfully.")

    # Grab the first available engine name from your DB to ensure foreign keys match
    if not engines_map:
        print("Error: No engines found in tb_engines!")
        return
    sample_engine = list(engines_map.keys())[0]

    dummy_match = Match(
        game_id=1_000_000,
        starting_pos="0N0N0N0G0G0B0B0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0000",
        players=(
            Pair(engine=sample_engine, god=God.APOLLO),
            Pair(engine=sample_engine, god=God.ARTEMIS)
        ),
        time_ms=(10000, 10000),
        winner=True,
        result_type=ResultType.NORMAL_WIN,
        played_at=datetime.datetime.now(),
        moves=[]
    )

    print("\nAttempting to execute store_match_pg...")
    with engine.connect() as conn:
        with conn.begin():
            store_match_pg(conn, dummy_match, gods_map, engines_map)

        print("\n✅ SUCCESS: The insert query ran without errors!")


if __name__ == '__main__':
    main()