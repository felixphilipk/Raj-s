import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'https://rajinstructor.co.nz'),
  title: { default: 'Raj Instructor | Driving lessons in Auckland', template: '%s | Raj Instructor' },
  description: 'Friendly, structured driving lessons in Auckland for learner, restricted and full licence drivers.',
  keywords: ['driving instructor Auckland', 'driving lessons Auckland', 'restricted licence lessons', 'learner driving lessons'],
  openGraph: { type: 'website', locale: 'en_NZ', title: 'Raj Instructor - Driving lessons in Auckland', description: 'Build skills, confidence and a clear path to your next licence.' },
};

export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en-NZ"><body>{children}</body></html>; }
