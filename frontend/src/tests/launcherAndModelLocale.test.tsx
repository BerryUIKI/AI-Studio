import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

const memoryStore: Record<string, string> = {};

const storageMock = {
  getItem: (key: string) => memoryStore[key] || null,
  setItem: (key: string, value: string) => {
    memoryStore[key] = value.toString();
  },
  clear: () => {
    for (const key of Object.keys(memoryStore)) {
      delete memoryStore[key];
    }
  },
  removeItem: (key: string) => {
    delete memoryStore[key];
  },
};

Object.defineProperty(globalThis, 'localStorage', {
  value: storageMock,
  writable: true,
  configurable: true,
});

import { useSettingsStore } from '../stores/useSettingsStore';
import { useEngineStore } from '../stores/useEngineStore';
import { LauncherHub } from '../components/launcher/LauncherHub';
import { SetupWizardModal } from '../components/launcher/SetupWizardModal';
import { CompatibilityBadge } from '../components/hub/CompatibilityBadge';
import { SettingsView } from '../components/settings/SettingsView';
import { ModelEvaluation } from '../stores/useModelHubStore';

describe('Launcher and Model Setup Screens Locale Verification (Issue #139)', () => {
  const CHINESE_REGEX = /[\u4e00-\u9fa5]/;

  beforeEach(() => {
    localStorage.clear();
    useSettingsStore.getInitialState = () => useSettingsStore.getState();
    useSettingsStore.getState().resetSettings();
    useEngineStore.setState({
      instances: [
        {
          id: 'test-canvas',
          name: 'Infinite Canvas',
          type: 'canvas',
          endpoint: null,
          status: 'ready',
          is_builtin: true,
          is_managed: false,
          capabilities: ['t2i', 'i2i'],
        },
      ],
      isLoading: false,
      searchQuery: '',
    });
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
  });

  describe('LauncherHub', () => {
    it('renders the setup wizard badge in English when English locale is selected', () => {
      useSettingsStore.getState().setLanguage('en');

      const markup = renderToStaticMarkup(
        <LauncherHub onOpenSetupWizard={() => {}} />
      );

      // Verify the badge contains English text and does not leak Chinese
      expect(markup).toContain('Hardware Diagnostics &amp; Model Setup');
      expect(markup).not.toContain('系统硬件体检与本地模型部署');
    });

    it('preserves Simplified Chinese badge when zh-CN locale is selected', () => {
      useSettingsStore.getState().setLanguage('zh-CN');

      const markup = renderToStaticMarkup(
        <LauncherHub onOpenSetupWizard={() => {}} />
      );

      expect(markup).toContain('系统硬件体检与本地模型部署');
    });
  });

  describe('SetupWizardModal', () => {
    it('renders modal title, subtitle, and step labels in English when English locale is selected', () => {
      useSettingsStore.getState().setLanguage('en');

      const markup = renderToStaticMarkup(
        <SetupWizardModal isOpen={true} onClose={() => {}} />
      );

      expect(markup).toContain('Hardware Diagnostics &amp; Model Setup');
      expect(markup).toContain('Live GPU diagnosis, embedded llama.cpp lifecycle &amp; instant local model provisioning');
      expect(markup).toContain('1. Hardware Check');
      expect(markup).toContain('2. Deploy Model');
      expect(markup).toContain('3. Ready');

      // The header title and step titles must not contain Chinese characters
      expect(markup).not.toContain('系统硬件体检与本地模型部署向导');
      expect(markup).not.toContain('1. 硬件配置体检');
      expect(markup).not.toContain('2. 选择与部署模型');
      expect(markup).not.toContain('3. 体验就绪');
    });

    it('renders modal title and step labels in Chinese when zh-CN locale is selected', () => {
      useSettingsStore.getState().setLanguage('zh-CN');

      const markup = renderToStaticMarkup(
        <SetupWizardModal isOpen={true} onClose={() => {}} />
      );

      expect(markup).toContain('系统硬件体检与本地模型部署向导');
      expect(markup).toContain('1. 硬件配置体检');
      expect(markup).toContain('2. 选择与部署模型');
      expect(markup).toContain('3. 体验就绪');
    });
  });

  describe('CompatibilityBadge', () => {
    it('renders all model compatibility tiers in English without Chinese leak when English is selected', () => {
      useSettingsStore.getState().setLanguage('en');

      const testTiers: Array<{
        evaluation: ModelEvaluation;
        expectedEnLabel: string;
      }> = [
        {
          evaluation: {
            tier: 'optimal',
            tier_label: '极致流畅 (Optimal)',
            tier_color: 'emerald',
            estimated_latency_sec: '4-8s',
            required_vram_mb: 6144,
            notes: 'Fits entirely in dedicated VRAM.',
          },
          expectedEnLabel: 'Optimal',
        },
        {
          evaluation: {
            tier: 'playable_offload',
            tier_label: '需共享内存 (RAM Offload)',
            tier_color: 'amber',
            estimated_latency_sec: '15-25s',
            required_vram_mb: 8192,
            notes: 'Offloads to host RAM.',
          },
          expectedEnLabel: 'RAM Offload',
        },
        {
          evaluation: {
            tier: 'playable_offload',
            tier_label: 'CPU运行 (无独立显卡)',
            tier_color: 'amber',
            estimated_latency_sec: '10s',
            required_vram_mb: 1024,
            notes: 'No GPU detected; will execute on host CPU.',
          },
          expectedEnLabel: 'CPU Mode',
        },
        {
          evaluation: {
            tier: 'heavy_paging',
            tier_label: '严重卡顿 (Heavy Paging)',
            tier_color: 'orange',
            estimated_latency_sec: '>60s',
            required_vram_mb: 12288,
            notes: 'Host memory under high pressure.',
          },
          expectedEnLabel: 'Heavy Paging',
        },
        {
          evaluation: {
            tier: 'unsupported',
            tier_label: '无法运行 (易爆显存，建议云端)',
            tier_color: 'rose',
            estimated_latency_sec: 'N/A',
            required_vram_mb: 24576,
            notes: 'Recommend Cloud BYOK.',
          },
          expectedEnLabel: 'Unsupported',
        },
      ];

      for (const { evaluation, expectedEnLabel } of testTiers) {
        const markup = renderToStaticMarkup(
          <CompatibilityBadge evaluation={evaluation} modelName="Test Model" />
        );
        expect(markup).toContain(expectedEnLabel);
        // The rendered badge label should not contain any Chinese characters in English locale
        const buttonContent = markup.match(/<button[^>]*>([\s\S]*?)<\/button>/)?.[1] || '';
        expect(CHINESE_REGEX.test(buttonContent)).toBe(false);
      }
    });

    it('preserves Chinese tier labels when zh-CN locale is selected', () => {
      useSettingsStore.getState().setLanguage('zh-CN');

      const evaluation: ModelEvaluation = {
        tier: 'optimal',
        tier_label: '极致流畅 (Optimal)',
        tier_color: 'emerald',
        estimated_latency_sec: '4-8s',
        required_vram_mb: 6144,
        notes: 'Fits entirely in dedicated VRAM.',
      };

      const markup = renderToStaticMarkup(
        <CompatibilityBadge evaluation={evaluation} modelName="Test Model" />
      );
      expect(markup).toContain('极致流畅 (Optimal)');
    });
  });

  describe('SettingsView Agent & Local Model Setup', () => {
    it('renders Agent tab, heading, wizard banner, and options in English with no Chinese characters', () => {
      useSettingsStore.getState().setLanguage('en');

      const markup = renderToStaticMarkup(
        <SettingsView initialSection="agent" />
      );

      // Verify the agent tab title, section header, and banner are in English
      expect(markup).toContain('AI Agent &amp; LLM');
      expect(markup).toContain('AI Agent &amp; Local LLM Base');
      expect(markup).toContain('Hardware Diagnostics &amp; Local Model Setup Wizard');
      expect(markup).not.toContain('大模型基座');

      // Verify no Chinese characters in the agent settings section when English is active
      expect(CHINESE_REGEX.test(markup)).toBe(false);
    });

    it('renders Agent tab in Chinese when zh-CN locale is selected', () => {
      useSettingsStore.getState().setLanguage('zh-CN');

      const markup = renderToStaticMarkup(
        <SettingsView initialSection="agent" />
      );

      expect(markup).toContain('AI Agent 与大模型基座');
    });
  });
});


