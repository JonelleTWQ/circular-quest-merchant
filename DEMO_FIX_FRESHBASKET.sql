-- OPTIONAL DEMO-ONLY reset of fictional products. DO NOT use for real expired goods.
-- Change dates to valid upcoming dates and restore eligible quantities for two fictional batches.
UPDATE public.surplus_batches b
SET expiry_date = CURRENT_DATE + 5,
    eligible_until = CURRENT_DATE + 4,
    status = 'active',
    quantity_eligible = quantity_registered,
    quantity_remaining = quantity_registered,
    unit_weight_kg = CASE WHEN merchant_sku='YOG101' THEN 0.15 ELSE 0.08 END,
    product_condition = 'Near expiry',
    expected_unsold_fate = 'Disposed',
    disposal_probability = 0.50
WHERE b.merchant_id IN (SELECT id FROM public.merchants WHERE merchant_name='FreshBasket')
  AND b.merchant_sku IN ('YOG101','BUN202');
-- This assumes these are test-only rows with no actual completed sales.
