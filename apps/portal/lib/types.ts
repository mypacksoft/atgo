export type User = {
  id: number;
  email: string;
  full_name: string | null;
  is_super_admin: boolean;
};

export type Tenant = {
  id: number;
  slug: string;
  name: string;
  plan_id: string;
  primary_domain: string | null;
  default_timezone: string;
  billing_country: string | null;
  is_active: boolean;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  user: User;
  tenant: Tenant | null;
};

export type Device = {
  id: number;
  name: string;
  serial_number: string;
  device_code: string;
  model: string | null;
  firmware_version: string | null;
  status: string;
  is_online: boolean;
  last_seen_at: string | null;
  timezone: string | null;
  branch_id: number | null;
  pending_commands_count: number;
};

export type DeviceClaim = {
  device_id: number;
  device_code: string;
  claim_code: string;
  claim_expires_at: string;
  adms_setup: { host: string; port: number; https: boolean; instructions: string[] };
};

export type Employee = {
  id: number;
  employee_code: string;
  device_pin: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  branch_id: number | null;
  department_id: number | null;
  is_active: boolean;
  hired_at: string | null;
};

export type Branch = {
  id: number;
  code: string;
  name: string;
  timezone: string | null;
  address: string | null;
  is_active: boolean;
};

export type Department = {
  id: number;
  code: string;
  name: string;
  parent_id: number | null;
  is_active: boolean;
};

export type DomainRow = {
  id: number;
  domain: string;
  normalized_domain: string;
  domain_type: string;
  status: string;
  is_primary: boolean;
  cname_target: string | null;
  txt_record_name: string | null;
  txt_record_value: string | null;
  ssl_status: string;
  expires_at: string | null;
  verified_at: string | null;
};

export type ApiKeyRow = {
  id: number;
  name: string;
  prefix: string;
  scopes: string[];
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

export type PricingPlan = {
  plan_id: string;
  name: string;
  amount_local: number;
  currency: string;
  tax_inclusive: boolean;
};

export type PricingResponse = {
  country: string;
  currency: string;
  providers: string[];
  default_provider: string;
  tax_inclusive: boolean;
  plans: PricingPlan[];
};

export type TimesheetRow = {
  employee_id: number;
  employee_code: string;
  full_name: string;
  work_date: string;
  first_check_in: string | null;
  last_check_out: string | null;
  total_punches: number;
  worked_minutes: number | null;
  status: string | null;
};

export type AttendanceLog = {
  id: number;
  employee_id: number | null;
  device_pin: string;
  device_id: number;
  punched_at: string;
  punch_state: number | null;
  verify_type: number | null;
};
