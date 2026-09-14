---
title: A data platform you can read, trust and build on
---

[JB Analytica](https://www.jbanalytica.com/) is a data architecture and analytics engineering
consultancy based in Belgium, working across the Benelux.

This is a **reference project** — not a client engagement. It is a complete data platform, built
end to end as a worked example and published with every line of its source: source system,
ingestion, warehouse, semantic layer, dashboards. The business it runs on is invented, the data
is generated, and there is no customer behind any number on this site.

We built it because most consultancies ask you to take their standards on faith, and this is the
alternative: you can open it, clone it and run it. Reading it is the point — it is what makes the
rest checkable rather than claimed. The pages in the sidebar are the finished product; the
interesting part is everything underneath them.

## The business it is built around

An invented one: a specialty-coffee webshop in Belgium, selling beans, ground coffee, capsules
and equipment direct to consumers through four channels — its own site, its mobile app, a
marketplace, and a physical store.

Inventing it was the point. A real engagement's data cannot be published, so a case study built
on one is a story you have to believe. This is the opposite: the business is made up, and
therefore every number, every model and every test behind it can be shown. What is *not* made up
is the shape — the size, the channel mix, the seasonality and the mess — because a platform that
only works on convenient data demonstrates nothing.

```sql shape
select
    count(*)                                     as orders,
    count(distinct customer_id)                  as customers,
    sum(realised_net_amount_eur)                 as revenue_eur,
    sum(net_amount_eur)                          as booked_eur,
    count(*) filter (where is_cancelled)
        / nullif(count(*), 0)::double            as cancellation_rate,
    min(order_date)                              as from_date,
    max(order_date)                              as to_date
from refarch.orders
```

<BigValue data={shape} value=revenue_eur title="Realised revenue, 12 months" fmt=eur0 />
<BigValue data={shape} value=orders title="Orders" fmt=num0 />
<BigValue data={shape} value=customers title="Customers who ordered" fmt=num0 />

Small enough that every report still comes out of a spreadsheet. Big enough that it has started
to hurt. Orders live in the operational database behind the shop and nowhere else, so every
question about last quarter is answered by exporting a CSV and rebuilding the same arithmetic by
hand — which is the point at which two people produce two different revenue figures and both are
defensible.

## The problem it reproduces

The scenario is built around the failure we are most often called about: **the numbers do not
agree, and the dashboards are not the reason.**

Ask what revenue was and it depends who you ask, because <Value data={shape} column=cancellation_rate fmt=pct1 /> of orders get cancelled and nothing says whether a cancelled order counts. One report includes them, another quietly excludes them, and the gap is real money — <Value data={shape} column=revenue_eur fmt=eur0 /> of revenue that actually happened, against <Value data={shape} column=booked_eur fmt=eur0 /> of orders as placed. Nobody wrote a bug. Two people made two reasonable choices, a year apart, in two different files.

That is not fixable in a BI tool, because a BI tool is where the disagreement surfaces, not where
it lives. It is fixable one layer down, by defining the number once.

## How it is built

Four stages, run by four commands, from a data model to a published report:

| | | |
|---|---|---|
| **1. Model the source** | A data model in DBML becomes a running database with realistic, relationship-preserving data — so the platform can be built and demonstrated before anyone has production access | `model2data` |
| **2. Ingest** | Incremental extraction that merges on the primary key, so re-running never duplicates a row | `dlt` |
| **3. Model the warehouse** | Staging, intermediate and mart layers, with the business definitions in the marts and tests that hold them there | `dbt` |
| **4. Publish** | A static report over the marts, with no server and no per-seat licence | `Evidence` |

[Architecture](/architecture) is the honest version of this, including the two seams that let the
whole thing move onto a production database and a cloud warehouse by changing one connection
string each — and what the generated data still cannot teach you.

## What it demonstrates

**The semantic layer is the product.** `net_amount_eur` is the order as placed;
`realised_net_amount_eur` is zero when it was cancelled. Two columns, defined once in the
warehouse, reviewed in a pull request, and inherited by every page on this site. Neither is a
filter somebody has to remember, because the ones people have to remember are the ones they
forget.

**Tested like any other code.** Every build runs the full suite before anything publishes, and
the checks that matter compare numbers two different models worked out independently from the
same source. Column-level tests
pass happily on a model that is uniformly wrong; that is exactly how a rounding bug once survived
review here, inflating a revenue column a hundredfold while every row still looked plausible.
The test that now catches it is in the repository, and so is the account of how it got in.

**It is a foundation, not a demo.** The layering is the part that survives contact with a real
business. A new mart is added without touching a line of staging or ingestion. A new source
table arrives, gets its own staging model, and nothing downstream notices. And the warehouse
itself is one connection string: the two seams either side of ingestion mean this whole stack
moves onto a production database and BigQuery or Snowflake without a single model being rewritten.
Growth gets absorbed rather than triggering a rebuild, which is the difference between a platform
and a prototype.

**It runs with no account at all.** Clone it, run four commands, and the whole platform builds on
a laptop — no cloud project, no credentials, no bill. That is not a demo trick. It is what lets
an architecture be reviewed and argued with before anyone commits to buying it.

## Where to look next

- [Webshop performance](/performance) — revenue, orders, fulfilment: the report a business like this needs
- [Products](/products) and [Customers](/customers) — the same definitions, at two other grains
- [Cancellations](/cancellations) — the question the whole example turns on, answered once
- [Architecture](/architecture) — how it is built, and where this data is thinner than it looks
- [The source, on GitHub](https://github.com/JB-Analytica/reference-architecture) — all of it, MIT licensed

## If this is your situation

If two reports in your business disagree and nobody can say which is right, that is the problem
we build for. A scoping call costs nothing and ends in a proposal for the actual work, or in an
honest answer that we are not the right people.

**[Start with the problem →](https://www.jbanalytica.com/#contact)**
