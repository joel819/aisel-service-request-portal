export const SERVICE_TYPES = [
  "website_digital_presence",
  "business_automation",
  "cloud_infrastructure",
  "devops_observability",
  "ai_automation",
] as const;
export const PRIORITIES = ["low", "medium", "high", "critical"] as const;
export const STATUSES = ["new", "in_review", "in_progress", "completed", "cancelled"] as const;

export type ServiceType = (typeof SERVICE_TYPES)[number];
export type Priority = (typeof PRIORITIES)[number];
export type Status = (typeof STATUSES)[number];

export interface ServiceRequest {
  id: number;
  reference: string;
  client_name: string;
  contact_name: string;
  service_type: ServiceType;
  priority: Priority;
  status: Status;
  description: string;
  created_by_id: number;
  created_at: string;
  updated_at: string;
}

export interface RequestPage {
  items: ServiceRequest[];
  total: number;
  page: number;
  page_size: number;
}

export interface RequestInput {
  client_name: string;
  contact_name: string;
  service_type: ServiceType;
  priority?: Priority;
  description: string;
}

const LABEL_OVERRIDES: Record<string, string> = {
  devops_observability: "DevOps & observability",
  ai_automation: "AI automation",
};

export function label(value: string): string {
  if (value in LABEL_OVERRIDES) return LABEL_OVERRIDES[value];
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
