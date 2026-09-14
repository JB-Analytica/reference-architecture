---
title: Customers
sidebar_position: 3
description: Six hundred invented customers, ranked by a lifetime value the warehouse computes once and every page inherits.
og:
  title: Customers · JB Analytica Reference Architecture
  image: /og.png
---

The same realised revenue again, at the grain a business actually asks about: per customer, all
time. `lifetime_realised_net_revenue_eur` is a column on the `dim_customers` mart, summed there
from the same order lines the [performance page](/performance) totals by month — so a customer's
lifetime value and the year's revenue cannot disagree, because neither is worked out twice.
`dbt/tests/assert_marts_reconcile.sql` fails the build if they ever do.

These people do not exist. The names, the cities and the email addresses are generated to look
Belgian and nothing more; there is no customer behind any row on this page.

```sql top_customers
select
    full_name,
    city,
    segment_label,
    lifetime_order_count,
    lifetime_realised_net_revenue_eur
from refarch.customers
where has_ordered
order by lifetime_realised_net_revenue_eur desc
limit 20
```

<DataTable data={top_customers} rows=20 search=true>
    <Column id=full_name title="Customer" />
    <Column id=city title="City" />
    <Column id=segment_label title="Segment" />
    <Column id=lifetime_order_count title="Orders" fmt=num0 />
    <Column id=lifetime_realised_net_revenue_eur title="Lifetime net revenue" fmt=eur0 contentType=bar barColor="#A8C9EE" />
</DataTable>

```sql revenue_by_segment
select
    segment_label,
    count(*)                                   as customers,
    sum(lifetime_realised_net_revenue_eur)     as net_revenue_eur
from refarch.customers
where has_ordered
group by 1
order by net_revenue_eur desc
```

<BarChart
    data={revenue_by_segment}
    x=segment_label
    y=net_revenue_eur
    yFmt=eur0
    title="Lifetime net revenue by customer segment"
/>

The table and the chart above both filter on `has_ordered`, which is a mart column rather than a
condition this page invents: 79 of the 600 customers have never placed an order. That is not a gap in the data —
it is what a customer table looks like, and [Architecture](/architecture) explains why the
generator was left alone to produce it.
