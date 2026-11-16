-- 1. Function to log violation status changes
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

-- 2. Trigger for violation status changes
DROP TRIGGER IF EXISTS on_violation_status_change ON public.violations;
CREATE TRIGGER on_violation_status_change
  AFTER UPDATE ON public.violations
  FOR EACH ROW
  EXECUTE FUNCTION public.log_violation_changes();


-- 3. Function to mark challan and linked violation as paid
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

-- 4. Trigger for payment completion
DROP TRIGGER IF EXISTS on_payment_completed ON public.payments;
CREATE TRIGGER on_payment_completed
  AFTER INSERT ON public.payments
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_payment_success();
