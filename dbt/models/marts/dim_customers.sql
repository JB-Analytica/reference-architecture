with customers as (

    select * from {{ ref('stg_webshop__customers') }}

),

orders as (

    -- Cancelled orders are excluded here on purpose: a customer's lifetime value is what they
    -- actually bought. Every column derived from this CTE is therefore realised, which is what
    -- the `realised` in its name is for -- see fct_orders for the booked/realised pair.
    select * from {{ ref('stg_webshop__orders') }}
    where order_status != 'cancelled'

),

order_money as (

    select * from {{ ref('int_orders__items_aggregated') }}

),

customer_orders as (

    select
        orders.customer_id,
        count(*) as order_count,
        min(orders.ordered_at) as first_order_at,
        max(orders.ordered_at) as last_order_at,
        sum(order_money.net_amount_cents) as lifetime_realised_net_amount_cents
    -- Left, not inner: the synthetic source produces orders with no lines at all (see
    -- docs/architecture/README.md), and an inner join silently dropped them from the counts.
    -- lifetime_order_count claims to be every non-cancelled order, so it has to count those
    -- too; they contribute nothing to the money, which sum() ignores and the coalesce below
    -- turns into 0 for a customer whose every order was empty.
    from orders
    left join order_money on orders.order_id = order_money.order_id
    group by orders.customer_id

)

select
    customers.customer_id,
    customers.first_name || ' ' || customers.last_name as full_name,
    customers.email,
    customers.phone,
    customers.city,
    customers.country,
    customers.customer_segment,
    -- Display labels live in the mart for the same reason the money columns do: a page may
    -- group and sum what the mart defines, but it may not decide what a value is called.
    -- The raw enum stays alongside as the key to filter and join on.
    {{ sentence_case('customers.customer_segment') }} as segment_label,
    customers.is_marketing_opt_in,
    customers.created_at as customer_since_at,
    customer_orders.first_order_at,
    customer_orders.last_order_at,
    coalesce(customer_orders.order_count, 0) as lifetime_order_count,
    {{ cents_to_eur('coalesce(customer_orders.lifetime_realised_net_amount_cents, 0)') }}
        as lifetime_realised_net_revenue_eur,
    customer_orders.order_count is not null as has_ordered
from customers
left join customer_orders on customers.customer_id = customer_orders.customer_id
