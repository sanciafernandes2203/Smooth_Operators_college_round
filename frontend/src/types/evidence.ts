export type EvidenceRelationship =
  | 'supports'
  | 'contradicts'
  | 'context'
  | 'insufficient'

export interface EvidenceItem {
  document_id: string
  document_name: string
  page_number: number | null
  quote: string
  relationship: EvidenceRelationship
  validated: boolean
}
