import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Cloud, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api/client';
import { SettingRow, SettingSection } from './SettingRow';

// "Log in with browser" device pairing. The backend opens the system browser
// and completes the code exchange; here we just kick it off and poll status
// until the link goes live. The API key never touches the frontend.
export function CloudSection() {
  const { t } = useTranslation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [polling, setPolling] = useState(false);

  const { data: status } = useQuery({
    queryKey: ['cloud-status'],
    queryFn: () => apiClient.getCloudStatus(),
    refetchInterval: polling ? 2000 : false,
  });

  const connected = status?.connected ?? false;
  const deviceName = status?.device_name ?? t('cloud.thisDevice');

  // Once the browser flow completes, stop polling and celebrate.
  useEffect(() => {
    if (connected && polling) {
      setPolling(false);
      toast({
        title: t('cloud.toast.connected'),
        description: t('cloud.toast.linkedAs', { device: deviceName }),
      });
    }
  }, [connected, polling, deviceName, toast, t]);

  // Give up after two minutes so an abandoned browser flow doesn't leave the
  // button stuck on "Waiting for browser…". The backend state stays valid for
  // ten, so the user can simply start again.
  useEffect(() => {
    if (!polling) return;
    const timeoutId = window.setTimeout(() => {
      setPolling(false);
      toast({
        title: t('cloud.toast.timedOut'),
        description: t('cloud.toast.timedOutDescription'),
        variant: 'destructive',
      });
    }, 120_000);
    return () => window.clearTimeout(timeoutId);
  }, [polling, toast, t]);

  const startLogin = useMutation({
    mutationFn: () => apiClient.startCloudLogin(),
    onSuccess: () => {
      setPolling(true);
      toast({
        title: t('cloud.toast.continueInBrowser'),
        description: t('cloud.toast.continueInBrowserDescription'),
      });
    },
    onError: (error: Error) =>
      toast({
        title: t('cloud.toast.startFailed'),
        description: error.message,
        variant: 'destructive',
      }),
  });

  const disconnect = useMutation({
    mutationFn: () => apiClient.disconnectCloud(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cloud-status'] });
      toast({
        title: t('cloud.toast.disconnected'),
        description: t('cloud.toast.disconnectedDescription'),
      });
    },
    onError: (error: Error) =>
      toast({
        title: t('cloud.toast.disconnectFailed'),
        description: error.message,
        variant: 'destructive',
      }),
  });

  const busy = startLogin.isPending || polling;

  return (
    <SettingSection title={t('cloud.title')} description={t('cloud.description')}>
      <SettingRow
        title={connected ? t('cloud.connected') : t('cloud.account')}
        description={
          connected
            ? `${t('cloud.linkedAs', { device: deviceName })}${
                status?.key_prefix ? ` · ${status.key_prefix}…` : ''
              }`
            : t('cloud.loginHint')
        }
        action={
          connected ? (
            <Button
              disabled={disconnect.isPending}
              onClick={() => disconnect.mutate()}
              size="sm"
              variant="outline"
            >
              {disconnect.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 me-1.5 animate-spin" />
                  {t('cloud.disconnecting')}
                </>
              ) : (
                t('cloud.disconnect')
              )}
            </Button>
          ) : (
            <Button disabled={busy} onClick={() => startLogin.mutate()} size="sm">
              {busy ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 me-1.5 animate-spin" />
                  {polling ? t('cloud.waitingForBrowser') : t('cloud.opening')}
                </>
              ) : (
                <>
                  <Cloud className="h-3.5 w-3.5 me-1.5" />
                  {t('cloud.login')}
                </>
              )}
            </Button>
          )
        }
      />

      {connected && (
        <SettingRow title={t('cloud.manage')} description={t('cloud.manageDescription')}>
          <a
            className="text-sm text-accent hover:underline"
            href={status?.dashboard_url ?? 'https://voicebox.sh/account'}
            rel="noopener noreferrer"
            target="_blank"
          >
            {t('cloud.openDashboard')} ↗
          </a>
        </SettingRow>
      )}
    </SettingSection>
  );
}
