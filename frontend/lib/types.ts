export type User = {
  id: string;
  full_name: string;
  email: string;
  role: "administrator" | "asset_manager" | "technician" | "employee";
  is_active: boolean;
  department_id?: string | null;
  department_name?: string | null;
};

export type Department = { id: string; name: string; description: string | null; employee_count: number };

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type Asset = {
  id: string;
  asset_tag: string;
  serial_number: string | null;
  name: string;
  description: string | null;
  category_id: string;
  category_name: string;
  location_id: string;
  location_name: string;
  vendor_id?: string | null;
  purchase_date?: string;
  purchase_cost?: string;
  company_currency?: string;
  residual_value?: string;
  useful_life_months?: number;
  status: "available" | "assigned" | "in_repair" | "retired";
  current_assignee_id: string | null;
  current_assignee_name: string | null;
};

export type DirectoryEntry = { id: string; name: string; description?: string | null; code?: string | null };
export type UserOption = { id: string; full_name: string; role: User["role"] };
export type Vendor = {
  id: string;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  is_active: boolean;
};
export type WorkOrder = {
  id: string;
  asset_id: string;
  asset_tag: string;
  plan_id: string | null;
  title: string;
  description: string | null;
  priority: "low" | "medium" | "high" | "critical";
  status: "open" | "in_progress" | "completed" | "cancelled";
  requested_by_id: string;
  assigned_to_id: string | null;
  due_date: string | null;
  completed_at: string | null;
  resolution: string | null;
};
export type Notification = { id: string; title: string; message: string; read_at: string | null; created_at: string };
