# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django 5.0.7 REST API backend for NPU (Nakhon Pathom University). Serves as a multi-functional platform integrating authentication, user management, library systems, IoT controls, and room reservations. Deployed on IIS (Windows) via FastCGI with Python 3.12.

## Common Commands

```bash
# Development server
python manage.py runserver

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Collect static files (required before deployment)
python manage.py collectstatic

# Admin user creation
python manage.py createsuperuser
```

There are no automated tests in this project.

## Architecture

### Dual API Versioning

The project maintains two parallel API versions in `apiapp/`:

- **V1 (Legacy):** Session-based auth. ViewSets in `views.py`, serializers in `serializer.py`. Routes registered under `/api/`, `/std-info/`, `/auth-ldap/`, `/staff-info/`, `/walai/`, `/mt/`, `/sonoff/`.
- **V2 (Modern):** JWT Bearer token auth. ViewSets in `views_v2.py`, serializers in `serializers_v2.py`. All routes prefixed with `/v2/`. Token endpoints at `/v2/token/` and `/v2/token/refresh/`.

Both versions are registered in `apiproject/urls.py` using DRF `DefaultRouter`.

### Authentication Pattern

`apiapp/authentication.py` defines two mixins used on V2 ViewSets:
- `JWTRequiredAuthentication` — protects endpoints, validates Bearer tokens
- `PublicEndpointAuthentication` — skips auth for login/token endpoints

JWT tokens have a 365-day access lifetime (configured in `settings.py`).

### Database Models

`StudentsInfo` and `StaffInfo` are **read-only** (`managed=False`) models that map to existing university database tables. `UserProfile` is the only writable Django-managed model.

### ReservApp

`reservapp/` handles room reservations and LINE OA integration. It uses **Google Sheets as a backend** (via `gspread`) instead of Django models — no database tables. Room-to-spreadsheet mappings are hardcoded in `reservapp/views.py`. Templates are in `reservapp/templates/reservapp/`.

### External Integrations

| Service | Purpose | Location |
|---|---|---|
| Active Directory (LDAP3) | User authentication, `NPU.local` domain | `views.py` / `views_v2.py` `auth_ldap` actions |
| MikroTik RouterOS API | Hotspot user management | `views.py` / `views_v2.py` MikroTik ViewSets |
| Home Assistant REST API | IoT device control (lights, AC, projectors) | `views_v2.py` `SonoffControlViewSetV2` |
| Walai Library API | Library membership check | `views.py` / `views_v2.py` Walai ViewSets |
| Google Sheets (gspread) | Room reservation storage | `reservapp/views.py` |

### Settings & Configuration

- Main settings: `apiproject/settings.py`
- Credentials are loaded from `.env` (database, MikroTik, Home Assistant token, Walai token)
- `apiproject/settings27062025.py` and `apiproject/settings 21032568.py` are backup files — do not use
- CORS allowed origins are explicitly listed in `settings.py` (includes production domains `api.npu.ac.th`, `rdb.npu.ac.th`, `arc.npu.ac.th`)
- Static files served via WhiteNoise middleware; collected to `/static/`
- Response timing logged via custom middleware in `apiproject/middleware.py`
