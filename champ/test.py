# import os, mysql.connector
# conn = mysql.connector.connect(
#     host=os.getenv("MYSQL_HOST","10.173.222.60"),
#     port=int(os.getenv("MYSQL_PORT","3306")),
#     database=os.getenv("MYSQL_DB","Physiochamp"),
#     user=os.getenv("MYSQL_USER","rag_user"),
#     password=os.getenv("MYSQL_PASSWORD","root"),
# )
# cur = conn.cursor()
# cur.execute("SELECT 1")
# print("Result:", cur.fetchone())
# conn.close()
# print("MySQL connection OK")


# import os; print("LLM_MODEL:", os.getenv("LLM_MODEL")); print("GEMINI_API_KEY set:", bool(os.getenv("GEMINI_API_KEY")))

# import os
# from champ.llm.provider import call_llm_text
# print("API set:", bool(os.getenv("GEMINI_API_KEY")))
# try:
#     out = call_llm_text("You are a test model.", "Reply with OK.")
#     print("LLM reply:", out)
# except Exception as e:
#     print("LLM call failed:", e)

import os
print("GEMINI_API_KEY set (app):", bool(os.getenv("GEMINI_API_KEY")))
print("LLM_MODEL (app):", os.getenv("LLM_MODEL"))