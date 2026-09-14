{#- Mart money columns must be DECIMAL, never a floating point type.

    Source money is integer cents, so every euro figure on the report is an exact number of
    cents and there is no reason for any of it to be approximate. It was, though: `cents_to_eur`
    returned `round(cents / 100, 2)`, a DOUBLE. Per row that is exact. Summed it is not --
    floating point addition is not associative, so a total depends on the order the rows are
    read in, and that order is an implementation detail of the table, not a fact about the data.

    One total in this warehouse sits exactly on a half cent: Honduras medium roast beans, at
    9313.50 euro of realised revenue. Adding an unrelated label column to fct_order_items
    changed the physical row order, the same sum came out as 9313.499999999998 instead of
    9313.50000000001, and the published figure moved from 9,314 to 9,313 with no change to any
    money anywhere. A number that changes when you add a column to the table is not a number
    anyone should be asked to trust.

    This test is the reason that cannot come back. It reads the warehouse's own column types
    rather than any value, so it fails on the modelling mistake itself rather than waiting for a
    figure to land on a boundary and expose it -- there is exactly one such figure here today,
    and a test that depends on one row of luck is not a test. -#}

with mart_columns as (

    select table_name, column_name, data_type
    from information_schema.columns
    where table_name in (
        '{{ ref('fct_orders').identifier }}',
        '{{ ref('fct_order_items').identifier }}',
        '{{ ref('dim_customers').identifier }}',
        '{{ ref('dim_products').identifier }}'
    )

)

select table_name, column_name, data_type
from mart_columns
where column_name like '%\_eur' escape '\'
  and data_type not like 'DECIMAL%'
