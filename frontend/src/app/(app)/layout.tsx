import { AppShell } from '@/components/ui/AppShell';
import { AuthGuard } from '@/features/auth/AuthGuard';
import { UserMenu } from '@/features/auth/UserMenu';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell userSlot={<UserMenu />}>{children}</AppShell>
    </AuthGuard>
  );
}
