import sqlite3
c = sqlite3.connect('grid_memory.db')
q = c.execute("SELECT count(1) FROM queue").fetchone()[0]
r = c.execute("SELECT count(1) FROM results").fetchone()[0]
print(f"Queue: {q}")
print(f"Results: {r}")
