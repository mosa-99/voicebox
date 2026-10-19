import { formatDistance } from 'date-fns';
import { ar, de, es, fr, ja, zhCN, zhTW } from 'date-fns/locale';
import i18n from '@/i18n';

/** Display name of an effect type ("reverb" → "Hall"), falling back to the raw id. */
export function formatEffectType(type: string): string {
  return i18n.t(`effects.types.${type}.label`, { defaultValue: type });
}

/**
 * Effect chain as "Hall → Delay", using the display name of each effect. The
 * arrow points in reading direction, so it turns into ← for Arabic.
 */
export function formatEffectChain(chain: { type: string }[], separator?: string): string {
  const arrow = i18n.dir(i18n.language) === 'rtl' ? ' ← ' : ' → ';
  return chain.map((e) => formatEffectType(e.type)).join(separator ?? arrow);
}

/**
 * Version labels are stored by the backend ("original", "clean", "take-2",
 * "version-3"); show those in the UI language and leave user-chosen ones as-is.
 */
export function formatVersionLabel(label: string): string {
  if (label === 'original' || label === 'clean') return i18n.t(`versions.${label}`);
  const numbered = /^(take|version)-(\d+)$/.exec(label);
  if (numbered) return i18n.t(`versions.${numbered[1]}`, { n: numbered[2] });
  return label;
}

export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function getDateLocale() {
  switch (i18n.language) {
    case 'de':
      return de;
    case 'ar':
      return ar;
    case 'es':
      return es;
    case 'ja':
      return ja;
    case 'zh-CN':
      return zhCN;
    case 'zh-TW':
      return zhTW;
    case 'fr':
      return fr;
    default:
      return undefined;
  }
}

// Backend timestamps are naive UTC — append `Z` so JS doesn't parse a
// timezone-less date-time string as local time.
function parseServerDate(date: string | Date): Date {
  if (typeof date !== 'string') {
    return date;
  }
  const dateStr = date.trim();
  if (!dateStr.includes('Z') && !dateStr.match(/[+-]\d{2}:\d{2}$/)) {
    return new Date(`${dateStr}Z`);
  }
  return new Date(dateStr);
}

export function formatDate(date: string | Date): string {
  return formatDistance(parseServerDate(date), new Date(), {
    addSuffix: true,
    locale: getDateLocale(),
  }).replace(/^about /i, '');
}

export function formatAbsoluteDate(date: string | Date): string {
  const dateObj = parseServerDate(date);
  return dateObj.toLocaleString(i18n.language, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

const ENGINE_DISPLAY_NAMES: Record<string, string> = {
  qwen: 'Qwen',
  qwen_custom_voice: 'Qwen CustomVoice',
  qwen_voice_design: 'Qwen VoiceDesign',
  luxtts: 'LuxTTS',
  chatterbox: 'Chatterbox',
  chatterbox_turbo: 'Chatterbox Turbo',
  tada: 'TADA',
  kokoro: 'Kokoro 82M',
};

export function formatEngineName(engine?: string, modelSize?: string): string {
  const name = ENGINE_DISPLAY_NAMES[engine ?? 'qwen'] ?? engine ?? 'Qwen';
  if (engine === 'qwen' && modelSize) {
    return `${name} ${modelSize}`;
  }
  return name;
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Math.round((bytes / k ** i) * 100) / 100} ${sizes[i]}`;
}
