'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle, RefreshCcw } from 'lucide-react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error(error);
  }, [error]);

  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <Card className="w-full max-w-md border-red-500/20 bg-red-500/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-red-500">
            <AlertCircle className="h-5 w-5" />
            Something went wrong!
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            An error occurred while rendering the leads data. This is usually caused by a malformed lead record.
          </p>
          
          <div className="rounded bg-background/50 p-4 font-mono text-xs text-red-400 border border-red-500/10 break-words">
            {error.message || "Unknown rendering error"}
          </div>

          <Button
            onClick={() => reset()}
            variant="outline"
            className="w-full border-red-500/20 text-red-500 hover:bg-red-500/10 hover:text-red-600"
          >
            <RefreshCcw className="mr-2 h-4 w-4" />
            Try again
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
