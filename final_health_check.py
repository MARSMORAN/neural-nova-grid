import sqlite3
c = sqlite3.connect('grid_memory.db')
p = c.execute("SELECT COUNT(*) FROM queue WHERE status='pending'").fetchone()[0]
pr = c.execute("SELECT COUNT(*) FROM queue WHERE status='processing'").fetchone()[0]
r = c.execute("SELECT COUNT(*) FROM results").fetchone()[0]
best = c.execute("SELECT MIN(score) FROM results").fetchone()[0]

print(f"--- SWARM LIVE TELEMETRY ---")
print(f"Pending Generation-2: {p}")
print(f"Currently in 3D Physics Simulation: {pr}")
print(f"Total Completed Hits: {r}")
print(f"Current Global Record: {best:.4f} kcal/mol")
print(f"-----------------------------")
