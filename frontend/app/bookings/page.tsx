'use client';

import { useEffect, useState } from 'react';
import Shell from '@/components/Shell';
import { api, user } from '@/lib/api';

export default function Bookings() {
  const [rows, setRows] = useState<any[]>([]);
  const me = user();
  const instructor = me?.role === 'instructor' || me?.role === 'admin';

  useEffect(() => { api('/bookings').then(setRows); }, []);

  return <Shell>
    <h1 className="text-3xl font-bold">{instructor ? 'Teaching schedule' : 'My bookings'}</h1>
    <p className="mt-2 text-gray-600">{instructor ? 'Confirmed lessons and learner feedback status.' : 'Upcoming and completed driving lessons.'}</p>
    <div className="mt-8 card overflow-hidden"><div className="divide-y">
      {rows.map(booking => <div key={booking.id} className="grid gap-3 p-5 md:grid-cols-[1.4fr_1fr_1fr_auto]">
        <div><div className="font-semibold">{new Date(booking.starts_at).toLocaleString()}</div><div className="text-sm text-gray-500">{instructor ? `Learner: ${booking.student_name}` : `Instructor: ${booking.instructor_name}`}</div></div>
        <div><div className="text-xs text-gray-500">Lesson</div><span className="badge bg-teal-50 text-teal-800">{booking.status}</span></div>
        <div><div className="text-xs text-gray-500">Payment</div><span className="badge bg-green-50 text-green-700">{booking.payment_status}</span></div>
        <a href={instructor ? `/instructor?booking=${booking.id}` : `/feedback?booking=${booking.id}`} className="btn btn-secondary">{instructor ? (booking.feedback_submitted ? 'View tools' : 'Complete feedback') : 'View feedback'}</a>
      </div>)}
      {rows.length === 0 ? <div className="p-6 text-gray-500">No bookings yet.</div> : null}
    </div></div>
  </Shell>;
}
