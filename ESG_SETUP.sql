-- Circular Quest hackathon demonstration migration.
-- Run once in Supabase SQL Editor. NOT production authentication/security.
ALTER TABLE public.surplus_batches ADD COLUMN IF NOT EXISTS unit_weight_kg numeric;
ALTER TABLE public.surplus_batches ADD COLUMN IF NOT EXISTS product_condition text;
ALTER TABLE public.surplus_batches ADD COLUMN IF NOT EXISTS expected_unsold_fate text;
ALTER TABLE public.surplus_batches ADD COLUMN IF NOT EXISTS disposal_probability numeric;

CREATE TABLE IF NOT EXISTS public.surplus_sales (
  id bigint generated always as identity primary key,
  merchant_id bigint NOT NULL references public.merchants(id),
  surplus_batch_id bigint NOT NULL references public.surplus_batches(id),
  receipt_ref text NOT NULL,
  quantity integer NOT NULL CHECK (quantity > 0),
  unit_sale_price numeric NOT NULL,
  unit_original_price numeric NOT NULL,
  unit_weight_kg numeric,
  product_condition text,
  expected_unsold_fate text,
  disposal_probability numeric,
  co2e_per_unit numeric,
  refunded boolean NOT NULL DEFAULT false,
  sold_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (merchant_id, receipt_ref, surplus_batch_id)
);
ALTER TABLE public.surplus_sales ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Demo read sales" ON public.surplus_sales;
CREATE POLICY "Demo read sales" ON public.surplus_sales FOR SELECT TO anon, authenticated USING (true);

-- Atomic demonstration checkout: lock batch, validate, decrement, snapshot and record sale.
-- SECURITY DEFINER is intentionally demo-only; replace with authenticated merchant authorization.
CREATE OR REPLACE FUNCTION public.record_surplus_sale(
 p_merchant_id bigint, p_batch_id bigint, p_quantity integer, p_receipt_ref text
) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE b public.surplus_batches%ROWTYPE; new_sale_id bigint;
BEGIN
 IF p_quantity <= 0 OR trim(coalesce(p_receipt_ref,'')) = '' THEN
   RAISE EXCEPTION 'Invalid sale quantity or receipt reference';
 END IF;
 SELECT * INTO b FROM public.surplus_batches WHERE id=p_batch_id FOR UPDATE;
 IF NOT FOUND OR b.merchant_id <> p_merchant_id THEN RAISE EXCEPTION 'Batch not found for merchant'; END IF;
 IF b.status NOT IN ('active','partially_eligible') OR b.eligible_until < CURRENT_DATE OR b.quantity_remaining < p_quantity THEN
   RAISE EXCEPTION 'Batch is ineligible, expired, or has insufficient stock';
 END IF;
 INSERT INTO public.surplus_sales (
  merchant_id,surplus_batch_id,receipt_ref,quantity,unit_sale_price,unit_original_price,
  unit_weight_kg,product_condition,expected_unsold_fate,disposal_probability,co2e_per_unit
 ) VALUES (
  p_merchant_id,p_batch_id,trim(p_receipt_ref),p_quantity,b.surplus_price,b.original_price,
  b.unit_weight_kg,b.product_condition,b.expected_unsold_fate,b.disposal_probability,b.co2e_per_unit
 ) RETURNING id INTO new_sale_id;
 UPDATE public.surplus_batches SET
  quantity_remaining = quantity_remaining - p_quantity,
  status = CASE WHEN quantity_remaining - p_quantity = 0 THEN 'sold_out' ELSE status END
 WHERE id = p_batch_id;
 RETURN new_sale_id;
END $$;
REVOKE ALL ON FUNCTION public.record_surplus_sale(bigint,bigint,integer,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.record_surplus_sale(bigint,bigint,integer,text) TO anon, authenticated;

-- Example demo merchant baseline: FreshBasket gets a current-month allowance.
INSERT INTO public.merchant_monthly_stats
 (merchant_id, month, units_procured, units_normal_sales, units_surplus, eligible_surplus_cap)
SELECT m.id, date_trunc('month', current_date)::date, 1000, 900, 100, 100
FROM public.merchants m
WHERE m.merchant_name = 'FreshBasket'
AND NOT EXISTS (
 SELECT 1 FROM public.merchant_monthly_stats x
 WHERE x.merchant_id=m.id AND x.month=date_trunc('month', current_date)::date
);
