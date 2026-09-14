-- Thin passthrough. Every column is defined in dbt (dbt/models/marts/fct_orders.sql); nothing
-- is computed here, so the mart stays the single definition of what a column means.
select * from refarch_marts.fct_orders
