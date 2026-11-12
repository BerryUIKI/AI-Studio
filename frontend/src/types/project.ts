import { Edge, Node } from '@xyflow/react';
import { CanvasNodeData, GenerationProvenance } from './creative';

export interface ProjectViewport {
  x: number;
  y: number;
  zoom: number;
}

export interface GenerationHistoryItem {
  id: string;
  action: string;
  prompt: string;
  timestamp: string;
  assetId?: string;
  imageUrl?: string;
  videoUrl?: string;
  provenance?: GenerationProvenance;
}

export interface ProjectCanvasData {
  version: number;
  nodes: Node<CanvasNodeData>[];
  edges: Edge[];
  viewport: ProjectViewport;
  generationHistory?: GenerationHistoryItem[];
  metadata?: Record<string, unknown>;
}

export interface Project {
  id: string;
  name: string;
  version: number;
  canvas: ProjectCanvasData;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  version: number;
  nodeCount: number;
  updated_at: string;
  created_at: string;
}
