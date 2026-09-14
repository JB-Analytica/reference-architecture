{#- realised_net_amount_eur must equal net_amount_eur on a live order and 0 on a cancelled one.

    This is the invariant that keeps "revenue" meaning one thing across the marts. It was not
    always true: fct_orders used to count cancelled orders in its only revenue column while
    dim_customers quietly excluded them, so the same word meant two different numbers depending
    on which mart you asked. If this test fails, that has happened again.

    One test covering both fact tables: the rule is the same rule, and splitting it would let
    one half be changed without the other. -#}

with orders as (

    select
        'fct_orders' as model,
        cast(order_id as varchar) as row_key,
        net_amount_eur,
        realised_net_amount_eur,
        is_cancelled
    from {{ ref('fct_orders') }}

),

items as (

    select
        'fct_order_items' as model,
        cast(order_item_id as varchar) as row_key,
        net_amount_eur,
        realised_net_amount_eur,
        is_cancelled
    from {{ ref('fct_order_items') }}

),

combined as (

    select * from orders
    union all
    select * from items

)

select *
from combined
where realised_net_amount_eur
      != case when is_cancelled then 0 else net_amount_eur end
