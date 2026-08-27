export type EntityCategory =
  | 'brand'
  | 'person'
  | 'song'
  | 'archival'
  | 'location'
  | 'other'

export type RiskLevel = 'green' | 'yellow' | 'red'

export interface Attempt {
  confidence: number
  risk_level: RiskLevel
  reasoning: string
  retry_query: string
  research_notes: string
}

export interface SearchTrailItem {
  tool: 'web_search' | 'web_fetch'
  args: Record<string, unknown>
}

export interface EntityResult {
  name: string
  category: EntityCategory
  risk: RiskLevel
  attempts: Attempt[]
  search_trail: SearchTrailItem[]
  reasoning: string
  source: 'internal-release-repository' | 'parallel-mcp' | 'agent-memory'
  license_ref?: string
  resolved_at?: string
}

export interface SceneResult {
  id: string
  heading: string
  text: string
  entities: EntityResult[]
}

export interface ClearanceGraphData {
  scenes: SceneResult[]
  warning?: string
}
