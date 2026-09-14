---
title: Webshop performance
---

The nine figures this stack used to publish to Lightdash, rebuilt as code, plus a
[cancellations](/cancellations) page the Lightdash version never had. Every number
below comes from the dbt marts in `warehouse/refarch.duckdb` — nothing is computed in a UI, and
nothing is stored anywhere a pull request cannot see it.

```sql headline
select
    sum(realised_net_amount_eur)                                as net_revenue_eur,
    sum(net_amount_eur)                                         as booked_revenue_eur,
    sum(net_amount_eur) - sum(realised_net_amount_eur)          as revenue_lost_eur,
    count(distinct order_id)                                    as order_count,
    sum(realised_net_amount_eur) / nullif(count(distinct order_id)
        filter (where not is_cancelled), 0)                     as average_order_value_eur,
    count(distinct order_id) filter (where is_cancelled)
        / nullif(count(distinct order_id), 0)::double           as cancellation_rate
from refarch.orders
```

<BigValue data={headline} value=net_revenue_eur title="Net revenue" fmt=eur0 />
<BigValue data={headline} value=order_count title="Orders" fmt=num0 />
<BigValue data={headline} value=average_order_value_eur title="Average order value" fmt=eur2 />
<BigValue data={headline} value=cancellation_rate title="Cancellation rate" fmt=pct1 />

Net revenue is **realised**: cancelled orders count as zero, not as revenue. Booked revenue —
every order as placed — was €<Value data={headline} value=booked_revenue_eur fmt=num0 />, so
cancellations cost <Value data={headline} value=revenue_lost_eur fmt=eur0 />. Both columns live
on `fct_orders`, which is why the two numbers can sit side by side without either being a filter
somebody has to remember. [Cancellations](/cancellations) breaks the gap down.

## Revenue over time

```sql revenue_by_month
select
    date_trunc('month', ordered_at) as month,
    sum(realised_net_amount_eur)    as net_revenue_eur,
    sum(net_amount_eur)             as booked_revenue_eur,
    count(distinct order_id)        as order_count
from refarch.orders
group by 1
order by 1
```

<BarChart
    data={revenue_by_month}
    x=month
    y=net_revenue_eur
    yFmt=eur0
    title="Net revenue by month"
    subtitle="Net of discounts, by the month the order was placed"
/>

The Q4 peak and the upward trend are deliberate: the synthetic generator is configured with
growth and seasonality so the reports have something to show that uniform random data never
would.

## Where the revenue comes from

```sql revenue_by_channel
select
    sales_channel,
    sum(realised_net_amount_eur) as net_revenue_eur,
    count(distinct order_id)     as order_count
from refarch.orders
group by 1
order by net_revenue_eur desc
```

<BarChart
    data={revenue_by_channel}
    x=sales_channel
    y=net_revenue_eur
    yFmt=eur0
    swapXY=true
    title="Net revenue by channel"
/>

```sql order_status_mix
select
    order_status,
    count(distinct order_id) as order_count
from refarch.orders
group by 1
order by order_count desc
```

<BarChart
    data={order_status_mix}
    x=order_status
    y=order_count
    yFmt=num0
    title="Order status mix"
    subtitle="Every order, by the status it is in now"
/>

## Fulfilment

```sql fulfilment_speed
select
    date_trunc('month', ordered_at) as month,
    avg(days_to_ship)               as avg_days_to_ship
from refarch.orders
where days_to_ship is not null
group by 1
order by 1
```

<LineChart
    data={fulfilment_speed}
    x=month
    y=avg_days_to_ship
    yFmt=num1
    title="Average days to ship, by month"
    subtitle="Orders that reached shipped or delivered"
/>
