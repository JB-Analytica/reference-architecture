{#- The source stores its enums lowercase and snake_cased (`light`, `beans`, `mobile_app`);
    marts expose labels a person reads. DuckDB has no initcap, so capitalise each word
    explicitly: underscores become spaces, split on spaces, upper the first character of each
    part, keep the rest. Empty strings pass through unharmed.

    Underscores are replaced rather than left alone because the label columns are what charts
    axis-label with: without it `mobile_app` reads `Mobile_app` on the report. -#}
{% macro title_case(column) -%}
    array_to_string(
        list_transform(
            string_split(replace(lower({{ column }}), '_', ' '), ' '),
            w -> upper(w[1]) || w[2:]
        ), ' '
    )
{%- endmacro %}
