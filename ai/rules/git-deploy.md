# Git Deploy Rules

## Before deploy:
- Check current branch
- Check uncommitted changes
- Check latest CI status
- Confirm target environment

## Forbidden:
- direct push to main
- deploy with failing tests
- deploy without rollback path
