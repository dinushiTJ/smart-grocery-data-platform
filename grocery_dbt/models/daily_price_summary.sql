select
    date_trunc('day', prices.event_timestamp) as price_date,
    prices.barcode,
    products.product_name,
    products.brand,
    products.category,
    count(distinct prices.store_id) as stores_reporting,
    round(avg(prices.price), 2) as average_price,
    min(prices.price) as minimum_price,
    max(prices.price) as maximum_price
from {{ source('silver', 'prices') }} as prices
inner join {{ source('silver', 'products') }} as products
    on prices.barcode = products.barcode
group by
    date_trunc('day', prices.event_timestamp),
    prices.barcode,
    products.product_name,
    products.brand,
    products.category
