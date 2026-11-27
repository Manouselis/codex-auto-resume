"""Leave a hot rollback journal by stopping after spilling uncommitted pages."""
import os
import sqlite3
import sys

database = sqlite3.connect(sys.argv[1])
database.execute("PRAGMA cache_size=1")
database.execute("BEGIN IMMEDIATE")
database.execute("UPDATE meta SET value=? WHERE key='schema_version'", ("x" * 100000,))
# A normal close rolls back the transaction and removes the journal.
os._exit(0)
