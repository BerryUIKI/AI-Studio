// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { FloatingCardToolbar } from '../components/canvas/FloatingCardToolbar';
import { ImageCardNode } from '../components/canvas/ImageCardNode';
import { useCreationSetupStore } from '../stores/useCreationSetupStore';
import { useCreativeStore } from '../stores/useCreativeStore';
import { ComponentProps } from 'react';

const card = { imageUrl: '/fixture.jpg', width: 32, height: 24, label: 'Fixture', mimeType: 'image/jpeg' };
const nodeProps: ComponentProps<typeof ImageCardNode> = { id: 'fixture', data: card, selected: true,
  type: 'imageCard', dragging: false, draggable: true, selectable: true, deletable: true, zIndex: 0,
  isConnectable: false, positionAbsoluteX: 0, positionAbsoluteY: 0 };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('blocks unsupported Ark actions on both toolbars and updates when the provider changes', () => {
  useCreationSetupStore.setState({ providers: [
    { id: 'volcengine', name: 'Ark', is_configured: true, supported_models: [], capabilities: ['txt2img', 'img2img'], upload_disclosure: '' },
    { id: 'fal', name: 'Fal', is_configured: true, supported_models: [], capabilities: ['txt2img', 'img2img', 'inpaint', 'upscale'], upload_disclosure: '' },
  ] });
  useCreativeStore.setState({ connectionId: 'volcengine', referenceImage: null });
  const openInpaint = vi.spyOn(useCreativeStore.getState(), 'openInpaint');
  render(<><FloatingCardToolbar nodeId="fixture" data={card} />
    <ImageCardNode {...nodeProps} /></>);
  expect(screen.getByRole('button', { name: 'Vary' }).hasAttribute('disabled')).toBe(false);
  for (const name of ['Inpaint', 'Inpaint / Mask', 'Upscale', 'Upscale Image', 'Animate', 'Animate (Image-to-Video)']) {
    expect(screen.getByRole('button', { name }).hasAttribute('disabled')).toBe(true);
  }
  fireEvent.click(screen.getByRole('button', { name: 'Inpaint' }));
  expect(openInpaint).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Reuse' }).hasAttribute('disabled')).toBe(false);
  expect(screen.getByRole('button', { name: 'Export Asset' }).hasAttribute('disabled')).toBe(false);
  act(() => useCreativeStore.setState({ connectionId: 'fal_ai' }));
  expect(screen.getByRole('button', { name: 'Inpaint' }).hasAttribute('disabled')).toBe(false);
  expect(screen.getByRole('button', { name: 'Upscale' }).hasAttribute('disabled')).toBe(false);
});

it('does not advertise editing for a txt2img-only provider or an unknown cloud catalog', () => {
  useCreationSetupStore.setState({ providers: [{ id: 'openai', name: 'OpenAI', is_configured: true,
    supported_models: ['dall-e-3'], capabilities: ['txt2img'], upload_disclosure: '' }] });
  useCreativeStore.setState({ connectionId: 'openai' });
  render(<FloatingCardToolbar nodeId="fixture" data={card} />);
  expect(screen.getByRole('button', { name: 'Vary' }).hasAttribute('disabled')).toBe(true);
  act(() => useCreationSetupStore.setState({ providers: [] }));
  expect(screen.getByRole('button', { name: 'Vary' }).hasAttribute('disabled')).toBe(true);
  act(() => useCreativeStore.setState({ connectionId: 'comfyui-managed' }));
  expect(screen.getByRole('button', { name: 'Inpaint' }).hasAttribute('disabled')).toBe(false);
});
