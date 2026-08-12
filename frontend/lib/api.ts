export const API = process.env.NEXT_PUBLIC_API_URL || '';

type DemoUser = { id: number; email: string; password: string; first_name: string; last_name: string; phone?: string; role: 'student' | 'instructor' };
type DemoState = { users: DemoUser[]; availability: any[]; bookings: any[]; feedback: any[]; notifications: any[]; nextId: number };

const demoMode = () => typeof window !== 'undefined' && (process.env.NEXT_PUBLIC_DEMO_MODE === 'true' || !API);
const stateKey = 'drivebook-demo-state';
const defaultState = (): DemoState => {
  const now = new Date();
  const availability = [1, 2, 3, 4, 5, 6].map((offset) => {
    const start = new Date(now);
    start.setDate(now.getDate() + offset);
    start.setHours(offset % 2 ? 10 : 14, 0, 0, 0);
    return { id: offset + 10, instructor_id: 2, starts_at: start.toISOString(), ends_at: new Date(start.getTime() + 60 * 60 * 1000).toISOString() };
  });
  return {
    users: [
      { id: 1, email: 'student@example.com', password: 'Password123!', first_name: 'Demo', last_name: 'Student', role: 'student' },
      { id: 2, email: 'instructor@example.com', password: 'Password123!', first_name: 'Alex', last_name: 'Morgan', role: 'instructor' },
    ],
    availability,
    bookings: [],
    feedback: [],
    notifications: [],
    nextId: 100,
  };
};
const loadState = (): DemoState => {
  const saved = localStorage.getItem(stateKey);
  if (!saved) return defaultState();
  try { return JSON.parse(saved); } catch { return defaultState(); }
};
const saveState = (state: DemoState) => localStorage.setItem(stateKey, JSON.stringify(state));
const demoUser = () => user();
const publicUser = (u: DemoUser) => ({ id: u.id, email: u.email, first_name: u.first_name, last_name: u.last_name, role: u.role });
const parseBody = (opts: RequestInit) => opts.body ? JSON.parse(String(opts.body)) : {};
const instructor = (state: DemoState) => state.users.find((u) => u.id === 2)!;
const notification = (state: DemoState, userId: number, title: string, body: string, link: string) => {
  state.notifications.unshift({ id: state.nextId++, user_id: userId, title, body, link, is_read: false, created_at: new Date().toISOString() });
};

function demoApi(path: string, opts: RequestInit) {
  const state = loadState();
  const current = demoUser();
  const method = (opts.method || 'GET').toUpperCase();
  const body = parseBody(opts);
  const requireUser = () => { if (!current) throw new Error('Please sign in to continue.'); return current; };
  const bookingView = (booking: any) => {
    const slot = state.availability.find((item) => item.id === booking.availability_id)!;
    const student = state.users.find((item) => item.id === booking.student_id)!;
    const teacher = state.users.find((item) => item.id === booking.instructor_id)!;
    return { ...booking, starts_at: slot.starts_at, ends_at: slot.ends_at, student_name: `${student.first_name} ${student.last_name}`, instructor_name: `${teacher.first_name} ${teacher.last_name}`, feedback_submitted: state.feedback.some((item) => item.booking_id === booking.id) };
  };

  if (path === '/auth/login' && method === 'POST') {
    const found = state.users.find((item) => item.email.toLowerCase() === String(body.email).toLowerCase() && item.password === body.password);
    if (!found) throw new Error('Incorrect email or password');
    return { access_token: `demo-${found.id}`, token_type: 'bearer', user: publicUser(found) };
  }
  if (path === '/auth/register' && method === 'POST') {
    if (state.users.some((item) => item.email.toLowerCase() === String(body.email).toLowerCase())) throw new Error('Email already registered');
    const newUser: DemoUser = { id: state.nextId++, email: body.email, password: body.password, first_name: body.first_name, last_name: body.last_name, phone: body.phone, role: 'student' };
    state.users.push(newUser); saveState(state);
    return { access_token: `demo-${newUser.id}`, token_type: 'bearer', user: publicUser(newUser) };
  }
  if (path === '/instructors') return [{ id: 2, name: 'Alex Morgan', bio: 'A calm, patient instructor focused on safe habits, confidence and practical test preparation.', expertise: 'Learner driving, restricted/full test preparation, confidence building', services: '1-hour lessons, mock tests, urban driving coaching', vehicle: 'Automatic dual-control training vehicle', teaching_areas: 'Auckland Central and surrounding suburbs', languages: 'English', image_url: '/instructor-placeholder.svg', lesson_price_cents: 9000 }];
  if (path === '/availability') return state.availability.filter((slot) => !state.bookings.some((booking) => booking.availability_id === slot.id));
  if (path.startsWith('/bookings/') && method === 'POST') {
    const learner = requireUser(); if (learner.role !== 'student') throw new Error('Sign in as the learner to book a lesson.');
    const slotId = Number(path.split('/').pop()); const slot = state.availability.find((item) => item.id === slotId);
    if (!slot || state.bookings.some((item) => item.availability_id === slotId)) throw new Error('This slot is no longer available.');
    const booking = { id: state.nextId++, student_id: learner.id, instructor_id: slot.instructor_id, availability_id: slotId, status: 'confirmed', payment_status: 'paid', amount_cents: 9000, created_at: new Date().toISOString() };
    state.bookings.unshift(booking); notification(state, learner.id, 'Lesson booked', 'Your demo lesson is confirmed. A feedback page has been reserved for it.', `/feedback?booking=${booking.id}`); saveState(state);
    return { booking_id: booking.id, checkout_url: `${window.location.origin}/bookings?booked=${booking.id}`, mode: 'demo' };
  }
  if (path === '/bookings') {
    const account = requireUser();
    return state.bookings.filter((item) => account.role === 'student' ? item.student_id === account.id : item.instructor_id === account.id).map(bookingView);
  }
  if (path === '/instructor/availability' && method === 'POST') {
    const account = requireUser(); if (account.role !== 'instructor') throw new Error('Instructor access is required.');
    const slot = { id: state.nextId++, instructor_id: account.id, starts_at: body.starts_at, ends_at: body.ends_at }; state.availability.push(slot); saveState(state); return slot;
  }
  if (path.startsWith('/instructor/bookings/') && path.endsWith('/feedback') && method === 'POST') {
    const account = requireUser(); const bookingId = Number(path.split('/')[3]); const booking = state.bookings.find((item) => item.id === bookingId);
    if (account.role !== 'instructor' || !booking) throw new Error('Booking not found.');
    if (state.feedback.some((item) => item.booking_id === bookingId)) throw new Error('Feedback already submitted.');
    const entry = { id: state.nextId++, booking_id: bookingId, student_id: booking.student_id, instructor_id: account.id, lesson_summary: body.lesson_summary, agreed_practice: body.agreed_practice, further_notes: body.further_notes || '', metrics: body.metrics || {} };
    booking.status = 'completed'; state.feedback.push(entry); notification(state, booking.student_id, 'New lesson feedback', 'Your instructor has submitted feedback for your latest lesson.', `/feedback?booking=${booking.id}`); saveState(state); return { id: entry.id };
  }
  if (path === '/feedback') {
    const account = requireUser();
    return state.bookings.filter((item) => account.role === 'student' ? item.student_id === account.id : item.instructor_id === account.id).map((booking) => {
      const entry = state.feedback.find((item) => item.booking_id === booking.id); const view = bookingView(booking);
      return { booking_id: booking.id, starts_at: view.starts_at, instructor_name: view.instructor_name, student_name: view.student_name, status: entry ? 'submitted' : 'pending', lesson_summary: entry?.lesson_summary || 'Feedback will appear here after the lesson.', agreed_practice: entry?.agreed_practice || '', further_notes: entry?.further_notes || '', metrics: entry?.metrics || {} };
    });
  }
  if (path === '/notifications') return state.notifications.filter((item) => item.user_id === requireUser().id);
  if (path.startsWith('/notifications/') && path.endsWith('/read') && method === 'POST') {
    const id = Number(path.split('/')[2]); const entry = state.notifications.find((item) => item.id === id && item.user_id === requireUser().id); if (!entry) throw new Error('Notification not found.'); entry.is_read = true; saveState(state); return { ok: true };
  }
  throw new Error(`Demo action is not available: ${method} ${path}`);
}

export const token = () => typeof window === 'undefined' ? null : localStorage.getItem('token');
export const user = () => { try { return typeof window === 'undefined' ? null : JSON.parse(localStorage.getItem('user') || 'null'); } catch { return null; } };

export async function api(path: string, opts: RequestInit = {}) {
  if (demoMode()) return demoApi(path, opts);
  const headers = new Headers(opts.headers); headers.set('Content-Type', 'application/json'); const currentToken = token(); if (currentToken) headers.set('Authorization', `Bearer ${currentToken}`);
  const response = await fetch(`${API}${path}`, { ...opts, headers, cache: 'no-store' });
  if (!response.ok) { let message = 'Request failed'; try { message = (await response.json()).detail || message; } catch {} throw new Error(message); }
  return response.status === 204 ? null : response.json();
}
