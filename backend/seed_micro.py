"""Micro-run: login + accounts + employees only, using real phase functions."""
import seed_demo_data as S

S.phase_login()
S.phase_accounts()
S.phase_employees()

from pymongo import MongoClient
import os
d = MongoClient(os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017"))[
    os.environ.get("DB_NAME", "lpk")]
print("MICRO RESULT accounts:", d.accounts.count_documents({}),
      "employees:", d.employees.count_documents({}))
