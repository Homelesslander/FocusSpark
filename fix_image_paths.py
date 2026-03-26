import sqlite3

# Connect to database
conn = sqlite3.connect('adhd_app.db')
cursor = conn.cursor()

# Check current paths
print("BEFORE FIX:")
cursor.execute('SELECT id, title, image_path FROM visual_task_cards')
rows = cursor.fetchall()
print('ID | Title | Image Path')
print('-' * 50)
for row in rows:
    print(f'{row[0]} | {row[1]} | {row[2]}')

# Fix the paths
cursor.execute('UPDATE visual_task_cards SET image_path = REPLACE(image_path, "/static/", "") WHERE image_path LIKE "/static/%"')
conn.commit()

# Check after fix
print("\nAFTER FIX:")
cursor.execute('SELECT id, title, image_path FROM visual_task_cards')
rows = cursor.fetchall()
print('ID | Title | Image Path')
print('-' * 50)
for row in rows:
    print(f'{row[0]} | {row[1]} | {row[2]}')

conn.close()
print("\nDatabase fixed!")
