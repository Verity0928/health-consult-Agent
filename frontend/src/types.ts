export interface LLMConfig {
  base_url: string;
  api_key: string;
  model: string;
  embedding_model?: string;
}

export interface ChatTurnRequest {
  session_id: string;
  message: string;
  llm_config: LLMConfig;
}

export type ChatStatus = 'answered' | 'asked' | 'handoff' | 'closed';

export interface SelfCheckResult {
  compliance_pass: boolean;
  grounding_pass: boolean;
  disclaimer_pass: boolean;
  format_pass: boolean;
  overall_pass: boolean;
  violations: string[];
}

export interface PipelineDebugInfo {
  route_scope: string | null;
  sub_type: string | null;
  population_status: string | null;
  hit_status: string | null;
  route_decision: string | null;
  handoff_reason: string | null;
  self_check: SelfCheckResult | null;
  retry_count: number;
}

export interface PipelineResult {
  reply: string;
  status: ChatStatus;
  debug: PipelineDebugInfo;
}
