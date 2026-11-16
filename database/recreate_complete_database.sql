-- ==============================================================================
-- 🚦 V.I.T.A.L.S. - COMPLETE SUPABASE DATABASE RESTORATION SCRIPT
-- ==============================================================================
-- Run this entire script in your new Supabase project's SQL Editor:
-- (Supabase Dashboard -> SQL Editor -> New Query -> Paste & Run)
--
-- This script creates:
--   1. Extensions & Custom ENUMs
--   2. All 17 Relational Tables
--   3. Foreign Key Constraints & Performance Indexes
--   4. Automation Functions & Payment Triggers
--   5. Row Level Security (RLS) Policies
--   6. Essential Seed Data (Fine rates, Cameras, Bhopal Parking Lots, Test Vehicles)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. EXTENSIONS & ENUMS
-- ------------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

DO $$ BEGIN
    CREATE TYPE public.user_role AS ENUM ('citizen', 'admin', 'officer');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE public.violation_status AS ENUM ('pending', 'verified', 'rejected', 'paid');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ------------------------------------------------------------------------------
-- 2. USERS & ROLES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  email TEXT NOT NULL,
  password TEXT NOT NULL,
  phone TEXT NULL,
  created_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT users_pkey PRIMARY KEY (id),
  CONSTRAINT users_email_key UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS public.user_roles (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  role public.user_role NULL DEFAULT 'citizen'::user_role,
  badge_number TEXT NULL,
  assigned_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT user_roles_pkey PRIMARY KEY (id),
  CONSTRAINT user_roles_user_id_key UNIQUE (user_id),
  CONSTRAINT user_roles_badge_number_key UNIQUE (badge_number),
  CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);

-- ------------------------------------------------------------------------------
-- 3. CAMERAS & SURVEILLANCE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.surveillance_cameras (
  id TEXT NOT NULL DEFAULT gen_random_uuid()::TEXT,
  location_name TEXT NOT NULL,
  ip_address TEXT NULL,
  direction TEXT NULL,
  latitude DOUBLE PRECISION NULL,
  longitude DOUBLE PRECISION NULL,
  is_active BOOLEAN NULL DEFAULT true,
  api_key TEXT NULL DEFAULT gen_random_uuid()::TEXT,
  managed_by UUID NULL,
  officer_id UUID NULL,
  created_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT surveillance_cameras_pkey PRIMARY KEY (id),
  CONSTRAINT surveillance_cameras_managed_by_fkey FOREIGN KEY (managed_by) REFERENCES public.users(id) ON DELETE SET NULL,
  CONSTRAINT surveillance_cameras_officer_id_fkey FOREIGN KEY (officer_id) REFERENCES public.user_roles(id) ON DELETE SET NULL
);

-- ------------------------------------------------------------------------------
-- 4. CONGESTION, TRAFFIC SIGNALS & INTERSECTION STATUS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.congested_roads (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  road_name TEXT NOT NULL,
  area TEXT NULL,
  camera_id TEXT NULL,
  congestion_level INTEGER NULL DEFAULT 0,
  vehicle_count INTEGER NULL DEFAULT 0,
  current_state TEXT NULL DEFAULT 'red',
  recommended_time INTEGER NULL DEFAULT 30,
  is_emergency BOOLEAN NULL DEFAULT false,
  is_closed BOOLEAN NULL DEFAULT false,
  danger_level TEXT NULL DEFAULT 'Low',
  wsi_score DOUBLE PRECISION NULL DEFAULT 0.0,
  last_updated TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT congested_roads_pkey PRIMARY KEY (id),
  CONSTRAINT signal_state_check CHECK (current_state = ANY (ARRAY['red'::TEXT, 'yellow'::TEXT, 'green'::TEXT]))
);

CREATE INDEX IF NOT EXISTS idx_congested_roads_name ON public.congested_roads(road_name);
CREATE INDEX IF NOT EXISTS idx_congested_roads_camera ON public.congested_roads(camera_id);

CREATE TABLE IF NOT EXISTS public.intersection_status (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  intersection_name TEXT NOT NULL DEFAULT 'Main Intersection',
  lane_direction TEXT NOT NULL,
  camera_id TEXT NULL,
  signal_state TEXT NULL DEFAULT 'red',
  green_duration INTEGER NULL DEFAULT 30,
  vehicle_count INTEGER NULL DEFAULT 0,
  is_emergency BOOLEAN NULL DEFAULT false,
  active_corridor BOOLEAN NULL DEFAULT false,
  last_synced TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT intersection_status_pkey PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_intersection_lane ON public.intersection_status(intersection_name, lane_direction);

CREATE TABLE IF NOT EXISTS public.traffic_signals (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  camera_id TEXT NULL,
  current_state TEXT NULL DEFAULT 'red',
  vehicle_count INTEGER NULL DEFAULT 0,
  recommended_time INTEGER NULL DEFAULT 30,
  is_emergency BOOLEAN NULL DEFAULT false,
  last_updated TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT traffic_signals_pkey PRIMARY KEY (id),
  CONSTRAINT traffic_signals_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.surveillance_cameras(id) ON DELETE CASCADE,
  CONSTRAINT traffic_signals_state_check CHECK (current_state = ANY (ARRAY['red'::TEXT, 'yellow'::TEXT, 'green'::TEXT]))
);

-- ------------------------------------------------------------------------------
-- 5. ACCIDENTS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.accidents (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  camera_id TEXT NULL,
  description TEXT NULL,
  reported_by UUID NULL,
  injuries INTEGER NULL DEFAULT 0,
  fatalities INTEGER NULL DEFAULT 0,
  severity TEXT NULL DEFAULT 'Minor',
  latitude DOUBLE PRECISION NULL,
  longitude DOUBLE PRECISION NULL,
  reported_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT accidents_pkey PRIMARY KEY (id),
  CONSTRAINT accidents_reported_by_fkey FOREIGN KEY (reported_by) REFERENCES public.users(id) ON DELETE SET NULL
);

-- ------------------------------------------------------------------------------
-- 6. CITIZEN VEHICLES REGISTRY (RTO)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.vehicles (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  plate_number TEXT NOT NULL,
  type TEXT NULL,
  model TEXT NULL,
  owner_name TEXT NULL DEFAULT 'Unknown Owner',
  owner_id UUID NULL,
  phone TEXT NULL,
  vehicle_color TEXT NULL,
  created_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT vehicles_pkey PRIMARY KEY (id),
  CONSTRAINT vehicles_plate_number_key UNIQUE (plate_number),
  CONSTRAINT vehicles_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vehicles_owner_id ON public.vehicles(owner_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_plate_number ON public.vehicles(plate_number);

-- ------------------------------------------------------------------------------
-- 7. VIOLATIONS & FORENSIC RECORDS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.violations (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  camera_id TEXT NULL,
  plate_number TEXT NULL,
  violation_type TEXT NOT NULL,
  evidence_image_url TEXT NOT NULL,
  confidence_score DOUBLE PRECISION NULL,
  status TEXT NULL DEFAULT 'pending',
  location TEXT NULL DEFAULT 'Bhopal City',
  severity TEXT NULL DEFAULT 'medium',
  source TEXT NULL DEFAULT 'live_camera',
  detected_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT violations_pkey PRIMARY KEY (id),
  CONSTRAINT fk_violation_camera FOREIGN KEY (camera_id) REFERENCES public.surveillance_cameras(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_violations_camera_id ON public.violations(camera_id);
CREATE INDEX IF NOT EXISTS idx_violations_status ON public.violations(status);
CREATE INDEX IF NOT EXISTS idx_violations_plate_number ON public.violations(plate_number);

-- Forensic table for uploaded batch test/surveillance video files
CREATE TABLE IF NOT EXISTS public.uploaded_video_violations (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  job_id TEXT NULL,
  video_filename TEXT NULL,
  camera_id TEXT NULL,
  location TEXT NULL,
  latitude DOUBLE PRECISION NULL,
  longitude DOUBLE PRECISION NULL,
  violation_type TEXT NOT NULL,
  plate_number TEXT NULL,
  confidence_score DOUBLE PRECISION NULL,
  hit_ratio DOUBLE PRECISION NULL,
  evaluable_frames INTEGER NULL,
  sha256_hash TEXT NULL,
  evidence_image_url TEXT NOT NULL,
  raw_frame_url TEXT NULL,
  status TEXT NULL DEFAULT 'pending',
  severity TEXT NULL DEFAULT 'medium',
  is_auto_verified BOOLEAN NULL DEFAULT false,
  detected_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT uploaded_video_violations_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_uploaded_violations_job_id ON public.uploaded_video_violations(job_id);
CREATE INDEX IF NOT EXISTS idx_uploaded_violations_plate ON public.uploaded_video_violations(plate_number);

-- ------------------------------------------------------------------------------
-- 8. E-CHALLANS & PAYMENTS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.e_challans (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  violation_id UUID NULL,
  vehicle_number TEXT NULL,
  amount NUMERIC(10, 2) NOT NULL,
  status TEXT NULL DEFAULT 'unpaid',
  owner_name TEXT NULL,
  owner_id UUID NULL,
  phone_number TEXT NULL,
  issued_by TEXT NULL,
  location TEXT NULL DEFAULT 'Unknown',
  is_strategic BOOLEAN NULL DEFAULT false,
  issued_at TIMESTAMPTZ NULL DEFAULT now(),
  due_date TIMESTAMPTZ NULL,
  paid_at TIMESTAMPTZ NULL,
  CONSTRAINT e_challans_pkey PRIMARY KEY (id),
  CONSTRAINT e_challans_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL,
  CONSTRAINT e_challans_violation_id_fkey FOREIGN KEY (violation_id) REFERENCES public.violations(id) ON DELETE CASCADE,
  CONSTRAINT e_challans_status_check CHECK (status = ANY (ARRAY['unpaid'::TEXT, 'paid'::TEXT, 'disputed'::TEXT]))
);

CREATE INDEX IF NOT EXISTS idx_e_challans_issued_by ON public.e_challans(issued_by);
CREATE INDEX IF NOT EXISTS idx_e_challans_owner_id ON public.e_challans(owner_id);
CREATE INDEX IF NOT EXISTS idx_e_challans_vehicle_number ON public.e_challans(vehicle_number);
CREATE INDEX IF NOT EXISTS idx_e_challans_status ON public.e_challans(status);

CREATE TABLE IF NOT EXISTS public.payments (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  challan_id UUID NULL,
  user_id UUID NULL,
  amount NUMERIC(10, 2) NOT NULL,
  payment_method TEXT NULL DEFAULT 'UPI',
  transaction_id TEXT NULL DEFAULT ('TXN-' || substr(gen_random_uuid()::text, 1, 8)),
  status TEXT NULL DEFAULT 'success',
  paid_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT payments_pkey PRIMARY KEY (id),
  CONSTRAINT payments_transaction_id_key UNIQUE (transaction_id),
  CONSTRAINT payments_challan_id_fkey FOREIGN KEY (challan_id) REFERENCES public.e_challans(id) ON DELETE CASCADE,
  CONSTRAINT payments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_payments_challan_id ON public.payments(challan_id);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON public.payments(user_id);

-- ------------------------------------------------------------------------------
-- 9. PARKING MANAGEMENT
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.parking_lots (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  location TEXT NULL,
  total_slots INTEGER NULL DEFAULT 50,
  occupied INTEGER NULL DEFAULT 0,
  latitude DOUBLE PRECISION NULL,
  longitude DOUBLE PRECISION NULL,
  updated_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT parking_lots_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.parking_requests (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  parking_lot_id UUID NULL,
  vehicle_number TEXT NULL,
  reason TEXT NULL,
  estimated_duration INTEGER NULL DEFAULT 60,
  status TEXT NULL DEFAULT 'pending',
  approved_by UUID NULL,
  created_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT parking_requests_pkey PRIMARY KEY (id),
  CONSTRAINT parking_requests_parking_lot_id_fkey FOREIGN KEY (parking_lot_id) REFERENCES public.parking_lots(id) ON DELETE CASCADE,
  CONSTRAINT parking_requests_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id) ON DELETE SET NULL
);

-- ------------------------------------------------------------------------------
-- 10. SYSTEM CONFIGURATION & AUDIT
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.system_configs (
  key TEXT NOT NULL,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT system_configs_pkey PRIMARY KEY (key)
);

CREATE TABLE IF NOT EXISTS public.ptu_settings (
  key TEXT NOT NULL,
  value NUMERIC NOT NULL,
  updated_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT ptu_settings_pkey PRIMARY KEY (key)
);

CREATE TABLE IF NOT EXISTS public.audit_logs (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  changed_by UUID NULL,
  action_type TEXT NOT NULL,
  table_name TEXT NOT NULL,
  record_id UUID NULL,
  payload JSONB NULL,
  created_at TIMESTAMPTZ NULL DEFAULT now(),
  CONSTRAINT audit_logs_pkey PRIMARY KEY (id),
  CONSTRAINT audit_logs_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_changed_by ON public.audit_logs(changed_by);
CREATE INDEX IF NOT EXISTS idx_audit_logs_table_record ON public.audit_logs(table_name, record_id);

-- ------------------------------------------------------------------------------
-- 11. AUTOMATION TRIGGERS & FUNCTIONS
-- ------------------------------------------------------------------------------
-- Automatically log violation status updates into audit_logs
CREATE OR REPLACE FUNCTION public.log_violation_changes()
RETURNS TRIGGER AS $$
BEGIN
  IF (OLD.status IS DISTINCT FROM NEW.status) THEN
    INSERT INTO public.audit_logs (changed_by, action_type, table_name, record_id, payload)
    VALUES (
      auth.uid(), 
      'UPDATE_STATUS_' || NEW.status, 
      'violations', 
      NEW.id, 
      jsonb_build_object('old_status', OLD.status, 'new_status', NEW.status)
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_violation_status_change ON public.violations;
CREATE TRIGGER on_violation_status_change
  AFTER UPDATE ON public.violations
  FOR EACH ROW
  EXECUTE FUNCTION public.log_violation_changes();

-- Automatically update e_challan and linked violation when payment is recorded
CREATE OR REPLACE FUNCTION public.handle_payment_success()
RETURNS TRIGGER AS $$
BEGIN
  -- Mark challan as paid
  UPDATE public.e_challans 
  SET status = 'paid', paid_at = now()
  WHERE id = NEW.challan_id;

  -- Mark corresponding violation as paid
  UPDATE public.violations
  SET status = 'paid'
  WHERE id = (SELECT violation_id FROM public.e_challans WHERE id = NEW.challan_id);

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_payment_completed ON public.payments;
CREATE TRIGGER on_payment_completed
  AFTER INSERT ON public.payments
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_payment_success();

-- ------------------------------------------------------------------------------
-- 12. ROW LEVEL SECURITY (RLS) POLICIES
-- ------------------------------------------------------------------------------
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.e_challans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.violations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.congested_roads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.surveillance_cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicles ENABLE ROW LEVEL SECURITY;

-- Allow backend service_role and public reads where appropriate for dashboard
CREATE POLICY "Allow public read on user_roles" ON public.user_roles FOR SELECT USING (true);
CREATE POLICY "Allow public read on payments" ON public.payments FOR SELECT USING (true);
CREATE POLICY "Allow public read on e_challans" ON public.e_challans FOR SELECT USING (true);
CREATE POLICY "Allow public read on violations" ON public.violations FOR SELECT USING (true);
CREATE POLICY "Allow public read on congested_roads" ON public.congested_roads FOR SELECT USING (true);
CREATE POLICY "Allow public read on surveillance_cameras" ON public.surveillance_cameras FOR SELECT USING (true);
CREATE POLICY "Allow public read on vehicles" ON public.vehicles FOR SELECT USING (true);
CREATE POLICY "Allow public read on audit_logs" ON public.audit_logs FOR SELECT USING (true);

-- ------------------------------------------------------------------------------
-- 13. SEED DATA (ESSENTIAL CONFIGURATION & SAMPLE DATA)
-- ------------------------------------------------------------------------------

-- 1. System Fine Multipliers (Critical for settings.py and challans.py)
INSERT INTO public.system_configs (key, value)
VALUES (
  'fine_multipliers',
  '{
    "no_helmet": 500,
    "triple_riding": 1000,
    "red_light_jump": 1000,
    "speeding": 1500,
    "wrong_side": 800,
    "no_parking": 500
  }'::JSONB
) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- 2. PTU Base Settings
INSERT INTO public.ptu_settings (key, value)
VALUES 
  ('helmet_fine', 500),
  ('triple_fine', 1000),
  ('red_light_fine', 1000)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- 3. Bhopal Surveillance Cameras
INSERT INTO public.surveillance_cameras (id, location_name, direction, latitude, longitude, is_active)
VALUES 
  ('cam_0', 'MP Nagar Zone-1 Junction', 'North', 23.2332, 77.4343, true),
  ('cam_1', 'DB City Mall Square', 'East', 23.2325, 77.4312, true),
  ('cam_2', 'Roshanpura Square', 'South', 23.2421, 77.3995, true),
  ('cam_3', 'Board Office Chauraha', 'West', 23.2384, 77.4289, true)
ON CONFLICT (id) DO UPDATE SET location_name = EXCLUDED.location_name;

-- 4. Bhopal Congested Roads (GIS Feed for React Dashboard)
INSERT INTO public.congested_roads (road_name, area, camera_id, congestion_level, vehicle_count, current_state, danger_level, wsi_score)
VALUES 
  ('Hoshangabad Road (MP Nagar)', 'MP Nagar', 'cam_0', 35, 12, 'green', 'Low', 0.2),
  ('Jail Road to DB Mall', 'Arera Hills', 'cam_1', 65, 24, 'red', 'Medium', 0.6),
  ('Roshanpura Link Road', 'New Market', 'cam_2', 45, 18, 'yellow', 'Low', 0.3),
  ('Link Road No. 1', 'Shivaji Nagar', 'cam_3', 20, 8, 'green', 'Low', 0.1)
ON CONFLICT DO NOTHING;

-- 5. Bhopal 4-Way Intersection Status
INSERT INTO public.intersection_status (intersection_name, lane_direction, camera_id, signal_state, green_duration, vehicle_count)
VALUES 
  ('Bhopal Main Square', 'N', 'cam_0', 'green', 45, 22),
  ('Bhopal Main Square', 'S', 'cam_2', 'red', 30, 14),
  ('Bhopal Main Square', 'E', 'cam_1', 'red', 30, 19),
  ('Bhopal Main Square', 'W', 'cam_3', 'red', 30, 11)
ON CONFLICT (intersection_name, lane_direction) DO NOTHING;

-- 6. Bhopal Smart Parking Facilities
INSERT INTO public.parking_lots (name, location, total_slots, occupied, latitude, longitude)
VALUES 
  ('MP Nagar Multi-Level Parking', 'Zone-I, MP Nagar', 200, 75, 23.2340, 77.4330),
  ('New Market Underground Parking', 'TT Nagar, Bhopal', 150, 92, 23.2370, 77.4010),
  ('DB City Mall Visitor Parking', 'Arera Hills, Bhopal', 300, 180, 23.2320, 77.4320),
  ('Bhopal Junction Railway Parking', 'Platform 1, Bhopal', 120, 105, 23.2660, 77.4110)
ON CONFLICT DO NOTHING;

-- 7. Sample Vehicles Registry (Indian Plates for testing ALPR)
INSERT INTO public.vehicles (plate_number, type, model, owner_name, phone, vehicle_color)
VALUES 
  ('MP04AB1234', 'Motorcycle', 'Honda Activa 6G', 'Ramesh Sharma', '+919876543210', 'White'),
  ('MP04CD5678', 'Motorcycle', 'Bajaj Pulsar 150', 'Amit Verma', '+919876543211', 'Black'),
  ('MP04EF9012', 'Car', 'Maruti Suzuki Swift', 'Priya Patel', '+919876543212', 'Red'),
  ('MP04GH3456', 'Motorcycle', 'TVS Jupiter', 'Vikram Singh', '+919876543213', 'Grey')
ON CONFLICT (plate_number) DO NOTHING;

-- ==============================================================================
-- ✅ RESTORATION COMPLETE
-- All 17 tables, triggers, policies, and initial configurations are ready.
-- ==============================================================================
