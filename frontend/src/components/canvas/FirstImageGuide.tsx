import { useMemo } from 'react';
import { Cloud, Cpu, ImagePlus, Sparkles } from 'lucide-react';
import { useUiText } from '../../i18n/useUiText';
import { useCanvasStore } from '../../stores/useCanvasStore';
import { useEngineStore } from '../../stores/useEngineStore';
import { useCreativeStore } from '../../stores/useCreativeStore';
import { useCreationSetupStore, localModelAvailable } from '../../stores/useCreationSetupStore';
import { useCreationReadiness } from './CreationSetup';

type Verdict = { state: 'ready' | 'needs-work'; reason: string; action: string };

interface FirstImageGuideProps {
  onCloudSetup: () => void;
  onLocalSetup: () => void;
  onOpenModels: () => void;
}

const IMAGE_ACTIONS = ['txt2img', 'img2img', 'inpaint', 'upscale'];

/**
 * Shown only while the canvas is empty.
 *
 * The dock at the bottom already disables Generate and links to setup, but a new
 * user opening the app sees a blank canvas and the reason sits in small text at
 * the edge of the screen. This puts the choice and its current blocker where the
 * user is already looking.
 */
export function FirstImageGuide({ onCloudSetup, onLocalSetup, onOpenModels }: FirstImageGuideProps) {
  const ui = useUiText();
  const nodeCount = useCanvasStore((state) => state.nodes.length);
  const instances = useEngineStore((state) => state.instances);
  const models = useCreationSetupStore((state) => state.models);
  const providers = useCreationSetupStore((state) => state.providers);
  const loading = useCreationSetupStore((state) => state.loading);
  const readiness = useCreationReadiness();
  const prompt = useCreativeStore((state) => state.prompt);

  const cloud = useMemo<Verdict>(() => {
    const usable = providers.filter((provider) => provider.capabilities.some((action) => IMAGE_ACTIONS.includes(action)));
    const configured = usable.filter((provider) => provider.is_configured);
    if (configured.length === 0) {
      return {
        state: 'needs-work',
        reason: usable.length
          ? ui('ui_guide_cloud_no_key')
          : ui('ui_guide_cloud_none'),
        action: ui('ui_guide_cloud_action'),
      };
    }
    // A configured provider still needs a model this action can use.
    const withModel = configured.find((provider) => readiness.provider?.id === provider.id);
    return {
      state: 'ready',
      reason: withModel
        ? ui('ui_guide_cloud_ready', { name: providerLabel(withModel.name) })
        : ui('ui_guide_cloud_select', { name: providerLabel(configured[0].name) }),
      action: ui('ui_guide_cloud_start'),
    };
  }, [providers, readiness.provider, ui]);

  const local = useMemo<Verdict>(() => {
    const engines = instances.filter((instance) => instance.type === 'comfyui' || instance.type === 'webui');
    if (engines.length === 0) {
      return { state: 'needs-work', reason: ui('ui_guide_local_none'), action: ui('ui_guide_local_install') };
    }
    const installed = engines.filter((engine) => engine.status !== 'not_installed');
    if (installed.length === 0) {
      return { state: 'needs-work', reason: ui('ui_guide_local_not_installed'), action: ui('ui_guide_local_install') };
    }
    const running = installed.filter((engine) => engine.status === 'running');
    if (running.length === 0) {
      const engine = installed[0];
      return {
        state: 'needs-work',
        reason: ui('ui_guide_local_stopped', { name: providerLabel(engine.name) }),
        action: ui('ui_guide_local_start'),
      };
    }
    const engine = running[0];
    const usable = models.filter((model) => localModelAvailable(model, engine.type));
    if (usable.length === 0) {
      return {
        state: 'needs-work',
        reason: ui('ui_guide_local_no_model', { name: providerLabel(engine.name) }),
        action: ui('ui_guide_local_models'),
      };
    }
    const selected = readiness.engine?.type === engine.type && readiness.ready;
    return {
      state: 'ready',
      reason: selected
        ? ui('ui_guide_local_ready', { name: providerLabel(engine.name) })
        : ui('ui_guide_local_models_ready', { count: String(usable.length) }),
      action: ui('ui_guide_local_start'),
    };
  }, [instances, models, readiness.engine, readiness.ready, ui]);

  if (nodeCount > 0) return null;

  return (
    <section
      aria-label={ui('ui_guide_title')}
      className="pointer-events-none absolute inset-x-0 top-0 bottom-[15.5rem] z-10 flex items-center justify-center p-6"
    >
      <div className="pointer-events-auto w-full max-w-2xl rounded-2xl border border-white/[0.08] bg-slate-900/80 p-6 shadow-2xl backdrop-blur-sm">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-indigo-500/30 bg-indigo-600/15 text-indigo-300">
            <Sparkles className="h-4.5 w-4.5" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-white">{ui('ui_guide_title')}</h2>
            <p className="text-[11px] text-slate-400">{ui('ui_guide_subtitle')}</p>
          </div>
        </div>

        <p className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2.5 text-xs text-slate-300">
          {prompt || ui('ui_guide_example_prompt')}
        </p>

        <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          <PathCard
            icon={<Cloud className="h-4 w-4" />}
            title={ui('ui_guide_cloud_title')}
            verdict={cloud}
            loading={loading}
            onAction={cloud.state === 'ready' ? undefined : onCloudSetup}
          />
          <PathCard
            icon={<Cpu className="h-4 w-4" />}
            title={ui('ui_guide_local_title')}
            verdict={local}
            loading={loading}
            onAction={local.state === 'ready' ? undefined : local.action === ui('ui_guide_local_models') ? onOpenModels : onLocalSetup}
          />
        </div>

        <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-relaxed text-slate-500">
          <ImagePlus className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{ui('ui_guide_footer')}</span>
        </p>
      </div>
    </section>
  );
}

/** Provider names arrive from the backend; keep the UI label readable without altering the id. */
function providerLabel(name: string): string {
  return name.length > 32 ? `${name.slice(0, 31)}…` : name;
}

function PathCard({ icon, title, verdict, loading, onAction }: {
  icon: React.ReactNode;
  title: string;
  verdict: Verdict;
  loading: boolean;
  onAction?: () => void;
}) {
  const ui = useUiText();
  const ready = verdict.state === 'ready';
  return (
    <div className={`flex flex-col gap-2 rounded-xl border p-3 ${ready ? 'border-emerald-800/50 bg-emerald-950/20' : 'border-slate-800 bg-slate-950/40'}`}>
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
        <span className={ready ? 'text-emerald-400' : 'text-slate-400'}>{icon}</span>
        <span>{title}</span>
        <span className={`ml-auto rounded-full px-1.5 py-0.5 text-[10px] ${ready ? 'bg-emerald-900/60 text-emerald-300' : 'bg-slate-800 text-slate-400'}`}>
          {loading ? ui('ui_guide_checking') : ready ? ui('ui_guide_state_ready') : ui('ui_guide_state_blocked')}
        </span>
      </div>
      <p className="min-h-8 text-[11px] leading-relaxed text-slate-400">{verdict.reason}</p>
      {onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-auto self-start rounded-lg border border-slate-700 px-2.5 py-1 text-[11px] text-slate-200 hover:bg-slate-800"
        >
          {verdict.action}
        </button>
      )}
    </div>
  );
}
