export type DataType = 'string' | 'image' | 'audio' | 'video' | 'json';

export interface NodePort {
  id: string;
  name: string;
  type: DataType;
  required?: boolean;
  default_value?: any;
}

export type ParameterType = 'string' | 'textarea' | 'number' | 'boolean' | 'select';

export interface SelectOption {
  label: string;
  value: any;
}

export interface ParameterDef {
  name: string;
  label: string;
  type: ParameterType;
  default?: any;
  description?: string;
  options?: SelectOption[];
  min_value?: number;
  max_value?: number;
  step?: number;
}

export type NodeCategory = 'input' | 'text' | 'image' | 'audio' | 'video' | 'output';

export interface NodeDefinition {
  type: string;
  title: string;
  category: NodeCategory;
  description: string;
  inputs: NodePort[];
  outputs: NodePort[];
  parameters: ParameterDef[];
}

export type ExecutionStatus = 'idle' | 'queued' | 'running' | 'cached' | 'completed' | 'error';

export interface CustomNodeData extends Record<string, unknown> {
  definition: NodeDefinition;
  params: Record<string, any>;
  status: ExecutionStatus;
  output?: Record<string, any>;
  errorMessage?: string;
}
