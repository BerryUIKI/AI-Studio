import { Node } from '@xyflow/react';
import { CanvasNodeData } from '../types/creative';

export function nextResultPosition(nodes: Node<CanvasNodeData>[], sourceId?: string): { x: number; y: number } {
  const source = nodes.find((node) => node.data.assetId === sourceId);
  const position = source ? { x: source.position.x + 360, y: source.position.y }
    : { x: 80, y: 80 };
  while (nodes.some((node) => Math.abs(node.position.x - position.x) < 340 && Math.abs(node.position.y - position.y) < 420)) {
    position.y += 440;
  }
  return position;
}
