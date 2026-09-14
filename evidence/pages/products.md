---
title: Products
sidebar_position: 2
---

```sql top_products
select
    p.product_name,
    p.coffee_origin,
    p.roast_level,
    sum(i.realised_net_amount_eur) as net_revenue_eur,
    sum(i.quantity) filter (where not i.is_cancelled) as units
from refarch.order_items i
join refarch.products p on i.product_id = p.product_id
group by 1, 2, 3
order by net_revenue_eur desc
limit 10
```

Product names run to nearly 40 characters, which a horizontal bar chart clips. The table below
is the bar chart: `contentType=bar` draws the bar in the cell, where the label cannot collide
with it.

<DataTable data={top_products} rows=10>
    <Column id=product_name title="Product" />
    <Column id=coffee_origin title="Origin" />
    <Column id=roast_level title="Roast" />
    <Column id=units title="Units" fmt=num0 />
    <Column id=net_revenue_eur title="Net revenue" fmt=eur0 contentType=bar barColor="#A8C9EE" />
</DataTable>
