with orders as (

    select * from {{ ref('stg_webshop__orders') }}

),

order_money as (

    select * from {{ ref('int_orders__items_aggregated') }}

)

select
    orders.order_id,
    orders.customer_id,
    orders.ordered_at,
    date(orders.ordered_at) as order_date,
    orders.order_status,
    orders.sales_channel,
    -- Display labels live in the mart for the same reason the money columns do: a page may
    -- group and sum what the mart defines, but it may not decide what a value is called.
    -- The raw enum stays alongside as the key to filter and join on.
    {{ sentence_case('orders.order_status') }} as order_status_label,
    {{ sentence_case('orders.sales_channel') }} as channel_label,
    orders.shipping_city,
    orders.shipping_country,
    orders.shipped_at,
    orders.delivered_at,
    coalesce(order_money.line_item_count, 0) as line_item_count,
    coalesce(order_money.units, 0) as units,
    {{ cents_to_eur('coalesce(order_money.gross_amount_cents, 0)') }} as gross_amount_eur,
    {{ cents_to_eur('coalesce(order_money.discount_cents, 0)') }} as discount_eur,
    {{ cents_to_eur('coalesce(order_money.net_amount_cents, 0)') }} as net_amount_eur,
    {{ cents_to_eur(
        "case when orders.order_status = 'cancelled' then 0
              else coalesce(order_money.net_amount_cents, 0) end"
    ) }} as realised_net_amount_eur,
    orders.order_status = 'cancelled' as is_cancelled,
    orders.order_status = 'delivered' as is_delivered,
    -- Keyed off shipped_at alone. An order shipped if and only if it has a shipping
    -- timestamp; order_status is a second, independent signal, and in this source the two
    -- disagree -- 600 orders sit at cancelled, paid or pending with a shipped_at set,
    -- because the generator draws each column independently (see
    -- docs/architecture/README.md). Gating on status as well silently dropped every one of
    -- them. Cancelled orders that did ship keep a real ship time; is_cancelled is on this
    -- row for anyone who wants them out.
    case
        when orders.shipped_at is not null
            then date_diff('hour', orders.ordered_at, orders.shipped_at) / 24.0
    end as days_to_ship
from orders
left join order_money on orders.order_id = order_money.order_id
