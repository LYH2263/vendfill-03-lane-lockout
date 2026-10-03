import os
import tempfile

# Tests run against an isolated SQLite file, never the configured dev/prod DB.
_DB_DIR = tempfile.mkdtemp(prefix="vendfill_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
os.environ["SEED_ON_EMPTY"] = "false"
