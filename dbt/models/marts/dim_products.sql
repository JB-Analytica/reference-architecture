with products as (

    select * from {{ ref('stg_webshop__products') }}

),

labelled as (

    -- Display labels live in the mart for the same reason the money columns do: a page may
    -- group and sum what the mart defines, but it may not decide what a value is called. The
    -- raw enums stay alongside as the keys to filter and join on. They are computed here in
    -- their own CTE so product_name below is composed from the same labels the charts use --
    -- one definition, not two that can drift apart.
    select
        *,
        {{ title_case('coffee_origin') }} as origin_label,
        {{ title_case('roast_level') }} as roast_label,
        {{ title_case('product_category') }} as category_label
    from products

),

final as (

    select
        product_id,
        sku,
        -- The source has no product name; the catalogue is described by attributes.
        -- Compose a human name once, here, so every chart labels products the same way.
        origin_label || ' · ' || roast_label || ' roast · '
            || category_label || ' ' || cast(weight_grams as string) || 'g'
            as product_name,
        coffee_origin,
        roast_level,
        product_category,
        origin_label,
        roast_label,
        category_label,
        weight_grams,
        {{ cents_to_eur('unit_price_cents') }} as unit_price_eur,
        {{ cents_to_eur('cost_cents') }} as unit_cost_eur,
        {{ cents_to_eur('unit_price_cents - cost_cents') }} as unit_margin_eur,
        is_active,
        created_at as listed_at
    from labelled

)

select * from final
