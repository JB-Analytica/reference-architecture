---
title: Customers
---

`lifetime_order_count` and `lifetime_realised_net_revenue_eur` are columns on the `dim_customers` mart,
not something this page works out — see `dbt/models/marts/dim_customers.sql`.

```sql top_customers
select
    full_name,
    city,
    customer_segment,
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
    <Column id=customer_segment title="Segment" />
    <Column id=lifetime_order_count title="Orders" fmt=num0 />
    <Column id=lifetime_realised_net_revenue_eur title="Lifetime net revenue" fmt=eur0 contentType=bar barColor="#A8C9EE" />
</DataTable>

```sql revenue_by_segment
select
    customer_segment,
    count(*)                          as customers,
    sum(lifetime_realised_net_revenue_eur)     as net_revenue_eur
from refarch.customers
where has_ordered
group by 1
order by net_revenue_eur desc
```

<BarChart
    data={revenue_by_segment}
    x=customer_segment
    y=net_revenue_eur
    yFmt=eur0
    title="Lifetime net revenue by customer segment"
/>
