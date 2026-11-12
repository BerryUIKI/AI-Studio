import { StrictMode } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from './components/ui/ErrorBoundary';
import './index.css';
import { LANGUAGE_OPTIONS } from './i18n/translations';
import { useSettingsStore } from './stores/useSettingsStore';

const setupLanguage = new URLSearchParams(window.location.search).get('setupLanguage');
const setupOption = LANGUAGE_OPTIONS.find((option) => option.id === setupLanguage);
if (setupOption) useSettingsStore.getState().setLanguage(setupOption.id);


ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary fallbackTitle="Application Error">
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
