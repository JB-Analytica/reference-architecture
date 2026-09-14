---
title: Cancellations
sidebar_position: 4
description: Five percent of orders get cancelled, and whether that counts as revenue is the disagreement this whole project exists to settle.
og:
  title: Cancellations · JB Analytica Reference Architecture
  image: /og.png
---

Every figure here is the gap between two columns on `fct_orders`: `net_amount_eur`, the order as
placed, and `realised_net_amount_eur`, which is zero when the order was cancelled. Neither is a
filter somebody has to remember to apply, which is the point — see
`dbt/models/marts/_marts__models.yml`.

```sql summary
select
    count(distinct order_id) filter (where is_cancelled)         as cancelled_orders,
    count(distinct order_id)                                     as order_count,
    count(distinct order_id) filter (where is_cancelled)
        / nullif(count(distinct order_id), 0)::double            as cancellation_rate,
    sum(net_amount_eur) - sum(realised_net_amount_eur)           as revenue_lost_eur,
    (sum(net_amount_eur) - sum(realised_net_amount_eur))
        / nullif(sum(net_amount_eur), 0)                         as revenue_lost_share
from refarch.orders
```

<BigValue data={summary} value=cancellation_rate title="Cancellation rate" fmt=pct2 />
<BigValue data={summary} value=cancelled_orders title="Cancelled orders" fmt=num0 />
<BigValue data={summary} value=revenue_lost_eur title="Revenue lost" fmt=eur0 />
<BigValue data={summary} value=revenue_lost_share title="Share of booked revenue" fmt=pct2 />

The order rate and the revenue share are close but not identical, and the difference is the
useful part: when they diverge, cancellations are landing on orders that are bigger or smaller
than average.

## Over time

```sql by_month
select
    date_trunc('month', ordered_at)                       as month,
    count(distinct order_id) filter (where is_cancelled)
        / nullif(count(distinct order_id), 0)::double     as cancellation_rate,
    sum(net_amount_eur) - sum(realised_net_amount_eur)    as revenue_lost_eur
from refarch.orders
group by 1
order by 1
```

<LineChart
    data={by_month}
    x=month
    y=cancellation_rate
    yFmt=pct1
    title="Cancellation rate by month"
    subtitle="Share of orders placed that month which were later cancelled"
/>

<BarChart
    data={by_month}
    x=month
    y=revenue_lost_eur
    yFmt=eur0
    title="Revenue lost to cancellations, by month"
    subtitle="Booked minus realised, on orders placed that month"
/>

The rate wanders between about 3% and 6.5% with no trend, while the lost amount tracks total
revenue — cancellations scale with volume here rather than clustering in a bad month. Both are
properties of how the synthetic data is generated: cancellation is drawn independently per
order, so the month-to-month movement is sampling noise on roughly 330 orders a month, not a
signal. Worth knowing before trusting a dashboard built only against this stack — nothing here
has been tested against a real spike.

## Where they happen

```sql by_channel
select
    channel_label,
    count(distinct order_id)                             as order_count,
    count(distinct order_id) filter (where is_cancelled)
        / nullif(count(distinct order_id), 0)::double    as cancellation_rate,
    sum(net_amount_eur) - sum(realised_net_amount_eur)   as revenue_lost_eur
from refarch.orders
group by 1
order by cancellation_rate desc
```

<BarChart
    data={by_channel}
    x=channel_label
    y=cancellation_rate
    yFmt=pct1
    swapXY=true
    title="Cancellation rate by channel"
/>

<DataTable data={by_channel}>
    <Column id=channel_label title="Channel" />
    <Column id=order_count title="Orders" fmt=num0 />
    <Column id=cancellation_rate title="Cancellation rate" fmt=pct1 />
    <Column id=revenue_lost_eur title="Revenue lost" fmt=eur0 contentType=bar barColor="#A8C9EE" />
</DataTable>

## Which products

```sql by_product
select
    p.product_name,
    sum(i.net_amount_eur) - sum(i.realised_net_amount_eur) as revenue_lost_eur,
    sum(i.realised_net_amount_eur)                         as realised_revenue_eur
from refarch.order_items i
join refarch.products p on i.product_id = p.product_id
group by 1
having sum(i.net_amount_eur) - sum(i.realised_net_amount_eur) > 0
order by revenue_lost_eur desc
limit 10
```

<DataTable data={by_product} rows=10>
    <Column id=product_name title="Product" />
    <Column id=realised_revenue_eur title="Realised revenue" fmt=eur0 />
    <Column id=revenue_lost_eur title="Lost to cancellation" fmt=eur0 contentType=bar barColor="#A8C9EE" />
</DataTable>

Read this one carefully: a product high on this list is not necessarily a problem product. Lost
revenue is mostly a function of how much the product sells, so the list largely re-ranks the
best sellers. The column worth acting on would be lost revenue as a share of that product's own
booked total — which this synthetic data has no signal in, because cancellation is generated
independently of which product is on the order.
