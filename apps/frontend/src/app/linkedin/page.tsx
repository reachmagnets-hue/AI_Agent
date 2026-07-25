'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function LinkedInRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/extraction');
  }, [router]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
      <p className="text-sm font-semibold text-slate-600">
        Redirecting to Unified Lead Sourcing & LinkedIn Automation Hub...
      </p>
    </div>
  );
}
