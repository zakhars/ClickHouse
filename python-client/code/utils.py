from functools import wraps
import statistics
import time

# Decorator to measure function execution time and show stats
def avg_time(n_calls=10, verbose=True, return_stats=False):
   def decorator(func):
      @wraps(func)
      def wrapper(*args, **kwargs):
         times = []

         result = None
         for i in range(n_calls):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            times.append(end_time - start_time)

         avg_time = statistics.mean(times)
         min_time = min(times)
         max_time = max(times)
         std_dev = statistics.stdev(times) if len(times) > 1 else 0

         if verbose:
            print(f"\nStats for function '{func.__name__}':")
            print(f"   Calls: {n_calls}")
            print(f"   Avg: {avg_time:.6f} s ({avg_time * 1000:.3f} ms)")
            print(f"   Min: {min_time:.6f} s")
            print(f"   Max: {max_time:.6f} s")
            print(f"   Stddev: {std_dev:.6f} s")

         if return_stats:
            return result, {
               'avg': avg_time,
               'min': min_time,
               'max': max_time,
               'std': std_dev,
               'times': times
            }
         return result
      return wrapper
   return decorator


def trace(msg, enabled=True):
   def decorator(func):
      @wraps(func)
      def wrapper(*args, **kwargs):
         if enabled: print(f"\n{msg}... ", flush=True, end='')
         result = func(*args, **kwargs)
         if enabled: print(f"Success", flush=True)
         return result
      return wrapper
   return decorator

def is_datetime_type(type_str):
    return 'DateTime64' in str(type_str)


def print_clickhouse_rowset(result, num_rows=0):
   if num_rows < 0: return

   print(f'\nNumber of rows returned: {result.row_count}', flush=True)

   columns = result.column_names
   rows = result.result_rows
   types = result.column_types

   widths = [len(str(col)) for col in columns]
   for row in rows[:10]:
      for i, val in enumerate(row):
         widths[i] = max(widths[i], len(str(val)))

   header = " | ".join(str(col).ljust(widths[i]) for i, col in enumerate(columns))
   print('')
   print(header)
   print("-" * len(header))

   for row in rows[:num_rows]:
      formatted_values = []
      for val, type, width in zip(row, types, widths):
         if is_datetime_type(type):
            microseconds = val.microsecond
            nanoseconds = val.nanosecond if hasattr(val, 'nanosecond') else 0
            total_nanoseconds = microseconds * 1000 + nanoseconds
            val = val.strftime('%Y-%m-%d %H:%M:%S') + f'.{total_nanoseconds:09d}'
         formatted_values.append(str(val).ljust(width))
      row_to_print = " | ".join(formatted_values)
      print(row_to_print)

