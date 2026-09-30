import type { Metadata } from 'next';

// The URL carries the cancel token — never send it to other sites as a Referer.
export const metadata: Metadata = {
  title: 'Keep your account · DhanRadar',
  referrer: 'no-referrer',
  robots: { index: false, follow: false },
};

export default function CancelDeletionLayout({ children }: { children: React.ReactNode }) {
  return children;
}
