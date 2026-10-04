# Review notes and changes

## Bugs fixed
1. **Double-click protection did not actually work.** The frontend made a new random
   idempotency key on every click, so Redis saw two different requests. Now one key is
   made per transfer attempt, the button is disabled while sending, and the backend replays
   the original result for a repeated key.
2. Idempotency key became a 500 error after 60 seconds (DB unique constraint). Now the DB
   is checked first, an IntegrityError returns 409, and the response is cached for 24h.
3. `crypto.randomUUID()` crashes on plain HTTP pages. Added a fallback.
4. Redis outage now returns 503 (fail closed) instead of moving money unprotected.
5. Raw exception text was returned to users on errors. Now a generic message.
6. Bad or non-UUID tokens caused 500. Now 401.
7. Duplicate email on /register caused 500. Now 409; basic email/password validation added.
8. Frozen accounts could send or receive. Now blocked.
9. Redis idempotency key now includes the user id so users cannot collide.

## Improvements
- Recipient is entered as an account number (e.g. 456) instead of a UUID.
- Removed duplicate psycopg dependency, normalised CRLF line endings.
- Added pytest suite (duplicate click, insufficient funds, wrong owner, retry, auth).
- Removed Vercel/Render/Upstash settings; AWS is now the only deployment target (frontend calls /api on the same origin).
- Added production compose + nginx + Terraform: CloudFront (HTTPS) in front of one EC2 running the stack, only port 80 exposed. Console-only option via user-data.sh.
- Page title and a clear error message if the account fails to load.
