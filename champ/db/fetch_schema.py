import mysql.connector

# Connect to MySQL
conn = mysql.connector.connect(
    host="10.171.28.60",
    user="rag_user",
    password="root",
    database="Physiochamp"
)
cursor = conn.cursor()

# Fetch schema
cursor.execute("""
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'Physiochamp'
ORDER BY TABLE_NAME, ORDINAL_POSITION;
""")

# Save to file
with open("schema.txt", "w") as f:
    for row in cursor.fetchall():
        f.write("\t".join([str(x) if x is not None else "" for x in row]) + "\n")

cursor.close()
conn.close()
print("Schema saved to schema.txt")
