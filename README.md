# DriveBook – Driving Lesson Booking Application

Raj Instructor is a full-stack driving-school portal for Auckland. It includes an SEO-ready public landing page, distinct learner and instructor workspaces, online booking, structured progress reports, Stripe Checkout and transactional notifications.

## Included features

- Separate learner and instructor registration with JWT authentication
- Instructor role and instructor profile fields for photo, expertise, services, vehicle, language and teaching area
- Instructor-managed availability, protected booking holds and one-click lesson booking
- Stripe Checkout integration for real payments, plus a safe `demo` payment mode for local/client demos
- Booking history and payment/booking statuses
- Instructor feedback workflow after lessons
- Structured 1–10 skill metrics grouped into introduction, intermediate and advanced driving skills
- Lesson-by-lesson feedback pagination. A page exists for each booked lesson even before feedback has been submitted
- Registration, booking, payment, student lesson-reminder and instructor feedback-reminder email flows
- In-app notifications with deep links to the relevant booking/feedback page
- WebSocket notification delivery for real-time UI updates
- Light/white theme only
- Docker Compose for local setup

## Quick start

Prerequisites: Docker Desktop / Docker Engine + Docker Compose.

```bash
docker compose up --build
```

Then seed demo data:

```bash
curl -X POST http://localhost:8000/dev/seed
```

Open `http://localhost:3000`.

Demo users:

- Learner: `student@example.com` / `Password123!`
- Instructor: `instructor@example.com` / `Password123!`

## Demo flow

1. Sign in as the learner.
2. Select the instructor and book one of the seeded slots.
3. In `PAYMENTS_MODE=demo`, payment is immediately treated as successful and the booking becomes confirmed.
4. Sign out and sign in as the instructor.
5. Open **Instructor tools**, select the learner's lesson, fill the summary, practice plan and 1–10 skill ratings, then submit.
6. Sign back in as the learner. The notification appears in-app and the feedback page is available in the paginated history.

## Real Stripe payments

Set the backend environment variables:

```env
PAYMENTS_MODE=stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
FRONTEND_URL=https://your-frontend-domain
```

Configure a Stripe webhook to call:

```text
POST https://your-api-domain/payments/stripe/webhook
```

Subscribe to `checkout.session.completed`. Keep the webhook signing secret private.

The webhook handler records Stripe event IDs so Stripe retries are idempotent. Do not confirm a payment from the browser redirect; Stripe's signed webhook is the source of truth.

For local Stripe testing, Stripe CLI can forward events to `localhost:8000/payments/stripe/webhook`.

## Email

Local mode uses `SMTP_MODE=console`. For production:

```env
SMTP_MODE=smtp
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM=lessons@yourdomain.com
```

To run scheduled reminders, set a long random `REMINDER_SECRET`, then have a trusted scheduler call this endpoint at least every hour:

```text
POST https://your-api-domain/internal/reminders/run
X-Reminder-Secret: <REMINDER_SECRET>
```

The endpoint sends one student reminder within the configured pre-lesson window and one instructor reminder after a confirmed lesson ends. Each delivery is recorded so scheduled retries do not send duplicates.

## Database migrations

The backend image runs `alembic upgrade head` before serving traffic. For an existing starter database that was created before migrations, back it up, then either migrate it through an approved compatibility migration or stamp the matching initial revision only after confirming its schema. Do not use `create_all` in production.

## Production deployment

### Vercel deployment

Deploy two Vercel projects from this repository:

- The existing frontend project has **Root Directory** `frontend`.
- Create a backend project with **Root Directory** `backend`; Vercel detects the FastAPI `main.py` entrypoint.

Attach a Vercel Marketplace Postgres integration (for example Neon) to the backend project, then configure the following backend Production environment variables:

```env
# Set by the Postgres integration, or provide the database connection yourself.
POSTGRES_URL=postgresql://...
JWT_SECRET=<long-random-value>
FRONTEND_URL=https://your-frontend-domain.vercel.app
CORS_ORIGINS=https://your-frontend-domain.vercel.app
REMINDER_SECRET=<long-random-value>
SMTP_MODE=smtp
SMTP_HOST=...
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM=...
```

Set the following frontend Production environment values after the backend is deployed:

```env
NEXT_PUBLIC_API_URL=https://your-backend-domain.vercel.app
```

The frontend uses normal HTTP API requests in production. On Vercel Hobby, configure a Supabase Cron job that invokes the reminder route hourly using the value in Supabase Vault; do not store the secret directly in the cron command.

Run Alembic migrations against the production database before the first deployment. Back up an existing database first; the Vercel build does not run migrations.

A practical split is:

- Frontend: any Next.js host
- Backend: any container host with a scheduler/cron capability
- Database: managed PostgreSQL

Set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` on the frontend to the public backend URLs. Set `CORS_ORIGINS` on the backend to your frontend origin. Use a strong random `JWT_SECRET`, real Stripe keys/webhook secret, SMTP credentials, and a `REMINDER_SECRET`. Never set `NEXT_PUBLIC_DEMO_MODE=true` in production.

For a single-server deployment, both Docker images can be deployed behind a reverse proxy such as Caddy or Nginx, with PostgreSQL either managed or containerized.

## Client handover checklist

- Replace the `DriveBook` name with the client's brand
- Replace `/public/instructor-placeholder.svg` with real instructor images or image URLs
- Edit instructor details in the database or add an admin profile editor
- Add the client's Stripe account and webhook secret
- Configure production SMTP
- Add Privacy Policy, Terms and cancellation/refund rules agreed with the client
- Add database backups and observability
- Rotate all secrets before handover

## Important implementation notes

The UI and copy are original. The reference driving-school website was used only to understand common information architecture such as instructor discovery, booking management and lesson/service presentation. Do not copy third-party logos, photos or proprietary text without permission.

The feedback model is based on the supplied lesson-progress report structure: lesson summary, agreed practice, further notes, and 1–10 ratings across introductory, intermediate and advanced driving skills. It is implemented as structured JSON so the client can add or remove metrics later without changing the database schema.

## Validation included

The backend modules are Python syntax-checked, a basic FastAPI health test is included under `backend/tests`, and the Docker setup keeps the frontend/backend/database configuration together. Run the full verification locally with:

```bash
cd backend && pytest
cd ../frontend && npm install && npm run build
```
