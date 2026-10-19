import { useTranslation } from 'react-i18next';
import { usePlayerStore } from '@/stores/playerStore';
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from './toast';
import { useToast } from './use-toast';

export function Toaster() {
  const { t } = useTranslation();
  const { toasts } = useToast();
  const isPlayerOpen = !!usePlayerStore((s) => s.audioUrl);

  return (
    <ToastProvider label={t('toast.label')}>
      {toasts.map(({ id, title, description, action, ...props }) => (
        <Toast key={id} {...props}>
          <div className="grid gap-1 flex-1 min-w-0">
            {title && <ToastTitle>{title}</ToastTitle>}
            {description && <ToastDescription>{description}</ToastDescription>}
          </div>
          {action}
          <ToastClose aria-label={t('common.close')} />
        </Toast>
      ))}
      <ToastViewport
        label={t('toast.viewportLabel')}
        className={isPlayerOpen ? 'sm:bottom-44' : ''}
      />
    </ToastProvider>
  );
}
