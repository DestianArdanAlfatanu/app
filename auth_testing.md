# Auth Testing Playbook

1. MongoDB: `db.users.find({role:"owner"})` — password_hash starts with `$2b$`; unique index on users.email.
2. API:
```
curl -c cookies.txt -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{"email":"owner@lpk.id","password":"owner123"}'
curl -b cookies.txt $API/api/auth/me
curl -H "Authorization: Bearer <token>" $API/api/auth/me
```
3. Wrong password 5x → 429 lockout 15 minutes.
4. Role check: finance user GET /api/employees write → 403; guru POST /api/payments → 403.
