export type DataType = 'string' | 'image' | 'audio' | 'video' | 'json';

export type PortValue = string | number | boolean | Record<string, unknown> | unknown[];

export interface NodePort {
  id: string;
  name: string;
  type: DataType;
  required?: boolean;
  default_value?: PortValue;
}

export type ParameterType = 'string' | 'textarea' | 'number' | 'boolean' | 'select';

export interface SelectOption {
  label: string;
  value: string | number | boolean;
}

export interface ParameterDef {
  name: string;
  label: string;
  type: ParameterType;
  default?: string | number | boolean;
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

export type ExecutionStatus = 'idle' | 'queued' | 'running' | 'cached' | 'completed' | 'error' | 'cancelled';

export type NodeParamValue = string | number | boolean | Record<string, unknown> | unknown[];
export type NodeOutputValue = string | number | boolean | Record<string, unknown> | unknown[];

export interface CustomNodeData extends Record<string, unknown> {
  definition: NodeDefinition;
  params: Record<string, NodeParamValue>;
  status: ExecutionStatus;
  output?: Record<string, NodeOutputValue>;
  errorMessage?: string;
}

