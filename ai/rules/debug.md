# Debug Rules

## If error like:
- server unavailable
- timeout
- 5xx
- no response

## ALWAYS check first:

1. git push
2. GitHub Actions status
3. VPS availability
4. docker containers (docker ps)
5. API health endpoint (/health)

## Only AFTER that:
-> analyze code

## Forbidden:
- guessing fixes
- changing logic without root cause
