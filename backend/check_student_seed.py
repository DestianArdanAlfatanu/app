"""CI integration check. Run only against an empty disposable database."""
import asyncio
from seed_student_accounts import seed_student_accounts
from core import db, client, hash_password, verify_password

async def main():
    try:
        assert await db.students.count_documents({}) == 0, 'Use an empty CI database'
        await db.users.create_index('email', unique=True)
        await db.users.create_index('student_id', unique=True, sparse=True)
        await db.students.insert_many([
            {'id': 'ci-a', 'nama_lengkap': 'CI A'},
            {'id': 'ci-b', 'nama_lengkap': 'CI B'},
        ])
        assert await seed_student_accounts(db, 'Initial-test-123') == {'created': 2, 'skipped': 0}
        first = await db.users.find_one({'student_id': 'ci-a'})
        assert first['role'] == 'student' and first['must_change_password']
        assert verify_password('Initial-test-123', first['password_hash'])
        await db.users.update_one({'id': first['id']}, {'$set': {
            'password_hash': hash_password('Changed-test-456'),
            'must_change_password': False, 'aktif': False,
        }})
        assert await seed_student_accounts(db, 'Another-test-789') == {'created': 0, 'skipped': 2}
        after = await db.users.find_one({'id': first['id']})
        assert verify_password('Changed-test-456', after['password_hash'])
        assert not after['must_change_password'] and not after['aktif']
        assert await db.users.count_documents({}) == 2
        try:
            await seed_student_accounts(db, 'short')
        except ValueError:
            pass
        else:
            raise AssertionError('Weak seed password accepted')
        print('Student seed integration checks passed')
    finally:
        await client.aclose()

asyncio.run(main())
