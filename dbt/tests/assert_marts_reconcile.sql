{#- The marts must agree with each other on money.

    Every check here compares two numbers that are computed independently, by different models,
    from the same underlying cents. Nothing in a single model can make them agree by accident,
    which is the point: this is the test that would have caught the cents_to_eur precedence bug
    on the day it was written. That bug made fct_order_items.net_amount_eur a hundred times too
    large while fct_orders was fine, and every per-row value still looked plausible. Only the
    comparison was absurd.

    Tolerance is half a cent, and it is there to absorb float representation, not rounding
    drift. Source money is integer cents, and an integer divided by 100 and rounded to two
    decimals is exact, so summing rounded line values equals rounding the summed value. If this
    tolerance ever has to be widened, that means money is being rounded at two different grains
    -- which is a modelling problem to fix, not a number to raise. -#}

{% set tolerance = 0.005 %}

with items_per_order as (

    select
        order_id,
        sum(net_amount_eur)          as booked_eur,
        sum(realised_net_amount_eur) as realised_eur
    from {{ ref('fct_order_items') }}
    group by order_id

),

-- An order's money must equal the sum of its lines, booked and realised alike. The left join
-- is deliberate: an order whose lines went missing should fail here, not be skipped.
orders_vs_items as (

    select
        'fct_orders vs fct_order_items (booked)' as check_name,
        cast(o.order_id as varchar)              as row_key,
        o.net_amount_eur                         as left_value,
        coalesce(i.booked_eur, 0)                as right_value
    from {{ ref('fct_orders') }} o
    left join items_per_order i on o.order_id = i.order_id

    union all

    select
        'fct_orders vs fct_order_items (realised)',
        cast(o.order_id as varchar),
        o.realised_net_amount_eur,
        coalesce(i.realised_eur, 0)
    from {{ ref('fct_orders') }} o
    left join items_per_order i on o.order_id = i.order_id

),

orders_per_customer as (

    select
        customer_id,
        sum(realised_net_amount_eur) as realised_eur
    from {{ ref('fct_orders') }}
    group by customer_id

),

-- A customer's lifetime value must equal their realised order revenue. These two were the
-- pair that disagreed: dim_customers excluded cancelled orders and fct_orders did not.
customers_vs_orders as (

    select
        'dim_customers vs fct_orders (realised)' as check_name,
        cast(c.customer_id as varchar)           as row_key,
        c.lifetime_realised_net_revenue_eur      as left_value,
        coalesce(o.realised_eur, 0)              as right_value
    from {{ ref('dim_customers') }} c
    left join orders_per_customer o on c.customer_id = o.customer_id

),

combined as (

    select * from orders_vs_items
    union all
    select * from customers_vs_orders

)

select
    check_name,
    row_key,
    left_value,
    right_value,
    left_value - right_value as difference
from combined
where abs(left_value - right_value) > {{ tolerance }}
