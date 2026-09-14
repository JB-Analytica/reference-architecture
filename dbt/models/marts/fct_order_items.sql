with order_items as (

    select * from {{ ref('stg_webshop__order_items') }}

),

orders as (

    select * from {{ ref('stg_webshop__orders') }}

),

final as (

    select
        order_items.order_item_id,
        order_items.order_id,
        order_items.product_id,
        orders.customer_id,
        orders.ordered_at,
        orders.order_status,
        orders.sales_channel,
        -- Display labels live in the mart for the same reason the money columns do: a page may
        -- group and sum what the mart defines, but it may not decide what a value is called.
        -- The raw enum stays alongside as the key to filter and join on.
        {{ sentence_case('orders.order_status') }} as order_status_label,
        {{ sentence_case('orders.sales_channel') }} as channel_label,
        order_items.quantity,
        {{ cents_to_eur('order_items.unit_price_cents') }} as unit_price_eur,
        {{ cents_to_eur('order_items.quantity * order_items.unit_price_cents') }} as gross_amount_eur,
        {{ cents_to_eur('order_items.discount_cents') }} as discount_eur,
        {{ cents_to_eur('order_items.quantity * order_items.unit_price_cents - order_items.discount_cents') }}
            as net_amount_eur,
        {{ cents_to_eur(
            "case when orders.order_status = 'cancelled' then 0
                  else order_items.quantity * order_items.unit_price_cents
                       - order_items.discount_cents end"
        ) }} as realised_net_amount_eur,
        -- The same flag fct_orders carries. Without it a page asking a product question had to
        -- remember `order_status != 'cancelled'`, which is exactly the filter-you-must-remember
        -- this mart layer exists to abolish.
        orders.order_status = 'cancelled' as is_cancelled
    from order_items
    inner join orders on order_items.order_id = orders.order_id

)

select * from final
