import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';
import ar from './locales/ar/translation.json';
import de from './locales/de/translation.json';
import en from './locales/en/translation.json';
import es from './locales/es/translation.json';
import fr from './locales/fr/translation.json';
import it from './locales/it/translation.json';
import ja from './locales/ja/translation.json';
import ko from './locales/ko/translation.json';
import ptBR from './locales/pt-BR/translation.json';
import zhCN from './locales/zh-CN/translation.json';
import zhTW from './locales/zh-TW/translation.json';

export const SUPPORTED_LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'de', label: 'Deutsch' },
  { code: 'ar', label: 'العربية' },
  { code: 'es', label: 'Español' },
  { code: 'pt-BR', label: 'Português (Brasil)' },
  { code: 'ja', label: '日本語' },
  { code: 'ko', label: '한국어' },
  { code: 'zh-CN', label: '简体中文' },
  { code: 'zh-TW', label: '繁體中文' },
  { code: 'fr', label: 'Français' },
  { code: 'it', label: 'Italiano' },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]['code'];

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      de: { translation: de },
      ar: { translation: ar },
      es: { translation: es },
      'pt-BR': { translation: ptBR },
      ja: { translation: ja },
      ko: { translation: ko },
      'zh-CN': { translation: zhCN },
      'zh-TW': { translation: zhTW },
      fr: { translation: fr },
      it: { translation: it },
    },
    fallbackLng: 'en',
    supportedLngs: SUPPORTED_LANGUAGES.map((l) => l.code),
    load: 'currentOnly',
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'voicebox:lang',
      caches: ['localStorage'],
    },
  });

// Arabic reads right-to-left; flip the whole document so layout and text
// alignment follow. `lang` also lets the browser pick proper fonts and hyphenation.
const RTL_LANGUAGES = new Set(['ar']);

function applyDocumentLanguage(lng: string) {
  if (!lng || typeof document === 'undefined') return;
  document.documentElement.lang = lng;
  document.documentElement.dir = RTL_LANGUAGES.has(lng) ? 'rtl' : 'ltr';
  // In the desktop app, relabel the native macOS menu bar to match.
  if ('__TAURI_INTERNALS__' in window) {
    import('@tauri-apps/api/core')
      .then(({ invoke }) => invoke('set_menu_language', { lang: lng }))
      .catch((error) => console.warn('Could not localize the app menu:', error));
  }
}

applyDocumentLanguage(i18n.language);
i18n.on('languageChanged', applyDocumentLanguage);

export default i18n;
