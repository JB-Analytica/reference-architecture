---
title: Webshop performance
sidebar_position: 1
---

The webshop's trading year. Every number here is a column defined in a dbt mart and reviewed in
a pull request — nothing is computed in this page, and nothing is stored anywhere a code review
cannot see it. [Architecture](/architecture) says how it is built, and where the data behind it
is thinner than it looks.

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
every order as placed — was <Value data={headline} column=booked_revenue_eur fmt=eur0 />, so
cancellations cost <Value data={headline} column=revenue_lost_eur fmt=eur0 />. Both columns live
on `fct_orders`, which is why the two numbers can sit side by side without either being a filter
somebody has to remember. [Cancellations](/cancellations) breaks the gap down.

Average order value is realised revenue over orders that were not cancelled. It reads low —
about one generated order in nine has no line items at all and so contributes €0, which is an
artefact of the synthetic source rather than a fact about the business.
[Architecture](/architecture) says where else that shows.

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
    subtitle="Every order carrying a shipping timestamp, by the month it was placed"
/>
