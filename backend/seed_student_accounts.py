"""Provision missing portal accounts; never reset existing credentials."""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))

from core import db, client, hash_password, new_id, now_iso
from pg_mongo import DuplicateKeyError


async def seed_student_accounts(database, password):
    if len(password) < 12:
        raise ValueError('STUDENT_SEED_PASSWORD must contain at least 12 characters')
    created = skipped = 0
    async for student in database.students.find({}):
        sid = student['id']
        if await database.users.find_one({'student_id': sid}):
            skipped += 1
            continue
        # Stable, unique login independent of missing/duplicate contact emails.
        email = f'siswa.{sid}@lpk.id'
        account = {
            'id': new_id(), 'name': student['nama_lengkap'], 'email': email,
            'role': 'student', 'student_id': sid, 'employee_id': None,
            'aktif': True, 'must_change_password': True,
            'password_hash': hash_password(password), 'created_at': now_iso(),
        }
        try:
            await database.users.insert_one(account)
            created += 1
        except DuplicateKeyError:
            if not await database.users.find_one({'student_id': sid}):
                raise
            skipped += 1
    return {'created': created, 'skipped': skipped}


async def main():
    try:
        await db.users.create_index('email', unique=True)
        await db.users.create_index('student_id', unique=True, sparse=True)
        print(await seed_student_accounts(db, os.environ['STUDENT_SEED_PASSWORD']))
    finally:
        await client.aclose()


if __name__ == '__main__':
    asyncio.run(main())
