# UI locale coverage and fallback contract

English is the verified first-release UI language. The seven retained dictionaries
are translation previews; their availability does not certify the complete image
workflow. Settings explicitly labels previews and explains English fallback.

`translations.ts` is the resolver for legacy dictionary entries and the shared
`uiMessages.ts` workflow catalog. `useUiText` subscribes to the locale only, updates
mounted UI on language changes and formats named placeholders through `uiText`.
Missing preview entries resolve to the English catalog. Legacy callers may supply
an explicit fallback; `t(key, lang) || fallback` is not a valid fallback because
unknown keys themselves are nonempty strings.

The catalog covers creation/readiness, image cards, mask/upscale/export controls,
projects/history, Agent, provider setup, navigation, engine repair/configuration,
safe exit/removal, downloads, onboarding/settings, model readiness and error
recovery. Existing Chinese preview wording is retained where supplied. Static
model/menu descriptions can use `ui.lookup` when rendered; the underlying metadata,
model names/identifiers and execution parameters remain unchanged. Runtime-provided
diagnostics, provider descriptions and user-authored content are retained verbatim
unless there is a known catalog entry. They must not be translated before dispatch,
hashing, persistence or ownership decisions.

Dates and numbers use `i18n/format.ts`; unknown failures use the shared error
normalizer and localized fallback text. Backend diagnostics remain English and are
displayed as observed text. No client guesses a localized error by matching a key
substring in a provider log. Semantic readiness and control decisions use the
original typed values, never the translated display label.

ESLint rejects new literal JSX display text and literal accessible names in the
application and production components. Catalog keys are typed for new UI calls.
Regression tests cover mounted locale changes, English fallback, key resolution,
execution identifier separation and existing preview behavior. These checks are
implementation evidence. Full keyboard/native workflow and translation-quality
acceptance for any newly advertised locale still requires the testing handover.
