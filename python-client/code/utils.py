from functools import wraps
import statistics

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
