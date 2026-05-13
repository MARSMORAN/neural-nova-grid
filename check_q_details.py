import sqlite3
c = sqlite3.connect('grid_memory.db')
pending = c.execute("SELECT count(1) FROM queue WHERE status='pending'").fetchone()[0]
processing = c.execute("SELECT count(1) FROM queue WHERE status='processing'").fetchone()[0]
print(f"Pending: {pending}, Processing: {processing}")
