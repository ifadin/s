WITH
  date_ranges AS (
      SELECT DISTINCT _PARTITIONDATE as window_left, DATE_ADD(_PARTITIONDATE, INTERVAL 364 DAY) as window_right
      FROM `orders`
      WHERE _PARTITIONDATE BETWEEN '2016-01-01' AND '2018-12-01'),
  time_buckets AS (
      SELECT *, ROW_NUMBER() OVER (ORDER BY window_left) as bucket_id
      FROM date_ranges),
  orders_across_time_buckets AS (
      SELECT iso_date, customer_hash, transaction_hash, buckets.*
      FROM `orders` JOIN time_buckets as buckets ON iso_date BETWEEN window_left AND window_right
      WHERE _PARTITIONDATE BETWEEN '2016-01-01' AND '2018-12-01'),
  orders_per_bucket AS (
      SELECT bucket_id, APPROX_COUNT_DISTINCT(transaction_hash) as orders
      FROM orders_across_time_buckets GROUP BY bucket_id, customer_hash),
  percentiles AS (
      SELECT DISTINCT bucket_id,
      PERCENTILE_CONT(orders, 0.5) OVER(PARTITION BY bucket_id) as median,
      PERCENTILE_CONT(orders, 0.95) OVER(PARTITION BY bucket_id) as p95,
      PERCENTILE_CONT(orders, 0.99) OVER(PARTITION BY bucket_id) as p99
      FROM orders_per_bucket
      ORDER BY bucket_id)

SELECT AVG(median) as avg_median, AVG(p95) as avg_p95, AVG(p99) as avg_p99 FROM percentiles