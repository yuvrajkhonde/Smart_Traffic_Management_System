-- Automated Trigger: Sync payment settlement across e_challans and violations
CREATE OR REPLACE FUNCTION public.handle_payment_success()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.e_challans 
    SET status = 'paid', paid_at = now() 
    WHERE id = NEW.challan_id;

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
