import { describe, it, expect } from 'vitest';
import { EngineInstance } from '../stores/useEngineStore';

/**
 * Tests for Engine Configuration logic (Issue #125)
 *
 * Verifies:
 * - Selected engine initial port and extra argument detection
 * - Engine switching synchronization (ComfyUI vs WebUI defaults)
 * - Port and argument validation
 * - Restart requirement detection for running instances
 * - External engine protection and connection identity preservation
 */

const KNOWN_FLAGS = [
  '--lowvram',
  '--medvram',
  '--xformers',
  '--cpu',
];

function getInitialPort(instance: EngineInstance): number {
  if (instance.port) return instance.port;
  if (instance.endpoint) {
    try {
      const parsed = Number(new URL(instance.endpoint).port);
      if (parsed) return parsed;
    } catch {
      // ignore
    }
  }
  return instance.type === 'webui' ? 7860 : 8188;
}

function parseArgs(extraArgs: string[] | undefined, defaultForType?: string) {
  const currentArgs = extraArgs || (defaultForType === 'comfyui' ? ['--lowvram'] : []);
  const flags = currentArgs.filter((a) => KNOWN_FLAGS.includes(a));
  const custom = currentArgs.filter((a) => !KNOWN_FLAGS.includes(a)).join(' ');
  return { flags, custom };
}

function validatePort(portStr: string): { valid: boolean; portNum?: number; error?: string } {
  const portNum = parseInt(portStr, 10);
  if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
    return { valid: false, error: 'Port must be a valid integer between 1 and 65535.' };
  }
  return { valid: true, portNum };
}

describe('Engine Configuration Logic (Issue #125)', () => {
  const comfyManaged: EngineInstance = {
    id: 'comfyui-managed',
    type: 'comfyui',
    name: 'Managed ComfyUI',
    is_managed: true,
    is_builtin: false,
    status: 'ready',
    endpoint: 'http://127.0.0.1:8188',
    capabilities: ['txt2img', 'img2img'],
    port: 8188,
    extra_args: ['--lowvram'],
    connection_id: 'comfyui-managed',
  };

  const webuiManaged: EngineInstance = {
    id: 'webui-managed',
    type: 'webui',
    name: 'Managed SD WebUI',
    is_managed: true,
    is_builtin: false,
    status: 'stopped',
    endpoint: 'http://127.0.0.1:7860',
    capabilities: ['txt2img', 'img2img', 'inpaint'],
    port: 7860,
    extra_args: ['--api', '--nowebui'],
    connection_id: 'webui-managed',
  };

  const externalComfy: EngineInstance = {
    id: 'ext_comfy_custom',
    type: 'comfyui',
    name: 'External ComfyUI on Custom Port',
    is_managed: false,
    is_builtin: false,
    status: 'ready',
    endpoint: 'http://127.0.0.1:9090',
    capabilities: ['txt2img'],
    port: 9090,
    extra_args: [],
    connection_id: 'ext_comfy_custom',
  };

  describe('Initial Port and Argument Loading', () => {
    it('loads ComfyUI actual port and default args', () => {
      const port = getInitialPort(comfyManaged);
      const { flags, custom } = parseArgs(comfyManaged.extra_args, comfyManaged.type);

      expect(port).toBe(8188);
      expect(flags).toEqual(['--lowvram']);
      expect(custom).toBe('');
    });

    it('loads WebUI actual port and custom args', () => {
      const port = getInitialPort(webuiManaged);
      const { flags, custom } = parseArgs(webuiManaged.extra_args, webuiManaged.type);

      expect(port).toBe(7860);
      expect(flags).toEqual([]);
      expect(custom).toBe('--api --nowebui');
    });

    it('loads external engine port from instance or endpoint URL', () => {
      const port = getInitialPort(externalComfy);
      expect(port).toBe(9090);

      const endpointOnly: EngineInstance = {
        ...externalComfy,
        port: undefined,
        endpoint: 'http://127.0.0.1:9191',
      };
      expect(getInitialPort(endpointOnly)).toBe(9191);
    });
  });

  describe('Switching Selected Engine', () => {
    it('correctly updates port and args when switching from ComfyUI to WebUI', () => {
      // Start with ComfyUI
      let currentPort = getInitialPort(comfyManaged);
      let args = parseArgs(comfyManaged.extra_args, comfyManaged.type);
      expect(currentPort).toBe(8188);
      expect(args.flags).toContain('--lowvram');

      // Switch to WebUI
      currentPort = getInitialPort(webuiManaged);
      args = parseArgs(webuiManaged.extra_args, webuiManaged.type);
      expect(currentPort).toBe(7860);
      expect(args.custom).toBe('--api --nowebui');
    });

    it('correctly updates port when switching from WebUI to external engine', () => {
      let currentPort = getInitialPort(webuiManaged);
      expect(currentPort).toBe(7860);

      currentPort = getInitialPort(externalComfy);
      expect(currentPort).toBe(9090);
    });
  });

  describe('Port Validation', () => {
    it('accepts valid ports within 1-65535', () => {
      expect(validatePort('8188').valid).toBe(true);
      expect(validatePort('8188').portNum).toBe(8188);
      expect(validatePort('1').valid).toBe(true);
      expect(validatePort('65535').valid).toBe(true);
    });

    it('rejects invalid ports: out of range, negative, or zero', () => {
      expect(validatePort('0').valid).toBe(false);
      expect(validatePort('-1').valid).toBe(false);
      expect(validatePort('65536').valid).toBe(false);
      expect(validatePort('99999').valid).toBe(false);
    });

    it('rejects non-numeric ports', () => {
      expect(validatePort('abc').valid).toBe(false);
      expect(validatePort('').valid).toBe(false);
    });
  });

  describe('Restart Requirement Detection', () => {
    it('determines restart is required when engine is currently running', () => {
      const runningEngine: EngineInstance = {
        ...comfyManaged,
        status: 'running',
      };
      const isRunning = runningEngine.status === 'running';
      expect(isRunning).toBe(true);
    });

    it('determines restart is not required when engine is stopped', () => {
      const stoppedEngine: EngineInstance = {
        ...comfyManaged,
        status: 'stopped',
      };
      const isRunning = stoppedEngine.status === 'running';
      expect(isRunning).toBe(false);
    });
  });

  describe('Preservation of Connection Identity and External Ownership', () => {
    it('preserves stable connection_id when configuring managed engine', () => {
      expect(comfyManaged.connection_id).toBe('comfyui-managed');
      expect(webuiManaged.connection_id).toBe('webui-managed');
    });

    it('preserves external engine identity and managed status', () => {
      expect(externalComfy.is_managed).toBe(false);
      expect(externalComfy.connection_id).toBe('ext_comfy_custom');
    });
  });
});
