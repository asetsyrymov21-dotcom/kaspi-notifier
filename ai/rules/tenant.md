# Tenant Rules

## Core invariant:
- Never remove, bypass, or guess tenant_id logic

## Before changing tenant-related code:
1. Identify where tenant_id enters the request
2. Identify where tenant_id is validated
3. Identify where tenant_id filters data access

## Forbidden:
- cross-tenant reads
- global queries without tenant filter
- default tenant assumptions without explicit source
