# DriveBook – Driving Lesson Booking Application

DriveBook is a complete full-stack starter for a driving-school booking portal. It uses **Next.js + React + Tailwind CSS** for the frontend, **FastAPI** for the API, and **PostgreSQL** for persistence.

## Included features

- Learner registration and login with JWT authentication
- Instructor role and instructor profile fields for photo, expertise, services, vehicle, language and teaching area
- Weekly availability and one-click lesson booking
- Stripe Checkout integration for real payments, plus a safe `demo` payment mode for local/client demos
- Booking history and payment/booking statuses
- Instructor feedback workflow after lessons
- Structured 1–10 skill metrics grouped into introduction, intermediate and advanced driving skills
- Lesson-by-lesson feedback pagination. A page exists for each booked lesson even before feedback has been submitted
- Email notifications (SMTP in production, console output locally)
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

## Production deployment

A practical split is:

- Frontend: Vercel or another Next.js host
- Backend: Render, Fly.io, Railway, AWS, Azure or another container host
- Database: managed PostgreSQL

Set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` on the frontend to the public backend URLs. Set `CORS_ORIGINS` on the backend to your frontend origin. Use a strong random `JWT_SECRET`.

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
