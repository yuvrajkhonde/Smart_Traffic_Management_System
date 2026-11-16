-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================

ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.e_challans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.violations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.congested_roads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.surveillance_cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicles ENABLE ROW LEVEL SECURITY;

-- Allow public read access where needed by officer & citizen dashboards
DROP POLICY IF EXISTS "Allow public read on user_roles" ON public.user_roles;
CREATE POLICY "Allow public read on user_roles" ON public.user_roles FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow public read on payments" ON public.payments;
CREATE POLICY "Allow public read on payments" ON public.payments FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow public read on e_challans" ON public.e_challans;
CREATE POLICY "Allow public read on e_challans" ON public.e_challans FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow public read on violations" ON public.violations;
CREATE POLICY "Allow public read on violations" ON public.violations FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow public read on congested_roads" ON public.congested_roads;
CREATE POLICY "Allow public read on congested_roads" ON public.congested_roads FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow public read on surveillance_cameras" ON public.surveillance_cameras;
CREATE POLICY "Allow public read on surveillance_cameras" ON public.surveillance_cameras FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow public read on vehicles" ON public.vehicles;
CREATE POLICY "Allow public read on vehicles" ON public.vehicles FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow public read on audit_logs" ON public.audit_logs;
CREATE POLICY "Allow public read on audit_logs" ON public.audit_logs FOR SELECT USING (true);
