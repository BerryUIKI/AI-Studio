# Settings Modular Sidebar & Multi-Language i18n Specification

## 1. Overview
As Berry AI Studio scales its capabilities (Launcher, Creative Infinite Canvas, Model Hub, Multi-Engine Supervisor, Cloud BYOK, and AI Agents), placing all settings options in a single long vertical scroll view increases cognitive overload.

This specification defines:
1. **Modular Settings Sidebar**: Separates preferences into dedicated, focused sections (**General**, **Language & Region**, **Engines & Hardware**, **Cloud & API**, **Startup & Exit**, and **About**).
2. **Internationalization (i18n)**:
   - Full support for 8 major languages:
     - 🇺🇸 English (`en`) [Default Fallback]
     - 🇨🇳 简体中文 (`zh-CN`)
     - 🇯🇵 日本語 (`ja`)
     - 🇰🇷 한국어 (`ko`)
     - 🇫🇷 Français (`fr`)
     - 🇩🇪 Deutsch (`de`)
     - 🇪🇸 Español (`es`)
     - 🇷🇺 Русский (`ru`)
   - **System Locale Follower**: Option for "Follow System / Auto-Detect (`system`)".
   - **Strict Fallback Policy**: When system language is not detected or unsupported, gracefully defaults to English (`en`).

---

## 2. Architecture & Data Contracts

### 2.1 Supported Languages Type
```typescript
export type SupportedLanguage = 'en' | 'zh-CN' | 'ja' | 'ko' | 'fr' | 'de' | 'es' | 'ru';
export type LanguageSetting = 'system' | SupportedLanguage;
```

### 2.2 System Detection Algorithm
```typescript
export function resolveEffectiveLanguage(setting: LanguageSetting): SupportedLanguage {
  if (setting !== 'system') return setting;
  
  if (typeof navigator !== 'undefined' && navigator.language) {
    const navLang = navigator.language.toLowerCase();
    if (navLang.startsWith('zh')) return 'zh-CN';
    if (navLang.startsWith('ja')) return 'ja';
    if (navLang.startsWith('ko')) return 'ko';
    if (navLang.startsWith('fr')) return 'fr';
    if (navLang.startsWith('de')) return 'de';
    if (navLang.startsWith('es')) return 'es';
    if (navLang.startsWith('ru')) return 'ru';
    if (navLang.startsWith('en')) return 'en';
  }
  
  // Default fallback when undetectable or unknown
  return 'en';
}
```

### 2.3 Settings Modular Sections
- `general`: Appearance, theme, and language selection.
- `startup`: Launch view (Launcher Hub vs Infinite Canvas).
- `engines`: ComfyUI / SD WebUI directories, model catalog roots, hardware telemetry.
- `cloud`: BYOK provider keys (OpenAI, Fal.ai, SiliconFlow).
- `exit`: Window close behavior & background engine daemon policy.
- `about`: Version details, architecture manifesto, and system info.
